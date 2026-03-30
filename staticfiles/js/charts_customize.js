/* =============================================================
   AirscopeGuardian – Charts Dashboard
   Endpoints used:
     GET /api/assets/stats/
     GET /api/assets/by-type/
     GET /api/assets/channel-usage/
     GET /api/assets/vendor-distribution/
     GET /api/assets/encryption-breakdown/
     GET /api/assets/?page_size=1000          (radar)
     GET /api/assets/client-ap-map/           (graph)
     GET /api/events/summary/
     GET /api/messages/recent/           (system messages)
   Auto-refresh: every 10s
   ============================================================= */

const RETRO_FONT = '"Press Start 2P", system-ui, sans-serif';
const COLORS = [
  "#3366CC", "#DC3912", "#FF9900", "#109618",
  "#990099", "#3B3EAC", "#0099C6", "#DD4477",
  "#66AA00", "#B82E2E", "#316395", "#994499",
  "#22AA99", "#AAAA11", "#6633CC"
];

const chartInstances = {};

function mkChart(id, config) {
  if (chartInstances[id]) chartInstances[id].destroy();
  const ctx = document.getElementById(id);
  if (!ctx) return;
  config.options = config.options || {};
  // Disable animations on chart creation/updates for instant refreshes
  config.options.animation = false;
  chartInstances[id] = new Chart(ctx.getContext('2d'), config);
}

function retroPlugin(titleText) {
  return {
    legend: { position: 'bottom', labels: { font: { family: RETRO_FONT, size: 7 } } },
    title: { display: !!titleText, text: titleText, color: 'black', font: { family: RETRO_FONT, size: 10 } },
    tooltip: { backgroundColor: '#222', titleFont: { family: RETRO_FONT, size: 9 }, bodyFont: { family: RETRO_FONT, size: 7 }, padding: 8 }
  };
}

// ── Stats Cards ────────────────────────────────────────────────
async function loadStats() {
  try {
    const data = await (await fetch('/api/assets/stats/')).json();
    document.getElementById('stat-total').textContent       = data.total_assets  ?? '—';
    document.getElementById('stat-aps').textContent         = data.access_points ?? '—';
    document.getElementById('stat-clients').textContent     = data.clients       ?? '—';
    document.getElementById('stat-signal').innerHTML        = (data.avg_signal ?? '—') + '<span>dBm</span>';
    document.getElementById('stat-whitelisted').textContent = data.whitelisted   ?? '—';
  } catch (e) { console.error('Stats error', e); }
}

