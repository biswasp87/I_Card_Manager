import unittest
import os
import pandas as pd
from app import app
import shutil
import base64
from io import BytesIO
from PIL import Image

class IDCardAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.secret_key = 'test'
        self.test_dir = os.path.abspath('test_env')
        self.upload_dir = os.path.join(self.test_dir, 'uploads')
        self.photo_dir = os.path.join(self.test_dir, 'photos')

        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.photo_dir, exist_ok=True)

        app.config['UPLOAD_FOLDER'] = self.upload_dir
        app.config['PHOTO_FOLDER'] = self.photo_dir

        self.client = app.test_client()

        df = pd.DataFrame({'ID': ['S001'], 'Name': ['Alice'], 'Photo': ['']})
        self.excel_path = os.path.join(self.test_dir, 'sample.xlsx')
        df.to_excel(self.excel_path, index=False)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_upload(self):
        with open(self.excel_path, 'rb') as f:
            response = self.client.post('/upload', data={'file': f}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)

    def test_save_photo_and_update_excel(self):
        # Upload
        with open(self.excel_path, 'rb') as f:
            self.client.post('/upload', data={'file': f}, content_type='multipart/form-data')

        img = Image.new('RGB', (10, 10), color='white')
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        b64_img = "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode()

        response = self.client.post('/save_photo', json={
            'image': b64_img,
            'filename': 'S001.jpg',
            'save_path': self.photo_dir,
            'destination': 'local',
            'compression': 'original',
            'index': 0,
            'update_column': 'Photo'
        })
        self.assertEqual(response.status_code, 200)

        # Verify Excel updated
        df = pd.read_excel(self.excel_path)
        self.assertEqual(df.iloc[0]['Photo'], 'S001.jpg')

if __name__ == '__main__':
    unittest.main()
