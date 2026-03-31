'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let _queue      = [];          // current alert queue data
let _selectedId = null;        // currently selected event id
let _refreshSec = 10;
let _ticker     = null;
let _countdownHandle = null;

// ── Helpers ────────────────────────────────────────────────────────────────
function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
}

function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

function sevBadge(sev) {
    return `<span class="sev-badge sev-${sev}">${sev}</span>`;
}

function statusBadge(status) {
    const labels = {
        OPEN:           'OPEN',
        ACKNOWLEDGED:   'ACK',
        FALSE_POSITIVE: 'FP',
        RESOLVED:       'DONE',
    };
    return `<span class="status-badge status-${status}">${labels[status] || status}</span>`;
}

// ── Queue Loading ──────────────────────────────────────────────────────────
async function loadQueue() {
    try {
        const resp = await fetch('/api/events/queue/');
        if (!resp.ok) throw new Error(resp.status);
        _queue = await resp.json();
    } catch (e) {
        console.error('Queue fetch failed:', e);
        _queue = [];
    }
    renderQueue();
    // If a row was selected, refresh its detail panel from updated data
    if (_selectedId !== null) {
        const updated = _queue.find(e => e.id === _selectedId);
        if (updated) renderDetail(updated);
    }
}

function renderQueue() {
    const tbody = document.getElementById('queueBody');
    const countEl = document.getElementById('queueCount');
    const filterVal = document.getElementById('statusFilter')?.value || '';

    const visible = filterVal ? _queue.filter(ev => ev.status === filterVal) : _queue;

    if (!visible.length) {
        const msg = filterVal ? `No alerts with status: ${filterVal}` : 'No active alerts — system is clear.';
        tbody.innerHTML = `<tr><td colspan="5" class="detail-empty">${msg}</td></tr>`;
        if (countEl) countEl.textContent = filterVal ? `(0 / ${_queue.length})` : '(0 alerts)';
        return;
    }

    if (countEl) countEl.textContent = filterVal
        ? `(${visible.length} of ${_queue.length})`
        : `(${_queue.length} alert${_queue.length !== 1 ? 's' : ''})`;

    tbody.innerHTML = visible.map(ev => {
        const mac = ev.asset_mac || ev.asset?.mac_address || '—';
        const active = ev.id === _selectedId ? ' active-row' : '';
        return `<tr class="queue-row${active}" data-id="${ev.id}" onclick="selectRow(${ev.id})">
            <td>${sevBadge(ev.severity)}</td>
            <td>${ev.event_type || '—'}</td>
            <td style="font-size:8px;">${mac}</td>
            <td style="font-size:8px;">${fmtTime(ev.timestamp)}</td>
            <td>${statusBadge(ev.status)}</td>
        </tr>`;
    }).join('');
}

// ── Detail Panel ───────────────────────────────────────────────────────────
function selectRow(id) {
    _selectedId = id;
    const ev = _queue.find(e => e.id === id);
    if (!ev) return;
    document.querySelectorAll('.queue-row').forEach(r => {
        r.classList.toggle('active-row', parseInt(r.dataset.id) === id);
    });
    renderDetail(ev);
}

function field(label, value) {
    return `<div class="detail-field">
        <span class="detail-label">${label}</span>
        <span class="detail-value">${value || '—'}</span>
    </div>`;
}

