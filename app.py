from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import pandas as pd
import base64
from io import BytesIO
from PIL import Image
import json
import psycopg2
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import Flow
from flask import session, url_for, redirect

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_session'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PHOTO_FOLDER'] = 'photos'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PHOTO_FOLDER'], exist_ok=True)

# Global variable to store student data
student_df = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_db', methods=['POST'])
def fetch_db():
    global student_df
    data = request.json
    try:
        conn = psycopg2.connect(
            host=data['host'],
            database=data['database'],
            user=data['user'],
            password=data['password'],
            port=data.get('port', 5432)
        )
        query = f"SELECT * FROM {data['table']}"
        student_df = pd.read_sql(query, conn)
        conn.close()
        student_df = student_df.fillna("")
        columns = student_df.columns.tolist()
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
        return jsonify({"message": f"Photo saved locally to {full_path}"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)
