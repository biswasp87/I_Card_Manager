let currentIndex = 0;
let totalRecords = 0;
let columns = [];
let allData = []; // Store all student records locally
let windowFromTable = false;

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const studentDataDisplay = document.getElementById('studentDataDisplay');
const recordStatus = document.getElementById('recordStatus');
const fieldCheckboxes = document.getElementById('fieldCheckboxes');
const tableHeader = document.getElementById('tableHeader');
const tableBody = document.getElementById('tableBody');
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

    document.querySelectorAll('.main-tabs .tab-btn').forEach(b => {
        b.classList.toggle('active', b.getAttribute('onclick').includes(tabId));
    });
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

async function browseFolder(base = '') {
    const res = await fetch(`/list_dirs?base=${encodeURIComponent(base)}`);
    const data = await res.json();
    if (data.error) return alert(data.error);

    let modal = document.getElementById('dirModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dirModal';
        modal.className = 'modal';
        document.body.appendChild(modal);
    }
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content card">
            <h3>Select Folder</h3>
            <p><strong>Current:</strong> ${data.current}</p>
            <div class="dir-list" style="max-height: 300px; overflow-y: auto; margin-bottom: 1rem;">
                <div class="dir-item" onclick="browseFolder('${data.parent}')">📁 .. [Up]</div>
                ${data.dirs.map(d => `<div class="dir-item" onclick="browseFolder('${data.current}/${d}')">📁 ${d}</div>`).join('')}
            </div>
            <div style="display: flex; gap: 10px;">
                <button class="primary-btn" onclick="confirmDir('${data.current}')">Select This Folder</button>
                <button class="secondary-btn" onclick="document.getElementById('dirModal').style.display='none'">Cancel</button>
            </div>
        </div>
    `;
}

function confirmDir(path) {
    document.getElementById('savePath').value = path;
    document.getElementById('dirModal').style.display = 'none';
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
    renderFilterRows();
    populateUpdateColumn();
    fetchAllData().then(() => fetchRecord(0));
}

function populateUpdateColumn() {
    updateColumnSelect.innerHTML = '<option value="">(Don\'t Save to Source)</option>';
    columns.forEach(col => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = col;
        updateColumnSelect.appendChild(opt);
    });
}

function renderFilterRows() {
    for (let i = 1; i <= 4; i++) {
        const row = document.getElementById(`filterRow${i}`);
        row.innerHTML = `
            <div class="filter-row-item">
                <select id="fieldSelect${i}" onchange="updateUniqueValues(${i})">
                    <option value="">Select Field ${i}</option>
                    ${columns.map(c => `<option value="${c}">${c}</option>`).join('')}
                </select>
                <select id="valueSelect${i}">
                    <option value="">All Values</option>
                </select>
                <select id="sortSelect${i}">
                    <option value="">No Sort</option>
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                </select>
            </div>
        `;
    }
}

async function updateUniqueValues(rowIdx) {
    const field = document.getElementById(`fieldSelect${rowIdx}`).value;
    const valSelect = document.getElementById(`valueSelect${rowIdx}`);
    valSelect.innerHTML = '<option value="">All Values</option>';

    if (!field) return;

    const uniqueVals = [...new Set(allData.map(s => s[field]))].filter(v => v !== null && v !== "");
    uniqueVals.forEach(v => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = v;
        valSelect.appendChild(opt);
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
    if (idx < 0 || idx >= totalRecords) return;
    const res = await fetch(`/data/${idx}`);
    const data = await res.json();
    displayRecord(data);
    recordStatus.innerText = `${idx + 1} / ${totalRecords}`;
    currentIndex = idx;
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

async function applyRecordFilter() {
    const filterPending = document.getElementById('imagePendingFilter').checked;
    if (filterPending) {
        const photoCol = columns.find(c => c.toLowerCase().includes('photo') || c.toLowerCase().includes('image'));
        if (photoCol) {
            let found = false;
            for (let i = currentIndex; i < totalRecords; i++) {
                if (!allData[i][photoCol]) {
                    currentIndex = i;
                    found = true;
                    break;
                }
            }
            if (!found) {
                 for (let i = 0; i < currentIndex; i++) {
                    if (!allData[i][photoCol]) {
                        currentIndex = i;
                        found = true;
                        break;
                    }
                }
            }
            if (!found) alert("No more pending images found.");
        }
    }
    fetchRecord(currentIndex);
}

function nextRecord() {
    if (currentIndex < totalRecords - 1) {
        currentIndex++;
        if (document.getElementById('imagePendingFilter').checked) applyRecordFilter();
        else fetchRecord(currentIndex);
    }
}

function prevRecord() {
    if (currentIndex > 0) {
        currentIndex--;
        if (document.getElementById('imagePendingFilter').checked) applyRecordFilter();
        else fetchRecord(currentIndex);
    }
}

async function fetchAllData() {
    const res = await fetch('/data/all');
    allData = await res.json();
}

async function generateTable() {
    let displayData = [...allData];
    const selectedCols = [];

    for (let i = 1; i <= 4; i++) {
        const field = document.getElementById(`fieldSelect${i}`).value;
        const value = document.getElementById(`valueSelect${i}`).value;
        const sort = document.getElementById(`sortSelect${i}`).value;

        if (field) {
            selectedCols.push(field);
            if (value) {
                displayData = displayData.filter(s => String(s[field]) === value);
            }
            if (sort) {
                displayData.sort((a, b) => {
                    if (a[field] < b[field]) return sort === 'asc' ? -1 : 1;
                    if (a[field] > b[field]) return sort === 'asc' ? 1 : -1;
                    return 0;
                });
            }
        }
    }

    tableHeader.innerHTML = '<th>Image</th>';
    selectedCols.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        tableHeader.appendChild(th);
    });

    renderTableRows(displayData, selectedCols);
}

function renderTableRows(data, selected) {
    tableBody.innerHTML = '';
    const customSavePath = document.getElementById('savePath').value;

    data.forEach((student) => {
        const realIdx = allData.findIndex(s => JSON.stringify(s) === JSON.stringify(student));
        const tr = document.createElement('tr');

        const imgTd = document.createElement('td');
        const img = document.createElement('img');

        const photoCol = columns.find(c => c.toLowerCase().includes('photo') || c.toLowerCase().includes('image'));
        const photoFilename = photoCol ? student[photoCol] : null;

        let imgSrc = '/static/images/placeholder.jpg';
        if (photoFilename) {
            imgSrc = `/get_image/${photoFilename}?path=${encodeURIComponent(customSavePath)}`;
        }

        img.src = imgSrc;
        img.style.width = '60px';
        img.style.height = '60px';
        img.style.objectFit = 'cover';
        img.style.cursor = 'pointer';
        img.onerror = () => { img.src = '/static/images/placeholder.jpg'; };
        img.onclick = () => goToCapture(realIdx);
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

function goToCapture(idx) {
    currentIndex = idx;
    fetchRecord(currentIndex);
    windowFromTable = true;
    showMainTab('configView');
}

// Capture and Save
async function authorizeDrive() {
    window.open('/authorize', '_blank');
}

async function capturePhoto() {
    const ctx = canvas.getContext('2d');
    try {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    } catch (e) {
        ctx.fillStyle = "blue";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    const image = canvas.toDataURL('image/jpeg');

    const selected = Array.from(document.querySelectorAll('input[name="field"]:checked'))
        .map(cb => ({
            name: cb.value,
            seq: parseInt(cb.parentElement.querySelector('.seq-input').value) || 99
        }))
        .sort((a, b) => a.seq - b.seq);

    if (selected.length === 0) return alert("Select filename fields");

    const student = allData[currentIndex];
    let filename = selected.map(s => student[s.name]).join('_');
    filename = filename.replace(/[^a-z0-9._-]/gi, '_');

    const body = {
        image,
        filename,
        format: document.getElementById('imgFormat').value,
        destination: document.getElementById('destination').value,
        save_path: document.getElementById('savePath').value,
        drive_folder_id: document.getElementById('driveFolderId').value,
        compression: document.getElementById('compression').value,
        quality: document.getElementById('imgQuality').value,
        target_size: document.getElementById('targetSize').value,
        index: currentIndex,
        update_column: document.getElementById('updateColumn').value
    };

    try {
        const res = await fetch('/save_photo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const result = await res.json();
        alert(result.message || result.error);

        if (windowFromTable) {
            windowFromTable = false;
            showMainTab('tableView');
            generateTable(); // Refresh table
        }
    } catch (err) {
        console.error("Save photo error:", err);
    }
}

window.onload = () => {
    startCamera();
    updatePreviewSize();
};
