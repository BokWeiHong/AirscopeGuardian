'use strict';

// ── State ─────────────────────────────────────────────────────────────────
let _assets      = [];
let _totalCount  = 0;
let _activeMode  = '';         // label shown in the mode indicator
let _currentParams = '';

// ── Helpers ───────────────────────────────────────────────────────────────
function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
}

function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: '2-digit', day: '2-digit', year: '2-digit' })
         + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function showMsg(text, ok = true) {
    const el = document.getElementById('statusMsg');
    if (!el) return;
    el.textContent = text;
    el.className = 'assetmgr-status ' + (ok ? 'assetmgr-status-ok' : 'assetmgr-status-err');
    el.style.display = 'block';
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.style.display = 'none'; }, 4000);
}

function setMode(label) {
    _activeMode = label;
    const el = document.getElementById('modeLabel');
    if (el) el.textContent = label ? '[ ' + label + ' ]' : '';
}

// ── Load + Render ─────────────────────────────────────────────────────────
async function loadAssets(params = '') {
    _currentParams = params;
    try {
        const resp = await fetch('/assetmgr/api/assets/' + params);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        _assets     = data.results !== undefined ? data.results : data;
        _totalCount = data.count   !== undefined ? data.count   : _assets.length;
        renderTable();
    } catch (e) {
        console.error('loadAssets', e);
        document.getElementById('assetBody').innerHTML =
            '<tr><td colspan="9" style="color:red;">Error loading assets: ' + e.message + '</td></tr>';
    }
}

function renderTable() {
    const body    = document.getElementById('assetBody');
    const countEl = document.getElementById('assetCount');

    if (countEl) {
        const showing = _assets.length;
        countEl.textContent = showing === _totalCount
            ? `${_totalCount} assets`
            : `Showing ${showing} of ${_totalCount}`;
    }

    if (!_assets.length) {
        body.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#888;padding:1rem;">No assets match this filter.</td></tr>';
        return;
    }

    body.innerHTML = _assets.map(a => {
        const wl = a.is_whitelisted;
        const alias = (a.ssid_alias || '').replace(/"/g, '&quot;');
        return `<tr data-id="${a.id}">
            <td style="text-align:center;"><input type="checkbox" class="asset-chk" data-id="${a.id}"></td>
            <td style="font-size:10px;">${a.mac_address}</td>
            <td style="font-size:10px;">${a.vendor_oui || '—'}</td>
            <td><span class="type-badge type-${a.asset_type}">${a.asset_type}</span></td>
            <td>
                <input class="ssid-input" data-id="${a.id}" data-orig="${alias}"
                       value="${alias}" placeholder="Add note / alias…"
                       style="width:100%;min-width:100px;padding:3px 5px;border:2px solid #aaa;font-size:10px;font-family:inherit;">
            </td>
            <td style="text-align:center;">
                <input type="checkbox" class="wl-chk" data-id="${a.id}" ${wl ? 'checked' : ''}>
            </td>
            <td style="font-size:10px;text-align:center;">${a.operating_channel != null ? 'Ch ' + a.operating_channel : '—'}</td>
            <td style="font-size:10px;">${fmtTime(a.first_seen)}</td>
            <td style="font-size:10px;">${fmtTime(a.last_seen)}</td>
        </tr>`;
    }).join('');
}

// ── Single-row API saves ──────────────────────────────────────────────────
async function saveTag(id, ssidAlias) {
    const resp = await fetch(`/assetmgr/api/assets/${id}/tag/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ ssid_alias: ssidAlias }),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp.json();
}

async function saveWhitelistRow(id, isWhitelisted) {
    const resp = await fetch(`/assetmgr/api/assets/${id}/tag/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ is_whitelisted: isWhitelisted }),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp.json();
}

// ── Bulk actions ──────────────────────────────────────────────────────────
function getSelectedIds() {
    return Array.from(document.querySelectorAll('.asset-chk:checked'))
                .map(i => parseInt(i.dataset.id));
}

async function doBulkWhitelist(vendor, ids) {
    const body = vendor ? { vendor_oui: vendor } : { ids };
    const resp = await fetch('/assetmgr/api/assets/bulk-whitelist/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp.json();
}

// ── Event wiring ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadAssets('?page_size=500');

    // General search filter
    document.getElementById('btnFilter').addEventListener('click', () => {
        const v = document.getElementById('vendorFilter').value.trim();
        const wl = document.getElementById('wlFilter').value;
        let p = '?page_size=500';
        if (v) p += '&search=' + encodeURIComponent(v);
        if (wl) p += '&whitelisted=' + wl;
        setMode(v ? 'Search: ' + v : wl === '0' ? 'Unclassified' : wl === '1' ? 'Whitelisted' : 'All');
        loadAssets(p);
    });

    // Allow pressing Enter in the vendor box
    document.getElementById('vendorFilter').addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('btnFilter').click();
    });

    // Orphan view
    document.getElementById('btnShowOrphans').addEventListener('click', () => {
        setMode('Orphaned (>24h, unclassified)');
        loadAssets('?orphaned=1&page_size=500');
    });

    // Show all
    document.getElementById('btnShowAll').addEventListener('click', () => {
        document.getElementById('vendorFilter').value = '';
        document.getElementById('wlFilter').value = '';
        setMode('');
        loadAssets('?page_size=500');
    });

    // Bulk whitelist — always uses selected IDs
    document.getElementById('btnBulkWhitelist').addEventListener('click', async () => {
        const ids = getSelectedIds();
        if (!ids.length) {
            showMsg('Select rows to bulk whitelist.', false);
            return;
        }
        try {
            const result = await doBulkWhitelist(null, ids);
            showMsg(`✓ Whitelisted ${result.updated} asset(s).`);
            loadAssets(_currentParams || '?page_size=500');
        } catch (e) {
            showMsg('✗ Bulk whitelist failed: ' + e.message, false);
        }
    });

    // Select-all toggle in header
    document.getElementById('selectAll').addEventListener('change', e => {
        document.querySelectorAll('.asset-chk').forEach(c => { c.checked = e.target.checked; });
    });

    // Single-row alias save on blur
    document.getElementById('assetBody').addEventListener('focusout', async e => {
        const inp = e.target;
        if (!inp.classList.contains('ssid-input')) return;
        if (inp.value === inp.dataset.orig) return;   // unchanged — skip
        const id = inp.dataset.id;
        try {
            await saveTag(id, inp.value);
            inp.dataset.orig = inp.value;
            inp.style.border = '2px solid #00aa44';
            setTimeout(() => { inp.style.border = '2px solid #aaa'; }, 1500);
        } catch (e) {
            inp.style.border = '2px solid #cc0000';
            showMsg('✗ Save failed for asset ' + id + ': ' + e.message, false);
        }
    });

    // Single-row whitelist toggle
    document.getElementById('assetBody').addEventListener('change', async e => {
        const chk = e.target;
        if (!chk.classList.contains('wl-chk')) return;
        const id  = chk.dataset.id;
        try {
            await saveWhitelistRow(id, chk.checked);
            const row = chk.closest('tr');
            if (row) {
                row.style.background = chk.checked ? '#eeffee' : '';
                setTimeout(() => { row.style.background = ''; }, 1200);
            }
        } catch (e) {
            chk.checked = !chk.checked;   // revert
            showMsg('✗ Whitelist update failed: ' + e.message, false);
        }
    });
});
