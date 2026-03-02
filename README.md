# ID Card Photo Manager

A Flask-based application to import student data from Excel and capture photos via a webcam or phone camera.

## Features
- Import student data from Excel (`.xlsx`, `.xls`).
- Browse student records using Next/Previous navigation buttons.
- Capture photos with a square (adjustable) preview window.
- Set image filenames using a combination of data fields (e.g., ID_Name.jpg).
- Choose a custom directory to save photos.

## Setup Instructions

1. **Install Dependencies:**
   Ensure you have Python installed. Then, run the following command to install required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application:**
   Start the Flask server by running:
   ```bash
   python app.py
   ```

3. **Access the App:**
   Open your browser and go to `http://localhost:5000`.

## Usage
1. Upload your student data Excel file.
2. Configure the preview window size (width and height).
3. Select the fields you want to use for the photo filename (e.g., ID and Name).
4. Specify the directory where you want to save the captured photos.
5. Use the navigation buttons to browse student records.
6. Click "Capture & Save Photo" to save the photo for the current student.
