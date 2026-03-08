let currentIndex = 0;
let totalRecords = 0;
let columns = [];
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const studentDataDisplay = document.getElementById('studentDataDisplay');
const recordStatus = document.getElementById('recordStatus');
const fieldCheckboxes = document.getElementById('fieldCheckboxes');
const tableHeader = document.getElementById('tableHeader');
const tableBody = document.getElementById('tableBody');
const tableFieldCheckboxes = document.getElementById('tableFieldCheckboxes');
const updateColumnSelect = document.getElementById('updateColumn');

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
    document.querySelectorAll('.sidebar .tab-content').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.sidebar .tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).style.display = 'block';
    event.currentTarget.classList.add('active');
}

function showMainTab(tabId) {
    document.getElementById('configView').style.display = tabId === 'configView' ? 'grid' : 'none';
    const tableEl = document.getElementById('tableView');
    tableEl.style.display = tabId === 'tableView' ? 'block' : 'none';
    tableEl.dataset.active = tabId === 'tableView' ? 'true' : 'false';

    // Manage tab active state
    document.querySelectorAll('.main-tabs .tab-btn').forEach(b => {
        b.classList.toggle('active', b.getAttribute('onclick').includes(tabId));
    });

    if (tabId === 'tableView') renderTableView();
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

function updatePath(input) {
    if (input.files.length > 0) {
        // webkitRelativePath gives 'folder/file.txt', we want the folder
        const path = input.files[0].webkitRelativePath.split('/')[0];
        document.getElementById('savePath').value = path;
    }
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
    renderTableFieldCheckboxes();
    populateUpdateColumn();
    fetchRecord(0);
}

function populateUpdateColumn() {
    updateColumnSelect.innerHTML = '<option value="">(Don\'t Save to Source)</option>';
    columns.forEach(col => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = col;
        updateColumnSelect.appendChild(opt);
    });
}

function renderTableFieldCheckboxes() {
    tableFieldCheckboxes.innerHTML = '';
    columns.forEach(col => {
        const div = document.createElement('div');
        div.className = 'field-item';
        div.innerHTML = `
            <input type="checkbox" name="tableField" value="${col}" onchange="renderTableView()">
            <span>${col}</span>
        `;
        tableFieldCheckboxes.appendChild(div);
    });
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

let allData = []; // Store all student records locally for table view
async function fetchAllData() {
    const records = [];
    for(let i=0; i<totalRecords; i++) {
        const res = await fetch(`/data/${i}`);
        records.push(await res.json());
    }
    allData = records;
}

async function renderTableView() {
    await fetchAllData();
    const selected = Array.from(document.querySelectorAll('input[name="tableField"]:checked'))
        .map(cb => cb.value)
        .slice(0, 4);

    // Update headers
    tableHeader.innerHTML = '<th>Image</th>';
    selected.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        th.style.cursor = 'pointer';
        th.onclick = () => sortTable(col);
        tableHeader.appendChild(th);
    });

    renderTableRows(allData, selected);
}

function renderTableRows(data, selected) {
    tableBody.innerHTML = '';
    data.forEach((student, idx) => {
        const tr = document.createElement('tr');

        // Image cell
        const imgTd = document.createElement('td');
        const img = document.createElement('img');

        // Find if a Photo/Image column has a value
        const photoCol = columns.find(c => c.toLowerCase().includes('photo') || c.toLowerCase().includes('image'));
        const photoFilename = photoCol ? student[photoCol] : null;

        img.src = photoFilename ? `/get_image/${photoFilename}` : '/static/images/placeholder.jpg';
        img.style.width = '60px';
        img.style.height = '60px';
        img.style.objectFit = 'cover';
        img.style.cursor = 'pointer';
        img.onerror = () => { img.src = '/static/images/placeholder.jpg'; };
        img.onclick = () => goToCapture(idx);
        imgTd.appendChild(img);
        tr.appendChild(imgTd);

        selected.forEach(col => {
            const td = document.createElement('td');
            td.textContent = student[col];
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });
}

function filterTable() {
    const val = document.getElementById('tableFilter').value.toLowerCase();
    const selected = Array.from(document.querySelectorAll('input[name="tableField"]:checked'))
        .map(cb => cb.value)
        .slice(0, 4);

    const filtered = allData.filter(s =>
        Object.values(s).some(v => String(v).toLowerCase().includes(val))
    );
    renderTableRows(filtered, selected);
}

let sortDir = 1;
function sortTable(col) {
    sortDir *= -1;
    const selected = Array.from(document.querySelectorAll('input[name="tableField"]:checked'))
        .map(cb => cb.value)
        .slice(0, 4);

    allData.sort((a, b) => {
        if (a[col] < b[col]) return -1 * sortDir;
        if (a[col] > b[col]) return 1 * sortDir;
        return 0;
    });
    renderTableRows(allData, selected);
}

function goToCapture(idx) {
    currentIndex = idx;
    fetchRecord(currentIndex);
    window.fromTable = true;
    showMainTab('configView');
}

// Capture and Save
async function authorizeDrive() {
    window.open('/authorize', '_blank');
}

async function capturePhoto() {
    console.log("CapturePhoto called");
    const ctx = canvas.getContext('2d');
    try {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    } catch (e) {
        console.warn("Canvas draw error (possibly no video stream):", e);
        // Just draw a colored rectangle for testing if video fails
        ctx.fillStyle = "blue";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
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

    try {
        const res = await fetch('/save_photo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...body,
                index: currentIndex,
                update_column: document.getElementById('updateColumn').value
            })
        });
        const result = await res.json();
        console.log("Save result:", result);
        alert(result.message || result.error);

        // If we were previously on Table View, navigate back
        if (window.fromTable) {
            console.log("Returning to table view");
            window.fromTable = false;
            showMainTab('tableView');
        }
    } catch (err) {
        console.error("Save photo error:", err);
        alert("Error saving photo.");
    }
}

window.onload = () => {
    startCamera();
    updatePreviewSize();
};
