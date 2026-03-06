// --- Core Helper Functions ---
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

// --- Polling Logic ---
let wifiPollingInterval = null;
let trackerRunning = false;

function startWiFiPolling() {
    // Prevent starting multiple intervals
    if (!wifiPollingInterval) {
        fetchWiFiData(); // Fetch immediately on start
        wifiPollingInterval = setInterval(fetchWiFiData, 5000); // Then fetch every 5 seconds
    }
}

function stopWiFiPolling() {
    if (wifiPollingInterval) {
        clearInterval(wifiPollingInterval);
        wifiPollingInterval = null;
    }
}

// --- Fetch and Render Data ---
function fetchWiFiData() {
    fetch('wifi-map/')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('wifi-table-body');
            if (!tbody) return;

            if (data.status === 'success') {
                if (data.data && typeof data.data === 'object') {
                    renderWiFiData(data.data, tbody);
                } else {
                    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">No WiFi data available.</td></tr>';
                }
            } else if (data.status === 'waiting') {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Waiting for trackerjacker to map devices...</td></tr>';
            }
        })
        .catch(error => console.error('Error fetching WiFi data:', error));
}

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

            // Start the AP Row
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
                        html += `<tr>`; // New row for subsequent devices
                    }
                    
                    html += `
                        <td>${devMac}</td>
                        <td>${devSignal}</td>
                        <td>${devBytes}</td>
                    `;
                    
                    html += `</tr>`;
                    firstDevice = false;
                }
            } else {
                // AP with no devices
                html += `
                    <td>-</td>
                    <td>-</td>
                    <td>-</td>
                </tr>`;
            }
        }
    }

    tbody.innerHTML = html;
}

function trackDevice(deviceMac) {
    if (trackerRunning) {
        showAlert('Tracker Active', 'Stop scanner before tracking a device.');
        return;
    }
    console.log("Tracking Device:", deviceMac);
    // Use fetch() to send this to a Django URL
    // Example: fetch(`/api/track-device/${deviceMac}/`)
}

// --- Start/Stop Scanners ---
function activateTracker() {
    const startBtn = document.getElementById('activateTracker');
    const stopBtn = document.getElementById('deactivateTracker');

    startBtn.disabled = true;

    fetch('start-scan/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showAlert('Scanner', data.message);
                if (stopBtn) stopBtn.disabled = false;
                updateButtonsBasedOnStatus();
            } else {
                showAlert('Error', 'Error: ' + data.message);
                startBtn.disabled = false;
            }
        })
        .catch(error => {
            showAlert('Error', 'An unexpected error occurred: ' + error);
            startBtn.disabled = false;
        });
}

function deactivateTracker() {
    const startBtn = document.getElementById('activateTracker');
    const stopBtn = document.getElementById('deactivateTracker');

    if (stopBtn) stopBtn.disabled = true;

    fetch('stop-scan/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showAlert('Scanner', data.message);
                if (startBtn) startBtn.disabled = false;
                updateButtonsBasedOnStatus();
            } else {
                showAlert('Error', 'Error: ' + data.message);
                if (stopBtn) stopBtn.disabled = false;
            }
        })
        .catch(error => {
            showAlert('Error', 'An unexpected error occurred: ' + error);
            if (stopBtn) stopBtn.disabled = false;
        });
}

// --- Check Status ---
function updateButtonsBasedOnStatus() {
    const startBtn = document.getElementById('activateTracker');
    const stopBtn = document.getElementById('deactivateTracker');

    fetch('status-scan/')
        .then(resp => resp.json())
        .then(data => {
            const running = !!data.running;
            trackerRunning = running;
            if (startBtn) startBtn.disabled = running;
            if (stopBtn) stopBtn.disabled = !running;

            // Start or stop the auto-refreshing table based on status
            if (running) {
                startWiFiPolling();
            } else {
                stopWiFiPolling();
            }
        })
        .catch(err => {
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
            stopWiFiPolling();
        });
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', function() {
    const startEl = document.getElementById('activateTracker');
    if (startEl) startEl.addEventListener('click', activateTracker);

    const stopEl = document.getElementById('deactivateTracker');
    if (stopEl) stopEl.addEventListener('click', deactivateTracker);

    updateButtonsBasedOnStatus();
});