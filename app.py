from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import pandas as pd
import base64
from io import BytesIO
from PIL import Image
import json
import psycopg2
from psycopg2 import sql
from flask import session, url_for, redirect, send_file, abort
from google.cloud import bigquery, storage

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_for_dev')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PHOTO_FOLDER'] = 'photos'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PHOTO_FOLDER'], exist_ok=True)

# Global variable to store student data
student_df = None
source_info = {}
current_project = None

# Google Cloud Clients
def get_bq_client():
    return bigquery.Client()

def get_storage_client():
    return storage.Client()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_db', methods=['POST'])
def fetch_db():
    global student_df
    data = request.json
    try:
        conn_params = {
            'host': data['host'],
            'database': data['database'],
            'user': data['user'],
            'password': data['password'],
            'port': data.get('port', 5432)
        }
        conn = psycopg2.connect(**conn_params)
        # Use psycopg2.sql to safely quote table name
        query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(data['table']))
        student_df = pd.read_sql(query.as_string(conn), conn)
        conn.close()
        student_df = student_df.fillna("")
        columns = student_df.columns.tolist()

        source_info['type'] = 'db'
        source_info['params'] = conn_params
        source_info['table'] = data['table']

        return jsonify({
            "message": "Data fetched from database successfully",
            "columns": columns,
            "total": len(student_df)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create_project', methods=['POST'])
def create_project():
    global student_df, current_project, source_info

    project_name = request.form.get('projectName')
    source_type = request.form.get('sourceType')

    if not project_name:
        return jsonify({"error": "Project name is required"}), 400

    # Sanitize project name for BigQuery table (letters, numbers, underscores)
    safe_project_name = "".join([c if c.isalnum() else "_" for c in project_name])

    # 1. Fetch Data
    temp_df = None
    if source_type == 'excel':
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        temp_df = pd.read_excel(filepath)
    elif source_type == 'db':
        try:
            conn_params = {
                'host': request.form.get('host'),
                'database': request.form.get('database'),
                'user': request.form.get('user'),
                'password': request.form.get('password'),
                'port': request.form.get('port', 5432)
            }
            conn = psycopg2.connect(**conn_params)
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(request.form.get('table')))
            temp_df = pd.read_sql(query.as_string(conn), conn)
            conn.close()
            source_info['params'] = conn_params
            source_info['table'] = request.form.get('table')
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if temp_df is None:
        return jsonify({"error": "Failed to load data"}), 400

    temp_df = temp_df.fillna("")
    if 'Image Link' not in temp_df.columns:
        temp_df['Image Link'] = ""

    # 2. Setup BigQuery
    bq_client = get_bq_client()
    dataset_id = "I_Card_Manage"
    dataset_ref = bq_client.dataset(dataset_id)
    try:
        bq_client.get_dataset(dataset_ref)
    except Exception:
        bq_client.create_dataset(bigquery.Dataset(dataset_ref))

    table_id = f"{bq_client.project}.{dataset_id}.{safe_project_name}"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    bq_client.load_table_from_dataframe(temp_df, table_id, job_config=job_config).result()

    # 3. Setup GCS
    storage_client = get_storage_client()
    bucket_name = f"icm-{bq_client.project}"
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except Exception:
        bucket = storage_client.create_bucket(bucket_name)

    # Create virtual folder by adding an empty object with trailing slash
    blob = bucket.blob(f"{safe_project_name}/")
    blob.upload_from_string('')

    student_df = temp_df
    current_project = safe_project_name
    source_info['type'] = source_type

    return jsonify({
        "message": f"Project '{project_name}' created successfully",
        "columns": student_df.columns.tolist(),
        "total": len(student_df)
    })

@app.route('/list_projects', methods=['GET'])
def list_projects():
    bq_client = get_bq_client()
    dataset_id = "I_Card_Manage"
    try:
        tables = bq_client.list_tables(dataset_id)
        return jsonify([t.table_id for t in tables])
    except Exception as e:
        return jsonify([])

@app.route('/load_project', methods=['POST'])
def load_project():
    global student_df, current_project
    bq_client = get_bq_client()
    project_id = request.json.get('projectName')
    dataset_id = "I_Card_Manage"
    table_id = f"{bq_client.project}.{dataset_id}.{project_id}"

    try:
        student_df = bq_client.query(f"SELECT * FROM `{table_id}`").to_dataframe()
        student_df = student_df.fillna("")
        current_project = project_id
        return jsonify({
            "message": f"Project '{project_id}' loaded",
            "columns": student_df.columns.tolist(),
            "total": len(student_df)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_project', methods=['POST'])
def delete_project():
    bq_client = get_bq_client()
    project_id = request.json.get('projectName')
    dataset_id = "I_Card_Manage"
    table_id = f"{bq_client.project}.{dataset_id}.{project_id}"
    try:
        bq_client.delete_table(table_id, not_found_ok=True)
        return jsonify({"message": f"Project '{project_id}' deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    global student_df
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            student_df = pd.read_excel(filepath)
            # Replace NaN with empty string for JSON serialization
            student_df = student_df.fillna("")
            columns = student_df.columns.tolist()

            source_info['type'] = 'excel'
            source_info['path'] = filepath

            return jsonify({
                "message": "File uploaded successfully",
                "columns": columns,
                "total": len(student_df)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/data/all', methods=['GET'])
def get_all_data():
    global student_df
    if student_df is None:
        return jsonify({"error": "No data uploaded"}), 400
    return jsonify(student_df.to_dict(orient='records'))

@app.route('/data/<int:index>', methods=['GET'])
def get_data(index):
    global student_df
    if student_df is None:
        return jsonify({"error": "No data uploaded"}), 400
    if 0 <= index < len(student_df):
        row = student_df.iloc[index].to_dict()
        return jsonify(row)
    else:
        return jsonify({"error": "Index out of range"}), 404

@app.route('/get_image/<path:filename>')
def get_image(filename):
    custom_path = request.args.get('path')

    # Security check: Ensure the filename is just a name and path doesn't escape
    if '..' in filename or (custom_path and '..' in custom_path):
        abort(400, "Directory traversal not allowed")

    if custom_path and os.path.isdir(custom_path):
        # Additional safety: verify the file is actually inside the directory
        full_path = os.path.abspath(os.path.join(custom_path, filename))
        if full_path.startswith(os.path.abspath(custom_path)):
            if os.path.exists(full_path):
                return send_from_directory(custom_path, filename)

    save_path = app.config['PHOTO_FOLDER']
    if os.path.exists(os.path.join(save_path, filename)):
        return send_from_directory(save_path, filename)
    elif os.path.exists(os.path.join('photos', filename)):
        return send_from_directory('photos', filename)
    else:
        return send_from_directory('static/images', 'placeholder.jpg')

@app.route('/list_dirs', methods=['GET'])
def list_dirs():
    base = request.args.get('base')
    app_root = os.path.abspath('.')

    if not base or base == 'undefined':
        base = app_root
    else:
        base = os.path.abspath(base)

    # Restrict browsing to the app root and its subdirectories
    if not base.startswith(app_root):
        base = app_root

    try:
        items = os.listdir(base)
        dirs = [d for d in items if os.path.isdir(os.path.join(base, d))]
        return jsonify({
            "current": base,
            "parent": os.path.dirname(base) if base != app_root else app_root,
            "dirs": sorted(dirs)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/save_photo', methods=['POST'])
def save_photo():
    data = request.json
    if not data or 'image' not in data:
        return jsonify({"error": "No image data"}), 400

    idx = data.get('index')
    if student_df is None:
         return jsonify({"error": "No student data loaded"}), 400
    if idx is None or not (0 <= idx < len(student_df)):
         return jsonify({"error": "Invalid student index"}), 400

    image_data = data['image'].split(',')[1]
    image_bytes = base64.b64decode(image_data)
    img = Image.open(BytesIO(image_bytes))

    fmt = data.get('format', 'JPEG').upper()
    ext = '.png' if fmt == 'PNG' else '.jpg'
    filename = data.get('filename', 'photo')
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        filename += ext

    # Handle Compression
    quality = 95
    if data.get('compression') == 'compressed':
        quality = int(data.get('quality', 60))
        target_size_kb = data.get('target_size')
        if target_size_kb:
            target_size = int(target_size_kb) * 1024
            # Iteratively find the best quality for target size
            low, high = 1, quality
            while low <= high:
                mid = (low + high) // 2
                out = BytesIO()
                img.save(out, format="JPEG", quality=mid)
                if out.tell() < target_size:
                    quality = mid
                    low = mid + 1
                else:
                    high = mid - 1

    output = BytesIO()
    img_format = 'PNG' if fmt == 'PNG' else 'JPEG'
    if img_format == 'PNG':
        img.save(output, format=img_format)
    else:
        img.save(output, format=img_format, quality=quality)
    final_image_bytes = output.getvalue()

    # Save locally as fallback/cache
    save_path = app.config['PHOTO_FOLDER']
    os.makedirs(save_path, exist_ok=True)
    full_path = os.path.join(save_path, filename)
    with open(full_path, 'wb') as f:
        f.write(final_image_bytes)

    # Update source if requested
    update_col = data.get('update_column')
    if update_col and student_df is not None:
        if idx is not None:
            student_df.at[idx, update_col] = filename
            if source_info.get('type') == 'excel':
                student_df.to_excel(source_info['path'], index=False)
            elif source_info.get('type') == 'db':
                try:
                    conn = psycopg2.connect(**source_info['params'])
                    cur = conn.cursor()
                    id_col = student_df.columns[0]
                    id_val = student_df.iloc[idx][id_col]

                    update_query = sql.SQL("UPDATE {} SET {} = %s WHERE {} = %s").format(
                        sql.Identifier(source_info['table']),
                        sql.Identifier(update_col),
                        sql.Identifier(id_col)
                    )
                    cur.execute(update_query, (filename, id_val))
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception as e:
                    print(f"DB update error: {e}")

        # Upload to GCS if project is active
        if current_project:
            try:
                storage_client = get_storage_client()
                bq_client = get_bq_client()
                bucket_name = f"icm-{bq_client.project}"
                bucket = storage_client.get_bucket(bucket_name)
                gcs_path = f"{current_project}/{filename}"
                blob = bucket.blob(gcs_path)
                blob.upload_from_string(final_image_bytes, content_type=f"image/{img_format.lower()}")

                # Update BigQuery
                dataset_id = "I_Card_Manage"
                table_id = f"{bq_client.project}.{dataset_id}.{current_project}"
                image_link = f"https://storage.googleapis.com/{bucket_name}/{gcs_path}"

                id_col = student_df.columns[0]
                id_val = student_df.iloc[idx][id_col]

                # Determine correct BigQuery type for ID column to avoid 400 mismatch error
                bq_type = "STRING"
                param_val = str(id_val)
                if pd.api.types.is_integer_dtype(student_df[id_col]):
                    bq_type = "INT64"
                    param_val = int(id_val)
                elif pd.api.types.is_float_dtype(student_df[id_col]):
                    bq_type = "FLOAT64"
                    param_val = float(id_val)

                query = f"""
                    UPDATE `{table_id}`
                    SET `Image Link` = @image_link
                    WHERE `{id_col}` = @id_val
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("image_link", "STRING", image_link),
                        bigquery.ScalarQueryParameter("id_val", bq_type, param_val),
                    ]
                )
                bq_client.query(query, job_config=job_config).result()
                student_df.at[idx, 'Image Link'] = image_link
            except Exception as e:
                print(f"GCS/BQ Update Error: {e}")

        return jsonify({"message": f"Photo saved locally to {full_path}"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