// ── Asset Type Pie ─────────────────────────────────────────────
async function loadByType() {
  try {
    const json = await (await fetch('/api/assets/by-type/')).json();
    mkChart('chartAssetType', {
      type: 'pie',
      data: { labels: json.map(d => d.asset_type), datasets: [{ data: json.map(d => d.count), backgroundColor: COLORS, borderColor: '#000', borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: retroPlugin('Asset Types') }
    });
  } catch (e) { console.error('By-type error', e); }
}

// ── Channel Usage Bar ──────────────────────────────────────────
async function loadChannels() {
  try {
    const json = await (await fetch('/api/assets/channel-usage/')).json();
    const values = json.map(d => d.count);
    mkChart('chartChannels', {
      type: 'bar',
      data: { labels: json.map(d => `CH ${d.operating_channel}`), datasets: [{ label: 'Devices', data: values, backgroundColor: values.map((_, i) => COLORS[i % COLORS.length]), borderColor: '#000', borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, scales: { x: { ticks: { font: { family: RETRO_FONT, size: 7 } } }, y: { beginAtZero: true, ticks: { font: { family: RETRO_FONT, size: 7 } } } }, plugins: retroPlugin('Channel Usage') }
    });
  } catch (e) { console.error('Channel error', e); }
}

// ── Vendor Distribution Bar ────────────────────────────────────
async function loadVendors() {
  try {
    const json = await (await fetch('/api/assets/vendor-distribution/')).json();
    const values = json.map(d => d.count);
    mkChart('chartVendors', {
      type: 'bar',
      data: { labels: json.map(d => d.vendor_oui || 'Unknown'), datasets: [{ label: 'Devices', data: values, backgroundColor: values.map((_, i) => COLORS[i % COLORS.length]), borderColor: '#000', borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', scales: { x: { beginAtZero: true, ticks: { font: { family: RETRO_FONT, size: 7 } } }, y: { ticks: { font: { family: RETRO_FONT, size: 7 } } } }, plugins: retroPlugin('Top Vendors') }
    });
  } catch (e) { console.error('Vendor error', e); }
}

// ── Encryption Pie ─────────────────────────────────────────────
async function loadEncryption() {
  try {
    const d = await (await fetch('/api/assets/encryption-breakdown/')).json();
    mkChart('chartEncryption', {
      type: 'pie',
      data: { labels: ['Encrypted', 'Open'], datasets: [{ data: [d.encrypted, d.unencrypted], backgroundColor: [COLORS[3], COLORS[1]], borderColor: '#000', borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: retroPlugin('Encryption') }
    });
  } catch (e) { console.error('Encryption error', e); }
}

// ── Security Events Severity Doughnut ─────────────────────────
async function loadEventSeverity() {
  try {
    const d = await (await fetch('/api/events/summary/')).json();
    mkChart('chartSeverity', {
      type: 'doughnut',
      data: { labels: d.by_severity.map(x => x.severity), datasets: [{ data: d.by_severity.map(x => x.count), backgroundColor: COLORS, borderColor: '#000', borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: retroPlugin('Events by Severity') }
    });
  } catch (e) { console.error('Event severity error', e); }
}

// =============================================================
// ── Tactical Signal Radar (RSSI-based, no GPS required) ──────
// APs are placed by estimated_radius_meters as distance from
// center. Angle is derived deterministically from the MAC so
// positions are stable across refreshes.
// =============================================================
const _radarCanvas = document.getElementById('radarCanvas');
const _radarCtx    = _radarCanvas ? _radarCanvas.getContext('2d') : null;
const RADAR_SIZE   = 450;
if (_radarCanvas) { _radarCanvas.width = RADAR_SIZE; _radarCanvas.height = RADAR_SIZE; }

let radarAPsData      = [];
let radarMaxRange     = 10;  // metres (from range selector)
let radarHoveredAP    = null;
let radarRenderedPts  = [];

// Stable angle derived from MAC so APs don't jump every refresh
function _macAngle(mac) {
  let h = 0;
  for (const c of (mac || '')) h = (Math.imul(h, 31) + c.charCodeAt(0)) | 0;
  return ((h >>> 0) / 0xffffffff) * 2 * Math.PI;
}

function drawRadar() {
  if (!_radarCtx) return;
  const cx = RADAR_SIZE / 2, cy = RADAR_SIZE / 2, r = RADAR_SIZE / 2 - 20;
  _radarCtx.clearRect(0, 0, RADAR_SIZE, RADAR_SIZE);
  _radarCtx.fillStyle = '#ffffff';
  _radarCtx.fillRect(0, 0, RADAR_SIZE, RADAR_SIZE);
  radarRenderedPts = [];

  // Concentric range rings
  _radarCtx.strokeStyle = 'rgba(0,0,0,0.25)';
  _radarCtx.lineWidth = 1.5;
  for (let i = 1; i <= 5; i++) {
    _radarCtx.beginPath();
    _radarCtx.arc(cx, cy, (r / 5) * i, 0, Math.PI * 2);
    _radarCtx.stroke();
    _radarCtx.fillStyle = '#888';
    _radarCtx.font = '9px monospace';
    _radarCtx.fillText(Math.round((radarMaxRange / 5) * i) + 'm', cx + 4, cy - (r / 5) * i + 10);
  }
  // Cross-hairs
  _radarCtx.beginPath();
  _radarCtx.moveTo(cx, cy - r); _radarCtx.lineTo(cx, cy + r);
  _radarCtx.moveTo(cx - r, cy); _radarCtx.lineTo(cx + r, cy);
  _radarCtx.stroke();
  // Observer
  _radarCtx.beginPath();
  _radarCtx.arc(cx, cy, 6, 0, Math.PI * 2);
  _radarCtx.fillStyle = '#0000ff';
  _radarCtx.fill();

  // AP dots
  radarAPsData.forEach(ap => {
    const dist = ap.estimated_radius_meters ?? 999;
    if (dist > radarMaxRange) return;
    const px = (dist / radarMaxRange) * r;
    const angle = _macAngle(ap.mac_address);
    const x = cx + Math.sin(angle) * px;
    const y = cy - Math.cos(angle) * px;
    radarRenderedPts.push({ x, y, ap });
    _radarCtx.beginPath();
    _radarCtx.arc(x, y, 5, 0, Math.PI * 2);
    _radarCtx.fillStyle = (radarHoveredAP === ap) ? '#ff9900' : '#ff0000';
    _radarCtx.fill();
  });

  if (radarHoveredAP) _drawRadarTooltip(radarHoveredAP);
}

function _drawRadarTooltip(ap) {
  const pt = radarRenderedPts.find(p => p.ap === ap);
  if (!pt || !_radarCtx) return;
  const { x, y } = pt;
  const lines = [
    (ap.ssid_alias || ap.mac_address).substring(0, 22),
    `RSSI: ${ap.smoothed_rssi ?? '?'} dBm`,
    `Dist: ${ap.estimated_radius_meters ?? '?'}m`,
  ];
  _radarCtx.font = "9px 'Press Start 2P', monospace";
  const w = Math.max(...lines.map(l => _radarCtx.measureText(l).width)) + 20;
  const lh = 14, h = lh * lines.length + 16;
  let tx = x + 15, ty = y + 15;
  if (tx + w > RADAR_SIZE) tx = x - w - 15;
  if (tx < 5) tx = 5;
  if (ty + h > RADAR_SIZE) ty = y - h - 15;
  if (ty < 5) ty = 5;
  _radarCtx.save();
  _radarCtx.fillStyle = '#ffffff'; _radarCtx.fillRect(tx, ty, w, h);
  _radarCtx.strokeStyle = '#000'; _radarCtx.lineWidth = 2; _radarCtx.strokeRect(tx, ty, w, h);
  _radarCtx.fillStyle = '#000'; _radarCtx.textBaseline = 'top';
  lines.forEach((l, i) => _radarCtx.fillText(l, tx + 8, ty + 8 + i * lh));
  _radarCtx.restore();
}

function _updateRadarTable() {
  const tbody = document.querySelector('#radarTable tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  [...radarAPsData]
    .filter(ap => (ap.estimated_radius_meters ?? 999) <= radarMaxRange)
    .sort((a, b) => (a.estimated_radius_meters ?? 999) - (b.estimated_radius_meters ?? 999))
    .forEach(ap => {
      const sig = ap.smoothed_rssi ?? -100;
      const sigClass = sig > -60 ? 'sig-high' : sig > -80 ? 'sig-med' : 'sig-low';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${ap.ssid_alias || '<span style="color:#999">HIDDEN</span>'}</td><td>${ap.mac_address}</td><td class="${sigClass}">${sig}</td><td><strong>${ap.estimated_radius_meters ?? '?'}m</strong></td>`;
      tr.addEventListener('mouseenter', () => { radarHoveredAP = ap; drawRadar(); });
      tr.addEventListener('mouseleave', () => { radarHoveredAP = null; drawRadar(); });
      tbody.appendChild(tr);
    });
}

if (_radarCanvas) {
  _radarCanvas.addEventListener('mousemove', e => {
    const rect = _radarCanvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (_radarCanvas.width / rect.width);
    const my = (e.clientY - rect.top)  * (_radarCanvas.height / rect.height);
    let found = null;
    for (const p of radarRenderedPts) {
      if (Math.hypot(mx - p.x, my - p.y) < 8) { found = p.ap; break; }
    }
    if (found !== radarHoveredAP) {
      radarHoveredAP = found;
      _radarCanvas.style.cursor = found ? 'pointer' : 'default';
      drawRadar();
    }
  });
}

const _rangeSelector = document.getElementById('rangeSelector');
if (_rangeSelector) {
  _rangeSelector.addEventListener('change', e => {
    radarMaxRange = parseInt(e.target.value);
    drawRadar();
    _updateRadarTable();
  });
}

async function loadRadar() {
  try {
    const json = await (await fetch('/api/assets/?page_size=1000')).json();
    const all = json.results ?? json;
    radarAPsData = all.filter(a => a.asset_type === 'AP');
    drawRadar();
    _updateRadarTable();
  } catch (e) { console.error('Radar error', e); }
}

// =============================================================
// ── AP-to-Client Cytoscape Graph ─────────────────────────────
// Uses /api/assets/client-ap-map/ — only re-renders when the
// association structure actually changes (hash check).
// =============================================================
let _cy           = null;
let _graphData    = [];
let _lastGraphKey = '';

async function loadClientGraph() {
  try {
    const data = await (await fetch('/api/assets/client-ap-map/')).json();
    _graphData = data;

    // Populate AP selector (preserve current selection)
    const sel = document.getElementById('apSelector');
    if (sel) {
      const prev = sel.value;
      sel.innerHTML = '<option value="">All APs</option>';
      data.forEach(ap => {
        const opt = document.createElement('option');
        opt.value = ap.ap_mac;
        opt.textContent = ap.ap_ssid ? `${ap.ap_ssid} (${ap.ap_mac})` : ap.ap_mac;
        sel.appendChild(opt);
      });
      if (prev && [...sel.options].some(o => o.value === prev)) sel.value = prev;
    }

    // Only re-render graph if structure changed
    const key = data.map(ap => `${ap.ap_mac}:${(ap.clients || []).length}`).join('|');
    if (key !== _lastGraphKey) {
      _lastGraphKey = key;
      _renderGraph(sel?.value || null);
    }
  } catch (e) { console.error('Client graph error', e); }
}

function _renderGraph(filterMac = null) {
  const container = document.getElementById('cy');
  if (!container || typeof cytoscape === 'undefined') return;

  const subset = filterMac ? _graphData.filter(ap => ap.ap_mac === filterMac) : _graphData;

  // Compute positions manually (preset layout = instant, no animation flicker)
  const elements = [];
  const added    = new Set();
  const AP_COLS  = Math.max(1, Math.ceil(Math.sqrt(subset.length)));
  const AP_GAP   = 220;
  const CX       = 300, CY = 160;

  subset.forEach((ap, idx) => {
    const col  = idx % AP_COLS;
    const row  = Math.floor(idx / AP_COLS);
    const apX  = CX + (col - (AP_COLS - 1) / 2) * AP_GAP;
    const apY  = CY + row * AP_GAP;

    if (!added.has(ap.ap_mac)) {
      elements.push({ data: { id: ap.ap_mac, label: ap.ap_ssid || ap.ap_mac, type: 'AP', mac: ap.ap_mac }, position: { x: apX, y: apY } });
      added.add(ap.ap_mac);
    }

      const clients = ap.clients || [];
    const clientR = Math.min(90, 40 + clients.length * 12);
    clients.forEach((client, ci) => {
      const angle = (ci / Math.max(clients.length, 1)) * 2 * Math.PI;
      const cx    = apX + Math.cos(angle) * clientR;
      const cy    = apY + Math.sin(angle) * clientR;
      if (!added.has(client.mac_address)) {
        // Show MAC address as the client label (avoid vendor/type display)
        elements.push({ data: { id: client.mac_address, label: client.mac_address, type: 'CLIENT', mac: client.mac_address, signal: client.smoothed_rssi }, position: { x: cx, y: cy } });
        added.add(client.mac_address);
      }
      elements.push({ data: { id: `e-${client.mac_address}-${ap.ap_mac}`, source: client.mac_address, target: ap.ap_mac, type: 'Associated' } });
    });
  });

  if (_cy) { _cy.destroy(); _cy = null; }

  if (elements.length === 0) {
    container.innerHTML = '<p style="text-align:center;padding:2rem;font-size:10px;color:#888">No associations yet — waiting for clients to connect to APs.</p>';
    return;
  }

    _cy = cytoscape({
    container,
    elements,
    style: [
      { selector: 'node[type="AP"]',     style: { 'background-color': '#007bff', 'label': 'data(label)', 'color': '#000', 'text-valign': 'bottom', 'text-halign': 'center', 'width': 38, 'height': 38, 'font-size': 6, 'shape': 'hexagon', 'font-family': RETRO_FONT } },
      { selector: 'node[type="CLIENT"]', style: { 'background-color': '#ff4d4d', 'label': 'data(label)', 'color': '#333', 'text-valign': 'bottom', 'text-halign': 'center', 'width': 22, 'height': 22, 'font-size': 5, 'font-family': RETRO_FONT } },
      { selector: 'edge',                style: { 'line-color': '#28a745', 'width': 2, 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#28a745' } },
      { selector: ':selected',           style: { 'border-width': 3, 'border-color': '#ff9900' } }
    ],
    layout: { name: 'preset' },
    userZoomingEnabled: true,
    userPanningEnabled: true,
  });

  // Populate association table
  const tbody = document.querySelector('#associationTable tbody');
  if (tbody) {
    tbody.innerHTML = '';
    subset.forEach(ap => {
      (ap.clients || []).forEach(client => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${ap.ap_ssid || ap.ap_mac}</td><td>${client.mac_address}</td><td>${client.vendor_oui || '—'}</td>`;
        tr.addEventListener('click', () => _cy?.nodes(`[mac = "${client.mac_address}"]`).select());
        tbody.appendChild(tr);
      });
    });
  }
}

const _apSelector = document.getElementById('apSelector');
if (_apSelector) {
  _apSelector.addEventListener('change', e => _renderGraph(e.target.value || null));
}

// ── System Messages Table ────────────────────────────────────
async function loadSystemMessages() {
  try {
    const msgs = await (await fetch('/api/messages/recent/')).json();
    const tbody = document.querySelector('#systemMessagesTable tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (msgs || []).forEach(m => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${m.timestamp ? new Date(m.timestamp).toLocaleString() : '—'}</td><td>${m.level || '—'}</td><td>${m.component || '—'}</td><td style="word-break:break-word;max-width:500px;">${m.message || '—'}</td>`;
      tbody.appendChild(tr);
    });
  } catch (e) { console.error('System messages error', e); }
}

// =============================================================
// ── Auto-refresh Bootstrap ───────────────────────────────────────────
// Charts & stats: every 5 seconds (lightweight)
// Radar + AP-client graph: every 5 seconds (heavier fetches)
// =============================================================
async function _refreshCharts() {
  await Promise.all([loadStats(), loadByType(), loadChannels(), loadVendors(), loadEncryption(), loadEventSeverity()]);
}

async function _refreshSpatial() {
  await Promise.all([loadRadar(), loadClientGraph()]);
}

(async function init() {
  await Promise.all([_refreshCharts(), _refreshSpatial(), loadSystemMessages()]);
  setInterval(_refreshCharts,  10000);
  setInterval(_refreshSpatial, 10000);
  setInterval(loadSystemMessages, 10000);
})();
