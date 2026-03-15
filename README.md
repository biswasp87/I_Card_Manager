# ID Card Photo Manager Pro

A comprehensive Flask-based application to manage student data and automate photo capturing for ID cards.

## Features
- **Flexible Data Sources:** Import student data from Excel files or directly from a **PostgreSQL** database.
- **Smart Filename Generation:** Combine multiple data fields (e.g., ID, Name) in a user-defined sequence to generate unique image filenames.
- **Adjustable Camera Preview:** Real-time webcam/phone camera preview with customizable dimensions (square by default).
- **Dual Storage Options:** Save photos to a local server directory or directly to **Google Drive**.
- **Advanced Image Processing:** Supports JPEG/PNG formats with optional **image compression** and target file size (KB) optimization.
- **Student Table View:** A powerful grid view to browse all students, apply up to **4-level filtering and sorting**, and quickly identify records missing photos.
- **Source Syncing:** Automatically save the generated filenames back to the original Excel file or PostgreSQL database.
- **Secure and Fast:** Includes directory traversal protection, SQL injection prevention, and optimized data loading.

## Setup Instructions

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Database Setup (Optional):**
   Ensure your PostgreSQL server is running if you intend to fetch data from a database.

3. **Google Drive Integration (Optional):**
   Place your `client_secrets.json` in the root directory and click "Authorize" in the app settings to link your account.

4. **Run the Application:**
   ```bash
   python app.py
   ```

5. **Access the App:**
   Navigate to `http://localhost:5000` in your web browser.

## Usage
1. **Manage Project:** Use the sidebar to create a new project by uploading an Excel file or connecting to a PostgreSQL database. You can also load existing projects.
2. **Configure Filename:** Select up to 4 fields from the dropdowns to determine the sequence of values in the image filename.
3. **Capture:** Use the "Next/Previous" buttons or the "Student Table View" to select a student, adjust camera settings, and click "Capture & Save". Photos are automatically synced to Google Cloud Storage and BigQuery.
4. **Filters:** In the Table View, use the multi-level selects to filter by specific classes, sections, or missing photos.
