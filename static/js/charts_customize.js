/* =============================================================
   AirscopeGuardian – Charts Dashboard
   Endpoints:
     GET /api/assets/stats/
     GET /api/assets/by-type/
     GET /api/assets/channel-usage/
     GET /api/assets/vendor-distribution/
     GET /api/assets/encryption-breakdown/
     GET /api/events/summary/
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
  chartInstances[id] = new Chart(ctx.getContext('2d'), config);
}

function retroPlugin(titleText) {
  return {
    legend: {
      position: 'bottom',
      labels: { font: { family: RETRO_FONT, size: 7 } }
    },
    title: {
      display: !!titleText,
      text: titleText,
      color: 'black',
      font: { family: RETRO_FONT, size: 10 }
    },
    tooltip: {
      backgroundColor: '#222',
      titleFont: { family: RETRO_FONT, size: 9 },
      bodyFont:  { family: RETRO_FONT, size: 7 },
      padding: 8
    }
  };
}

// ── Stats Cards ────────────────────────────────────────────────
async function loadStats() {
  try {
    const res  = await fetch('/api/assets/stats/');
    const data = await res.json();
    document.getElementById('stat-total').textContent    = data.total_assets  ?? '—';
    document.getElementById('stat-aps').textContent      = data.access_points ?? '—';
    document.getElementById('stat-clients').textContent  = data.clients       ?? '—';
    document.getElementById('stat-signal').innerHTML     = (data.avg_signal ?? '—') + '<span>dBm</span>';
    document.getElementById('stat-whitelisted').textContent = data.whitelisted ?? '—';
  } catch (e) { console.error('Stats error', e); }
}

// ── Asset Type Pie ─────────────────────────────────────────────
async function loadByType() {
  try {
    const json = await (await fetch('/api/assets/by-type/')).json();
    const labels = json.map(d => d.asset_type);
    const values = json.map(d => d.count);
    mkChart('chartAssetType', {
      type: 'pie',
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: COLORS, borderColor: '#000', borderWidth: 2 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: retroPlugin('Asset Types') }
    });
  } catch (e) { console.error('By-type error', e); }
}

// ── Channel Usage Bar ──────────────────────────────────────────
async function loadChannels() {
  try {
    const json = await (await fetch('/api/assets/channel-usage/')).json();
    const labels = json.map(d => `CH ${d.operating_channel}`);
    const values = json.map(d => d.count);
    mkChart('chartChannels', {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Devices',
          data: values,
          backgroundColor: values.map((_, i) => COLORS[i % COLORS.length]),
          borderColor: '#000', borderWidth: 2
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          x: { ticks: { font: { family: RETRO_FONT, size: 7 } } },
          y: { beginAtZero: true, ticks: { font: { family: RETRO_FONT, size: 7 } } }
        },
        plugins: retroPlugin('Channel Usage')
      }
    });
  } catch (e) { console.error('Channel error', e); }
}

// ── Vendor Distribution Bar ────────────────────────────────────
async function loadVendors() {
  try {
    const json = await (await fetch('/api/assets/vendor-distribution/')).json();
    const labels = json.map(d => d.vendor_oui || 'Unknown');
    const values = json.map(d => d.count);
    mkChart('chartVendors', {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Devices',
          data: values,
          backgroundColor: values.map((_, i) => COLORS[i % COLORS.length]),
          borderColor: '#000', borderWidth: 2
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { beginAtZero: true, ticks: { font: { family: RETRO_FONT, size: 7 } } },
          y: { ticks: { font: { family: RETRO_FONT, size: 7 } } }
        },
        plugins: retroPlugin('Top Vendors')
      }
    });
  } catch (e) { console.error('Vendor error', e); }
}

// ── Encryption Pie ─────────────────────────────────────────────
async function loadEncryption() {
  try {
    const d = await (await fetch('/api/assets/encryption-breakdown/')).json();
    mkChart('chartEncryption', {
      type: 'pie',
      data: {
        labels: ['Encrypted', 'Open'],
        datasets: [{ data: [d.encrypted, d.unencrypted], backgroundColor: [COLORS[3], COLORS[1]], borderColor: '#000', borderWidth: 2 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: retroPlugin('Encryption') }
    });
  } catch (e) { console.error('Encryption error', e); }
}

// ── Security Events by Severity Pie ───────────────────────────
async function loadEventSeverity() {
  try {
    const d = await (await fetch('/api/events/summary/')).json();
    const labels = d.by_severity.map(x => x.severity);
    const values = d.by_severity.map(x => x.count);
    mkChart('chartSeverity', {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: COLORS, borderColor: '#000', borderWidth: 2 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: retroPlugin('Events by Severity') }
    });

    // Fill recent events table
    const tbody = document.querySelector('#recentEventsTable tbody');
    if (tbody) {
      tbody.innerHTML = '';
      (d.recent || []).forEach(ev => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${ev['asset__mac_address'] || '—'}</td>
          <td>${ev.event_type || '—'}</td>
          <td>${ev.severity || '—'}</td>
          <td>${ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '—'}</td>`;
        tbody.appendChild(tr);
      });
    }
  } catch (e) { console.error('Event severity error', e); }
}

// ── Bootstrap ─────────────────────────────────────────────────
(async function init() {
  await Promise.all([
    loadStats(),
    loadByType(),
    loadChannels(),
    loadVendors(),
    loadEncryption(),
    loadEventSeverity(),
  ]);
})();