function renderDetail(ev) {
    const panel = document.getElementById('detailPanel');
    const title = document.getElementById('detailTitle');

    title.textContent = `EVENT #${ev.id} — ${ev.event_type || 'Unknown'}`;

    const isClosed = ev.status === 'RESOLVED' || ev.status === 'FALSE_POSITIVE';
    const btnDisabled = isClosed ? 'disabled' : '';

    panel.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:0.5rem;">
            <div>
                ${field('Status',      statusBadge(ev.status))}
                ${field('Severity',    sevBadge(ev.severity))}
                ${field('Event Type',  ev.event_type)}
                ${field('Timestamp',   fmtTime(ev.timestamp))}
                ${field('Description', ev.description)}
            </div>

            <hr style="border:1px dashed #aaa; margin:0.3rem 0;">

            <div>
                <div style="font-size:12px; font-weight:bold; margin-bottom:0.3rem; color:#444;">ASSET DETAILS</div>
                ${field('MAC Address', `<strong>${ev.asset_mac || '—'}</strong>`)}
                ${field('Vendor/OUI',  ev.asset_vendor)}
                ${field('Asset Type',  ev.asset_type)}
                ${field('Channel',     ev.asset_channel)}
                ${field('RSSI',        ev.asset_rssi !== null && ev.asset_rssi !== undefined ? ev.asset_rssi + ' dBm' : '—')}
                ${field('Radius',      ev.asset_radius !== null && ev.asset_radius !== undefined ? '≈ ' + ev.asset_radius + ' m' : '—')}
                ${field('First Seen',  fmtTime(ev.asset_first_seen))}
            </div>

            <div>
                ${ev.resolved_by ? field('Resolved By', ev.resolved_by) : ''}
                ${ev.resolved_at ? field('Resolved At', fmtTime(ev.resolved_at)) : ''}
            </div>

            <div>
                <div style="font-size:12px; font-weight:bold; margin-bottom:0.2rem; color:#444;">ANALYST NOTES</div>
                <textarea id="notesArea" rows="5" placeholder="Enter analysis notes here..."${isClosed ? ' readonly' : ''}>${ev.analyst_notes || ''}</textarea>
            </div>

            <div class="action-status-msg" id="actionMsg"></div>

            <div class="action-row">
                <button class="action-btn btn-ack"      ${btnDisabled}
                    onclick="doAction('acknowledge')">Acknowledge</button>
                <button class="action-btn btn-resolve"  ${btnDisabled}
                    onclick="doAction('resolve')">Resolve</button>
                <button class="action-btn btn-fp"       ${btnDisabled}
                    onclick="doAction('false-positive')">False +ve</button>
                <button class="action-btn btn-dispatch" ${btnDisabled}
                    onclick="doAction('dispatch-hunter')">Dispatch Hunter</button>
                <a class="action-btn" style="text-decoration:none; border-color:#555; color:#333;"
                   href="/reports/export/incident/${ev.id}/" target="_blank">Export Incident</a>
            </div>
        </div>
    `;
}

// ── Actions ────────────────────────────────────────────────────────────────
async function doAction(actionName) {
    if (_selectedId === null) return;
    const notes = document.getElementById('notesArea')?.value || '';
    const msgEl = document.getElementById('actionMsg');

    try {
        const resp = await fetch(`/api/events/${_selectedId}/${actionName}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ notes }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || resp.statusText);
        }

        const data = await resp.json();

        if (msgEl) {
            msgEl.className = 'action-status-msg action-status-ok';
            msgEl.style.display = 'block';
            msgEl.textContent = `✓ ${actionName.toUpperCase()} applied.`;
            setTimeout(() => { if (msgEl) msgEl.style.display = 'none'; }, 3000);
        }

        // Update queue & re-render
        await loadQueue();
        if (actionName === 'dispatch') loadDispatchLog();

    } catch (e) {
        if (msgEl) {
            msgEl.className = 'action-status-msg action-status-err';
            msgEl.style.display = 'block';
            msgEl.textContent = `✗ Error: ${e.message}`;
        }
    }
}

// ── Dispatch Log ───────────────────────────────────────────────────────────
async function loadDispatchLog() {
    try {
        const resp = await fetch('/api/dispatch/?ordering=-timestamp&page_size=50');
        if (!resp.ok) throw new Error(resp.status);
        const data = await resp.json();
        const rows = data.results || data;
        renderDispatchLog(rows);
    } catch (e) {
        console.error('Dispatch log fetch failed:', e);
    }
}

function renderDispatchLog(rows) {
    const tbody = document.getElementById('dispatchBody');
    if (!rows || !rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="detail-empty">No dispatch records.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(d => `<tr>
        <td>${fmtTime(d.timestamp)}</td>
        <td>${d.admin_id || '—'}</td>
        <td>${d.target_mac || '—'}</td>
        <td>Ch ${d.locked_channel}</td>
        <td>${d.status}</td>
        <td style="max-width:150px; overflow:hidden; text-overflow:ellipsis;">${d.resolution_notes || ''}</td>
    </tr>`).join('');
}

// ── Countdown refresh ──────────────────────────────────────────────────────
function startCountdown() {
    let remaining = _refreshSec;
    const el = document.getElementById('refreshTimer');
    if (_countdownHandle) clearInterval(_countdownHandle);
    _countdownHandle = setInterval(() => {
        remaining--;
        if (el) el.textContent = `next refresh in ${remaining}s`;
        if (remaining <= 0) {
            remaining = _refreshSec;
            loadQueue();
        }
    }, 1000);
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadQueue();
    loadDispatchLog();
    startCountdown();
});
