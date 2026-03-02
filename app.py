from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import pandas as pd
import base64
from io import BytesIO
from PIL import Image
import json

app = Flask(__name__)
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
    
    save_path = data.get('save_path', app.config['PHOTO_FOLDER'])
    # Simple sanitization to prevent saving outside of the base directory if needed
    # but the requirement says "directory choosed by the user", so we'll allow it 
    # but ensure it's at least within a reasonable place or just follow the requirement.
    # For a local tool, we follow the user's choice.
    
    # Ensure the path is not empty and is safe-ish
    if not save_path:
        save_path = app.config['PHOTO_FOLDER']
        
    os.makedirs(save_path, exist_ok=True)
    
    full_path = os.path.join(save_path, filename)
    img.save(full_path)
    
    return jsonify({"message": f"Photo saved to {full_path}"})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)
