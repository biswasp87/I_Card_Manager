let currentIndex = 0;
let totalRecords = 0;
let columns = [];
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const studentDataDisplay = document.getElementById('studentDataDisplay');
const recordStatus = document.getElementById('recordStatus');
const fieldCheckboxes = document.getElementById('fieldCheckboxes');

// Camera setup
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" }
        });
        video.srcObject = stream;
    } catch (err) {
        console.error("Camera access error:", err);
    }
}

function updatePreviewSize() {
    const w = document.getElementById('previewWidth').value;
    const h = document.getElementById('previewHeight').value;
    video.style.width = w + 'px';
    video.style.height = h + 'px';
    canvas.width = w;
    canvas.height = h;
}

// UI Toggles
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).style.display = 'block';
    event.currentTarget.classList.add('active');
}

function toggleDestination() {
    const dest = document.getElementById('destination').value;
    document.getElementById('localDest').style.display = dest === 'local' ? 'block' : 'none';
    document.getElementById('driveDest').style.display = dest === 'google_drive' ? 'block' : 'none';
}

function toggleCompression() {
    const comp = document.getElementById('compression').value;
    document.getElementById('compressionSettings').style.display = comp === 'compressed' ? 'block' : 'none';
}

// Data Import
async function uploadExcel() {
    const file = document.getElementById('excelFile').files[0];
    if (!file) return alert("Select file");
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/upload', { method: 'POST', body: formData });
    handleImportResponse(await res.json());
}

async function fetchFromDB() {
    const data = {
        host: document.getElementById('dbHost').value || 'localhost',
        database: document.getElementById('dbName').value,
        user: document.getElementById('dbUser').value,
        password: document.getElementById('dbPass').value,
        table: document.getElementById('dbTable').value
    };
    const res = await fetch('/fetch_db', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    handleImportResponse(await res.json());
}

function handleImportResponse(data) {
    if (data.error) return alert(data.error);
    columns = data.columns;
    totalRecords = data.total;
    currentIndex = 0;
    renderFieldCheckboxes();
    fetchRecord(0);
}

// Filename Field Sequencing
function renderFieldCheckboxes() {
    fieldCheckboxes.innerHTML = '';
    columns.forEach(col => {
        const div = document.createElement('div');
        div.className = 'field-item';
        div.innerHTML = `
            <input type="checkbox" name="field" value="${col}" onchange="updateSequenceInputs()">
            <span>${col}</span>
            <input type="number" name="seq" data-field="${col}" class="seq-input" min="1" disabled>
        `;
        fieldCheckboxes.appendChild(div);
    });
}

function updateSequenceInputs() {
    document.querySelectorAll('input[name="field"]').forEach(cb => {
        const seqInput = cb.parentElement.querySelector('.seq-input');
        seqInput.disabled = !cb.checked;
        if (!cb.checked) seqInput.value = '';
    });
}

// Navigation
async function fetchRecord(idx) {
    const res = await fetch(`/data/${idx}`);
    const data = await res.json();
    displayRecord(data);
    recordStatus.innerText = `${idx + 1} / ${totalRecords}`;
}

function displayRecord(data) {
    studentDataDisplay.innerHTML = '';
    for (const [k, v] of Object.entries(data)) {
        const div = document.createElement('div');
        const strong = document.createElement('strong');
        strong.textContent = `${k}:`;
        div.appendChild(strong);
        div.appendChild(document.createTextNode(` ${v}`));
        studentDataDisplay.appendChild(div);
    }
}

function nextRecord() { if (currentIndex < totalRecords - 1) fetchRecord(++currentIndex); }
function prevRecord() { if (currentIndex > 0) fetchRecord(--currentIndex); }

// Capture and Save
async function authorizeDrive() {
    window.open('/authorize', '_blank');
}

async function capturePhoto() {
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const image = canvas.toDataURL('image/jpeg');

    // Filename sequence
    const selected = Array.from(document.querySelectorAll('input[name="field"]:checked'))
        .map(cb => ({
            name: cb.value,
            seq: parseInt(cb.parentElement.querySelector('.seq-input').value) || 99
        }))
        .sort((a, b) => a.seq - b.seq);

    if (selected.length === 0) return alert("Select filename fields");

    const resRecord = await fetch(`/data/${currentIndex}`);
    const student = await resRecord.json();
    let filename = selected.map(s => student[s.name]).join('_') + '.jpg';
    filename = filename.replace(/[^a-z0-9._-]/gi, '_');

    const body = {
        image,
        filename,
        destination: document.getElementById('destination').value,
        save_path: document.getElementById('savePath').value,
        drive_folder_id: document.getElementById('driveFolderId').value,
        compression: document.getElementById('compression').value,
        quality: document.getElementById('imgQuality').value,
        target_size: document.getElementById('targetSize').value
    };

    const res = await fetch('/save_photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const result = await res.json();
    alert(result.message || result.error);
}

window.onload = () => {
    startCamera();
    updatePreviewSize();
};
