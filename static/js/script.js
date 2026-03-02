let currentIndex = 0;
let totalRecords = 0;
let columns = [];
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const studentDataDisplay = document.getElementById('studentDataDisplay');
const recordStatus = document.getElementById('recordStatus');
const fieldCheckboxes = document.getElementById('fieldCheckboxes');
const mainContent = document.getElementById('mainContent');

// Start camera stream
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            video.play();
        };
    } catch (err) {
        console.error("Error accessing camera:", err);
        // alert("Could not access camera. Please check permissions.");
    }
}

// Update preview dimensions
function updatePreviewSize() {
    const width = document.getElementById('previewWidth').value;
    const height = document.getElementById('previewHeight').value;
    video.style.width = width + 'px';
    video.style.height = height + 'px';
    canvas.width = width;
    canvas.height = height;
}

// Excel upload handler
async function uploadExcel() {
    const fileInput = document.getElementById('excelFile');
    if (fileInput.files.length === 0) {
        alert("Please select a file first.");
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.error) {
            alert(data.error);
        } else {
            columns = data.columns;
            totalRecords = data.total;
            currentIndex = 0;
            renderFieldCheckboxes();
            await fetchRecord(currentIndex);
            mainContent.style.display = 'block';
        }
    } catch (err) {
        console.error("Error uploading file:", err);
    }
}

// Render checkboxes for filename fields
function renderFieldCheckboxes() {
    fieldCheckboxes.innerHTML = '<strong>Filename Fields:</strong><br>';
    columns.forEach(col => {
        const label = document.createElement('label');
        label.innerHTML = `<input type="checkbox" name="filenameField" value="${col}"> ${col} `;
        fieldCheckboxes.appendChild(label);
    });
}

// Fetch a single record
async function fetchRecord(index) {
    try {
        const response = await fetch(`/data/${index}`);
        const data = await response.json();
        if (data.error) {
            alert(data.error);
        } else {
            displayRecord(data);
            recordStatus.innerText = `${index + 1} / ${totalRecords}`;
        }
    } catch (err) {
        console.error("Error fetching record:", err);
    }
}

// Display record data in UI
function displayRecord(data) {
    studentDataDisplay.innerHTML = '';
    for (const [key, value] of Object.entries(data)) {
        const item = document.createElement('div');
        item.innerHTML = `<strong>${key}:</strong> ${value}`;
        studentDataDisplay.appendChild(item);
    }
}

// Navigation functions
async function nextRecord() {
    if (currentIndex < totalRecords - 1) {
        currentIndex++;
        await fetchRecord(currentIndex);
    }
}

async function prevRecord() {
    if (currentIndex > 0) {
        currentIndex--;
        await fetchRecord(currentIndex);
    }
}

// Capture and save photo
async function capturePhoto() {
    const context = canvas.getContext('2d');
    const width = document.getElementById('previewWidth').value;
    const height = document.getElementById('previewHeight').value;

    // Draw current frame to canvas
    context.drawImage(video, 0, 0, width, height);
    const imageData = canvas.toDataURL('image/jpeg');

    // Generate filename from selected fields
    const selectedFields = Array.from(document.querySelectorAll('input[name="filenameField"]:checked'))
        .map(cb => cb.value);

    if (selectedFields.length === 0) {
        alert("Please select at least one field for the filename.");
        return;
    }

    // Get the current student data to construct the name
    try {
        const response = await fetch(`/data/${currentIndex}`);
        const student = await response.json();

        let filename = selectedFields.map(field => student[field]).join('_') + '.jpg';
        // Basic sanitization: replace spaces and special chars
        filename = filename.replace(/[^a-z0-9._-]/gi, '_');

        const savePath = document.getElementById('savePath').value;

        const saveResponse = await fetch('/save_photo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: imageData,
                filename: filename,
                save_path: savePath
            })
        });

        const result = await saveResponse.json();
        alert(result.message || result.error);
    } catch (err) {
        console.error("Error saving photo:", err);
    }
}

// Initial setup
window.onload = () => {
    startCamera();
    updatePreviewSize();
};
