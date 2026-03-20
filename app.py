from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
import os
from werkzeug.utils import secure_filename
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
from flask import session, url_for, redirect

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

# Global variable to store report card data
report_df = {} # Dict mapping session_id to dataframe

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
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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

@app.route('/report_card/upload', methods=['POST'])
def upload_report_card():
    global report_df
    session_id = session.get('report_session_id', os.urandom(16).hex())
    session['report_session_id'] = session_id
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'report_' + filename)
        file.save(filepath)
        try:
            df = pd.read_excel(filepath)
            df = df.fillna("")
            report_df[session_id] = df
            columns = df.columns.tolist()
            return jsonify({
                "message": "Report card data uploaded successfully",
                "columns": columns,
                "total": len(df)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/uploads/<path:filename>')
def download_template(filename):
    return send_from_directory('uploads', filename)

@app.route('/report_card/data/<int:index>', methods=['GET'])
def get_report_data(index):
    global report_df
    session_id = session.get('report_session_id')
    if not session_id or session_id not in report_df:
        return jsonify({"error": "No report card data uploaded"}), 400
    df = report_df[session_id]
    if 0 <= index < len(df):
        row = df.iloc[index].to_dict()
        return jsonify(row)
    else:
        return jsonify({"error": "Index out of range"}), 404

@app.route('/report_card/download/<int:index>', methods=['GET'])
def download_report_card(index):
    global report_df
    session_id = session.get('report_session_id')
    if not session_id or session_id not in report_df:
        return jsonify({"error": "No report card data uploaded"}), 400
    df = report_df[session_id]
    if 0 <= index < len(df):
        data = df.iloc[index].to_dict()
        pdf_bytes = generate_report_pdf(data)

        filename = f"Report_Card_{data.get('Student_Name', 'Student')}_{data.get('Roll_No', index)}.pdf"
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    else:
        return jsonify({"error": "Index out of range"}), 404

def generate_report_pdf(data):
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_line_width(1)
            self.rect(5, 5, 200, 287) # Outer border

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header Section
    pdf.set_font("helvetica", 'B', 20)
    pdf.set_text_color(128, 0, 0)
    pdf.cell(0, 10, "KENDRIYA VIDYALAYA CRPF DURGAPUR", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", 'B', 14)
    pdf.cell(0, 8, "PROGRESS CARD FOR THE ACADEMIC SESSION " + str(data.get('Academic_Session', '')), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # Student Info Table
    pdf.set_font("helvetica", 'B', 9)
    info_fields = [
        [("STUDENT'S NAME:", data.get('Student_Name', '')), ("ROLL NO:", data.get('Roll_No', '')), ("ADMN NO:", data.get('ADMN_NO', ''))],
        [("FATHER'S NAME:", data.get('Father_Name', '')), ("CLASS & SEC:", data.get('Class_Section', '')), ("DOB:", data.get('DOB', ''))],
        [("MOTHER'S NAME:", data.get('Mother_Name', '')), ("APAAR ID:", data.get('APAAR_ID', '')), ("PEN NO:", data.get('PEN_NO', ''))]
    ]

    col_widths = [40, 26, 40, 26, 40, 28]
    for row in info_fields:
        for i, (label, val) in enumerate(row):
            pdf.set_font("helvetica", 'B', 8)
            pdf.cell(col_widths[i*2], 6, label, border=1)
            pdf.set_font("helvetica", '', 8)
            pdf.cell(col_widths[i*2+1], 6, str(val), border=1)
        pdf.ln()

    pdf.ln(2)

    # Group 1 Subjects Table
    pdf.set_fill_color(255, 255, 204) # Yellow
    pdf.set_font("helvetica", 'B', 10)
    pdf.cell(0, 6, "(A) GROUP 1 : SUBJECTS", border=1, align='C', fill=True, new_x="LMARGIN", new_y="NEXT")

    # Marks Headers
    pdf.set_font("helvetica", 'B', 7)
    pdf.cell(30, 12, "Subjects", border=1, align='C', fill=True)
    pdf.cell(50, 6, "Term I", border=1, align='C', fill=True)
    pdf.cell(50, 6, "Term II", border=1, align='C', fill=True)
    pdf.cell(20, 12, "Grand Total", border=1, align='C', fill=True)
    pdf.cell(30, 12, "Grade", border=1, align='C', fill=True)

    pdf.set_xy(40, pdf.get_y() + 6)
    sub_headers = ["PT", "WW", "SEA", "LD", "HY"]
    for _ in range(2):
        for h in sub_headers:
            pdf.cell(10, 6, h, border=1, align='C', fill=True)
    pdf.ln()

    # Subjects Data
    subjects = ['English', 'Hindi', 'Maths', 'Science', 'Social_Science', 'Sanskrit']
    pdf.set_font("helvetica", '', 8)
    for sub in subjects:
        pdf.set_font("helvetica", 'B', 8)
        pdf.cell(30, 6, sub, border=1)
        pdf.set_font("helvetica", '', 8)
        # Term 1
        for f in ['PT_M', 'WW', 'SEA', 'LD', 'HY']:
            val = data.get(f"{sub}_T1_{f}", "")
            pdf.cell(10, 6, str(val), border=1, align='C')
        # Term 2
        for f in ['PT_M', 'WW', 'SEA', 'LD', 'SEE']:
            val = data.get(f"{sub}_T2_{f}", "")
            pdf.cell(10, 6, str(val), border=1, align='C')

        pdf.cell(20, 6, str(data.get(f"{sub}_Grand_Total_M", "")), border=1, align='C')
        pdf.set_fill_color(204, 255, 204) # Green
        pdf.cell(30, 6, str(data.get(f"{sub}_Grade", "")), border=1, align='C', fill=True)
        pdf.set_fill_color(255, 255, 204) # Back to Yellow
        pdf.ln()

    pdf.ln(2)
    # Group 2 and Others
    pdf.set_font("helvetica", 'B', 10)
    pdf.cell(0, 6, "(B) GROUP 2 : SUBJECTS", border=1, align='C', fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", 'B', 8)
    pdf.cell(40, 6, "Subject", border=1, fill=True)
    pdf.cell(20, 6, "Term I", border=1, align='C', fill=True)
    pdf.cell(20, 6, "Term II", border=1, align='C', fill=True)
    pdf.cell(40, 6, "Attendance", border=1, align='C', fill=True)
    pdf.cell(80, 6, "Remarks", border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font("helvetica", '', 8)
    group2 = [("Art", "Art_T1", "Art_T2"), ("PE", "PE_T1", "PE_T2"), ("Vocational", "Vocational_T1", "Vocational_T2"), ("Digital", "Digital_T1", "Digital_T2")]
    for i, (name, t1, t2) in enumerate(group2):
        pdf.cell(40, 6, name, border=1)
        pdf.cell(20, 6, str(data.get(t1, "")), border=1, align='C')
        pdf.cell(20, 6, str(data.get(t2, "")), border=1, align='C')
        if i == 0:
            curr_x, curr_y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(40, 12, f"T1: {data.get('Attendance_T1', '')}\nT2: {data.get('Attendance_T2', '')}", border=1, align='C')
            pdf.set_xy(curr_x + 40, curr_y)
            pdf.multi_cell(80, 24, str(data.get('Remarks', '')), border=1, align='C')
        pdf.ln()

    pdf.ln(10)
    pdf.set_font("helvetica", 'B', 10)
    pdf.cell(50, 10, "CLASS TEACHER", align='C')
    pdf.cell(50, 10, "CHECKER", align='C')
    pdf.cell(50, 10, "VICE PRINCIPAL", align='C')
    pdf.cell(50, 10, "PRINCIPAL", align='C')

    return bytes(pdf.output())

@app.route('/get_image/<path:filename>')
def get_image(filename):
    # Search for image in the configured PHOTO_FOLDER or in root photos
    save_path = app.config['PHOTO_FOLDER']
    if os.path.exists(os.path.join(save_path, filename)):
        return send_from_directory(save_path, filename)
    elif os.path.exists(os.path.join('photos', filename)):
        return send_from_directory('photos', filename)
    else:
        return send_from_directory('static/images', 'placeholder.jpg')

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
    
    filename = data.get('filename', 'photo.jpg')
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        filename += '.jpg'
    
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
    img.save(output, format="JPEG", quality=quality)
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
    app.run(debug=False, host='0.0.0.0', port=8080)
