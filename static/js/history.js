// --- Helper Functions ---
function showAlert(title, message) {
    const existing = document.querySelector('.alert');
    if (existing) existing.remove();

    const alertEl = document.createElement('div');
    alertEl.className = 'alert';

    const titleEl = document.createElement('div');
    titleEl.className = 'alert-title';
    titleEl.textContent = title || '';

    const msgEl = document.createElement('div');
    msgEl.className = 'alert-message';
    msgEl.textContent = message || '';

    const btn = document.createElement('button');
    btn.className = 'alert-btn';
    btn.textContent = 'OK';
    btn.addEventListener('click', () => alertEl.remove());

    alertEl.appendChild(titleEl);
    alertEl.appendChild(msgEl);
    alertEl.appendChild(btn);
    document.body.appendChild(alertEl);
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

let currentTrackingMac = null;
let trackingLogInterval = null;

function trackDevice(deviceMac) {
    currentTrackingMac = deviceMac;
    document.getElementById('trackingMacLabel').textContent = deviceMac;
    document.getElementById('trackingLogs').value = '';
    document.getElementById('trackingChannels').value = '1,2,3,6,10';

    // Sync button states with current tracking status
    fetch('/tracker/status-tracking/')
        .then(r => r.json())
        .then(data => {
            document.getElementById('startTrackingBtn').disabled = data.running;
            document.getElementById('stopTrackingBtn').disabled = !data.running;
            if (data.running) startTrackingLogPoll();
        })
        .catch(() => {
            document.getElementById('startTrackingBtn').disabled = false;
            document.getElementById('stopTrackingBtn').disabled = true;
        });

    document.getElementById('trackingPopup').style.display = 'flex';
}

function closeTrackingPopup() {
    document.getElementById('trackingPopup').style.display = 'none';
    stopTrackingLogPoll();
}

function startTracking() {
    const channels = document.getElementById('trackingChannels').value.trim() || '1,2,3,6,10';

    fetch('/tracker/start-tracking/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ mac: currentTrackingMac, channels })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('trackingLogs').value = `Started: ${data.message}\n`;
            document.getElementById('startTrackingBtn').disabled = true;
            document.getElementById('stopTrackingBtn').disabled = false;
            startTrackingLogPoll();
        } else {
            showAlert('Error', data.message || 'Failed to start tracker.');
        }
    })
    .catch(() => showAlert('Error', 'Could not connect to server.'));
}

function stopTracking() {
    fetch('/tracker/stop-tracking/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') }
    })
    .then(r => r.json())
    .then(data => {
        stopTrackingLogPoll();
        document.getElementById('startTrackingBtn').disabled = false;
        document.getElementById('stopTrackingBtn').disabled = true;
        if (data.status !== 'success') showAlert('Error', data.message || 'Failed to stop tracker.');
    })
    .catch(() => showAlert('Error', 'Could not connect to server.'));
}

function startTrackingLogPoll() {
    const logBox = document.getElementById('trackingLogs');
    const indicator = document.getElementById('trackingLogIndicator');
    stopTrackingLogPoll();
    if (indicator) indicator.style.background = '#0f0';
    trackingLogInterval = setInterval(() => {
        fetch('/tracker/tracking-logs/')
            .then(r => r.json())
            .then(data => {
                if (data.logs) {
                    logBox.value = data.logs.join('\n');
                    logBox.scrollTop = logBox.scrollHeight;
                }
            })
            .catch(() => {});
    }, 2000);
}

function stopTrackingLogPoll() {
    if (trackingLogInterval) {
        clearInterval(trackingLogInterval);
        trackingLogInterval = null;
    }
    const indicator = document.getElementById('trackingLogIndicator');
    if (indicator) indicator.style.background = '';
}

// --- Render Wi-Fi Table ---
function renderWiFiData(wifiData, tbody) {
    if (!wifiData || typeof wifiData !== 'object' || Object.keys(wifiData).length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">No mapped WiFi data.</td></tr>';
        return;
    }

    let html = '';

    for (const [ssid, apData] of Object.entries(wifiData)) {
        for (const [apMac, apDetails] of Object.entries(apData)) {

            const devices = apDetails.devices || {};
            const deviceCount = Object.keys(devices).length;
            const rowSpan = deviceCount > 0 ? deviceCount : 1;

            const apSignal = apDetails.signal ? `${apDetails.signal} dBm` : 'N/A';
            const apBytes = (apDetails.bytes !== undefined && apDetails.bytes !== null) ? apDetails.bytes : '-';

            let apChannel = 'N/A';
            if (Array.isArray(apDetails.channels) && apDetails.channels.length > 0) {
                apChannel = apDetails.channels.join(', ');
            } else if (apDetails.channel !== undefined) {
                apChannel = apDetails.channel;
            }

            const displayName = ssid === '~unassociated_devices' ? 'Unassociated Clients' : ssid;

            html += `<tr>
                <td rowspan="${rowSpan}"><strong>${displayName}</strong><br><small>${apMac}</small></td>
                <td rowspan="${rowSpan}">${apSignal}</td>
                <td rowspan="${rowSpan}">${apChannel}</td>
                <td rowspan="${rowSpan}">${apBytes}</td>`;

            if (deviceCount > 0) {
                let firstDevice = true;
                for (const [devMac, devDetails] of Object.entries(devices)) {
                    const devSignal = devDetails.signal ? `${devDetails.signal} dBm` : 'N/A';
                    const devBytes = (devDetails.bytes !== undefined && devDetails.bytes !== null) ? devDetails.bytes : '-';

                    if (!firstDevice) {
                        html += `<tr>`;
                    }

                    html += `
                        <td>${devMac}</td>
                        <td>${devSignal}</td>
                        <td>${devBytes}</td>
                        <td class="action-cell">
                            <button onclick="trackDevice('${devMac}')" title="Track Device">
                                <img src="/static/images/icon_track.png" class="icon-pixel" alt="Track">
                            </button>
                        </td>
                    </tr>`;

                    firstDevice = false;
                }
            } else {
                html += `
                    <td>-</td>
                    <td>-</td>
                    <td>-</td>
                    <td class="action-cell">-</td>
                </tr>`;
            }
        }
    }

    tbody.innerHTML = html;
}

// --- Load File Data ---
function loadHistoryFile(filename) {
    const tbody = document.getElementById('wifi-table-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Loading...</td></tr>';

    fetch(`wifi-data/?file=${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                renderWiFiData(data.data, tbody);
            } else {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;">Error: ${data.message}</td></tr>`;
            }
        })
        .catch(() => {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Error loading data.</td></tr>';
        });
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', function () {
    const fileSelector = document.getElementById('scanSelector');
    if (!fileSelector) return;

    fileSelector.addEventListener('change', function () {
        const selected = this.options[this.selectedIndex];
        if (!selected || selected.disabled) return;

        const selectedInput = document.getElementById('selectedFile');
        if (selectedInput) selectedInput.value = selected.text;

        loadHistoryFile(selected.value);
    });

    // Auto-select the first file
    if (fileSelector.options.length > 0) {
        fileSelector.selectedIndex = 0;
        fileSelector.dispatchEvent(new Event('change'));
    }
});
