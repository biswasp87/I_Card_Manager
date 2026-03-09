from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import pandas as pd
import base64
from io import BytesIO
from PIL import Image
import json
import psycopg2
from psycopg2 import sql
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import Flow
from flask import session, url_for, redirect, send_file, abort

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
    if not base or base == 'undefined':
        base = os.path.abspath('.')

    if '..' in base: base = os.path.abspath('.')
    try:
        items = os.listdir(base)
        dirs = [d for d in items if os.path.isdir(os.path.join(base, d))]
        return jsonify({
            "current": base,
            "parent": os.path.dirname(base),
            "dirs": sorted(dirs)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        'client_secrets.json',
        scopes=['https://www.googleapis.com/auth/drive.file'],
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(access_type='offline')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        'client_secrets.json',
        scopes=['https://www.googleapis.com/auth/drive.file'],
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return 'Authenticated successfully! You can close this window.'

def upload_to_drive(image_bytes, filename, folder_id=None):
    from google.oauth2.credentials import Credentials
    creds = Credentials(**session['credentials'])
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaIoBaseUpload(BytesIO(image_bytes), mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

@app.route('/save_photo', methods=['POST'])
def save_photo():
    data = request.json
    if not data or 'image' not in data:
        return jsonify({"error": "No image data"}), 400

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

    # Handle Destination
    destination = data.get('destination', 'local')
    if destination == 'google_drive':
        if 'credentials' not in session:
            return jsonify({"error": "Not authenticated with Google Drive"}), 401
        try:
            file_id = upload_to_drive(final_image_bytes, filename, data.get('drive_folder_id'))
            return jsonify({"message": f"Photo saved to Google Drive (ID: {file_id})"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        save_path = data.get('save_path', app.config['PHOTO_FOLDER'])
        if not save_path:
            save_path = app.config['PHOTO_FOLDER']
        os.makedirs(save_path, exist_ok=True)
        full_path = os.path.join(save_path, filename)
        with open(full_path, 'wb') as f:
            f.write(final_image_bytes)

        # Update source if requested
        update_col = data.get('update_column')
        if update_col and student_df is not None:
            idx = data.get('index')
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

        return jsonify({"message": f"Photo saved locally to {full_path}"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
