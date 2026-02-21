// Theme
const theme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
document.documentElement.setAttribute('data-theme', theme);

document.getElementById('themeToggle').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
});

// Apply stored language on load
if (typeof currentLang !== 'undefined') {
    const langSel = document.getElementById('langSelect');
    if (langSel) langSel.value = currentLang;
    // Apply language to support page
    const supportDe = document.getElementById('supportDe');
    const supportEn = document.getElementById('supportEn');
    if (supportDe) supportDe.style.display = currentLang === 'de' ? '' : 'none';
    if (supportEn) supportEn.style.display = currentLang === 'en' ? '' : 'none';
    // Apply data-i18n on initial load
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const attr = el.getAttribute('data-i18n-attr');
        if (attr === 'placeholder') el.placeholder = t(key);
        else if (attr === 'title') el.title = t(key);
        else el.textContent = t(key);
    });
}

// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
        if (!link.dataset.page) return;
        e.preventDefault();
        const page = link.dataset.page;
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById('page-' + page).classList.add('active');
        const footerRight = document.querySelector('.footer-right');
        if (footerRight) footerRight.style.visibility = page === 'support' ? 'hidden' : '';
        loadPageData(page);
    });
});

function loadPageData(page) {
    if (page === 'dashboard') loadDashboard();
    else if (page === 'channels') loadChannels();
    else if (page === 'products') loadProducts();
    else if (page === 'log') loadLog();
    else if (page === 'caldav') loadCaldav();
    else if (page === 'help') { /* static content, handled by CSS lang-de/lang-en */ }
    else if (page === 'support') { /* static content, handled by setLanguage */ }
    else if (page === 'settings') loadSettings();
}

// Toast
function toast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// API Helper
async function api(url, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(url, opts);
    return resp.json();
}

// Dashboard
async function loadDashboard() {
    try {
        const data = await api('/api/status');
        if (data.error) {
            document.getElementById('statExpiring').textContent = '-';
            document.getElementById('statExpired').textContent = '-';
            document.getElementById('statMissing').textContent = '-';
            document.getElementById('statTotal').textContent = '-';
            toast(data.error, 'error');
            return;
        }
        document.getElementById('statExpiring').textContent = (data.due_products || []).length;
        document.getElementById('statExpired').textContent = (data.overdue_products || []).length + (data.expired_products || []).length;
        document.getElementById('statMissing').textContent = (data.missing_products || []).length;
        document.getElementById('statTotal').textContent = data.total_products || 0;

        fillProductTable('tableDue', data.due_products || [], ['name', 'amount', 'best_before_date']);
        const expired = (data.overdue_products || []).concat(data.expired_products || []);
        fillProductTable('tableExpired', expired, ['name', 'amount', 'best_before_date']);
        fillMissingTable('tableMissing', data.missing_products || []);
    } catch (e) {
        toast(t('dash.load_error') + ': ' + e.message, 'error');
    }
}

function fillProductTable(tableId, items, fields) {
    const tbody = document.querySelector('#' + tableId + ' tbody');
    if (!items.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="3">' + esc(t('dash.no_entries')) + '</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const p = item.product || item;
        return `<tr>
            <td>${esc(p.name || t('dash.unknown'))}</td>
            <td>${item.amount || p.amount || '-'}</td>
            <td>${item.best_before_date || '-'}</td>
        </tr>`;
    }).join('');
}

function fillMissingTable(tableId, items) {
    const tbody = document.querySelector('#' + tableId + ' tbody');
    if (!items.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="2">' + esc(t('dash.no_entries')) + '</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const p = item.product || item;
        return `<tr>
            <td>${esc(p.name || item.name || t('dash.unknown'))}</td>
            <td>${item.amount_missing || '-'}</td>
        </tr>`;
    }).join('');
}

async function checkNow() {
    toast(t('dash.check_running'), 'info');
    const data = await api('/api/check-now', 'POST');
    if (data.ok) {
        toast(data.message, 'success');
        loadDashboard();
    } else {
        toast(data.message || t('gen.error'), 'error');
    }
}

// Channels
const CHANNEL_FIELDS = {
    email: [
        { key: 'smtp_host', labelKey: 'ch.smtp_host', type: 'text', placeholder: 'smtp.gmail.com' },
        { key: 'smtp_port', labelKey: 'ch.smtp_port', type: 'number', placeholder: '587' },
        { key: 'username', labelKey: 'ch.username', type: 'text' },
        { key: 'password', labelKey: 'ch.password', type: 'password' },
        { key: 'from_email', labelKey: 'ch.from_email', type: 'email' },
        { key: 'to_email', labelKey: 'ch.to_email', type: 'email' },
        { key: 'use_tls', labelKey: 'ch.use_tls', type: 'checkbox', default: true },
    ],
    pushover: [
        { key: 'api_token', labelKey: 'ch.api_token', type: 'text' },
        { key: 'user_key', labelKey: 'ch.user_key', type: 'text' },
        { key: 'priority', labelKey: 'ch.priority', type: 'number', placeholder: '0' },
    ],
    telegram: [
        { key: 'bot_token', labelKey: 'ch.bot_token', type: 'text' },
        { key: 'chat_id', labelKey: 'ch.chat_id', type: 'text' },
    ],
    slack: [
        { key: 'webhook_url', labelKey: 'ch.webhook_url', type: 'url' },
    ],
    discord: [
        { key: 'webhook_url', labelKey: 'ch.webhook_url', type: 'url' },
    ],
    gotify: [
        { key: 'server_url', labelKey: 'ch.server_url', type: 'url', placeholder: 'https://gotify.example.com' },
        { key: 'app_token', labelKey: 'ch.app_token', type: 'text' },
        { key: 'priority', labelKey: 'ch.gotify_priority', type: 'number', placeholder: '5' },
    ],
};

async function loadChannels() {
    const channels = await api('/api/channels');
    const list = document.getElementById('channelsList');
    if (!channels.length) {
        list.innerHTML = '<div class="card"><p class="hint" style="margin:0">' + esc(t('ch.no_channels')) + '</p></div>';
        return;
    }
    list.innerHTML = channels.map(ch => `
        <div class="channel-card">
            <div class="channel-info">
                <div class="channel-status ${ch.enabled ? '' : 'disabled'}"></div>
                <strong>${esc(ch.name)}</strong>
                <span class="channel-type-badge">${esc(ch.type)}</span>
            </div>
            <div class="channel-actions">
                <button class="btn btn-sm btn-secondary" onclick="testChannel(${ch.id})">${esc(t('ch.test'))}</button>
                <button class="btn btn-sm btn-secondary" onclick="editChannel(${ch.id})">${esc(t('ch.edit'))}</button>
                <button class="btn btn-sm btn-danger" onclick="deleteChannel(${ch.id})">${esc(t('ch.delete'))}</button>
            </div>
        </div>
    `).join('');
    window._channels = channels;
}

function showAddChannel() {
    document.getElementById('channelId').value = '';
    document.getElementById('channelName').value = '';
    document.getElementById('channelType').value = 'email';
    document.getElementById('channelEnabled').checked = true;
    document.getElementById('channelModalTitle').textContent = t('ch.add_title');
    updateChannelFields();
    openModal('channelModal');
}

function editChannel(id) {
    const ch = (window._channels || []).find(c => c.id === id);
    if (!ch) return;
    document.getElementById('channelId').value = ch.id;
    document.getElementById('channelName').value = ch.name;
    document.getElementById('channelType').value = ch.type;
    document.getElementById('channelEnabled').checked = !!ch.enabled;
    document.getElementById('channelModalTitle').textContent = t('ch.edit_title');
    updateChannelFields(ch.config || {});
    openModal('channelModal');
}

function updateChannelFields(existingConfig = {}) {
    const type = document.getElementById('channelType').value;
    const untested = document.getElementById('channelUntested');
    if (untested) untested.style.display = type === 'gotify' ? '' : 'none';
    const fields = CHANNEL_FIELDS[type] || [];
    const container = document.getElementById('channelConfigFields');
    container.innerHTML = fields.map(f => {
        const val = existingConfig[f.key] ?? f.default ?? '';
        const label = t(f.labelKey);
        if (f.type === 'checkbox') {
            return `<div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="cfg_${f.key}" ${val ? 'checked' : ''}>
                    ${esc(label)}
                </label>
            </div>`;
        }
        return `<div class="form-group">
            <label>${esc(label)}</label>
            <input type="${f.type}" id="cfg_${f.key}" value="${esc(String(val))}" placeholder="${esc(f.placeholder || '')}">
        </div>`;
    }).join('');
}

async function saveChannel(e) {
    e.preventDefault();
    const type = document.getElementById('channelType').value;
    const fields = CHANNEL_FIELDS[type] || [];
    const config = {};
    const emptyFields = [];
    fields.forEach(f => {
        const el = document.getElementById('cfg_' + f.key);
        const val = f.type === 'checkbox' ? el.checked : el.value;
        config[f.key] = val;
        if (f.type !== 'checkbox' && !String(val).trim()) {
            emptyFields.push(t(f.labelKey));
        }
    });
    if (emptyFields.length > 0) {
        const msg = t('ch.fields_empty').replace('{fields}', emptyFields.map(f => '- ' + f).join('\n'));
        if (!confirm(msg)) return;
    }
    const data = {
        id: document.getElementById('channelId').value || undefined,
        type,
        name: document.getElementById('channelName').value,
        enabled: document.getElementById('channelEnabled').checked ? 1 : 0,
        config,
    };
    await api('/api/channels', 'POST', data);
    closeModal('channelModal');
    toast(t('ch.saved'), 'success');
    loadChannels();
}

async function deleteChannel(id) {
    if (!confirm(t('ch.confirm_delete'))) return;
    await api('/api/channels/' + id, 'DELETE');
    toast(t('ch.deleted'), 'success');
    loadChannels();
}

async function testChannel(id) {
    toast(t('ch.test_sending'), 'info');
    const data = await api('/api/channels/' + id + '/test', 'POST');
    if (data.ok) {
        toast(data.message || t('ch.test_sent'), 'success');
    } else {
        toast(data.message || t('gen.error'), 'error');
        if (data.detail) {
            console.error(t('ch.test_error'), data.detail);
            showErrorDetail(data.message, data.detail);
        }
    }
}

// Products
async function loadProducts() {
    try {
        const data = await api('/api/products');
        if (data.error) { toast(data.error, 'error'); return; }
        const tbody = document.querySelector('#tableProducts tbody');
        const products = data.products || [];
        if (!products.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="5">' + esc(t('prod.no_products')) + '</td></tr>';
            return;
        }
        tbody.innerHTML = products.map(p => `
            <tr>
                <td>${esc(p.name)}</td>
                <td>${p.amount}</td>
                <td>${p.best_before_date || '-'}</td>
                <td>
                    <input type="number" min="1" max="365" value="${p.custom_days || ''}"
                        style="width:120px" placeholder="${esc(t('prod.placeholder'))}"
                        data-pid="${p.product_id}" data-pname="${esc(p.name)}"
                        onchange="saveOverride(this)">
                </td>
                <td>
                    ${p.custom_days ? '<button class="btn btn-sm btn-secondary" onclick="removeOverride(' + p.product_id + ')">' + esc(t('prod.reset')) + '</button>' : ''}
                </td>
            </tr>
        `).join('');
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

async function saveOverride(el) {
    const days = parseInt(el.value);
    if (!days || days < 1) return;
    await api('/api/products/override', 'POST', {
        product_id: parseInt(el.dataset.pid),
        product_name: el.dataset.pname,
        days,
    });
    toast(t('prod.saved'), 'success');
}

async function removeOverride(pid) {
    await api('/api/products/override', 'POST', { product_id: pid, delete: true });
    toast(t('prod.override_removed'), 'success');
    loadProducts();
}

// Log
const LOG_TYPE_LABELS = {
    'expiring': 'log.type_expiring',
    'expired': 'log.type_expired',
    'missing': 'log.type_missing',
    'test': 'log.type_test',
    'error': 'log.type_error',
};
const LOG_TYPE_COLORS = {
    'expiring': '#e67e22',
    'expired': '#e74c3c',
    'missing': '#9b59b6',
    'test': '#3498db',
    'error': '#e74c3c',
};

const LOG_MSG_TRANSLATIONS = {
    'Ablaufdatum': 'log.msg_expiry_date',
    'Abgelaufen seit': 'log.msg_expired_since',
    'Fehlmenge': 'log.msg_missing_amount',
    'Bald ablaufend': 'log.msg_type_expiring',
    'Abgelaufen': 'log.msg_type_expired',
    'Mindestbestand unterschritten': 'log.msg_type_missing',
};

function translateLogMessage(msg) {
    if (!msg) return msg;
    for (const [de, key] of Object.entries(LOG_MSG_TRANSLATIONS)) {
        if (msg.includes(de)) {
            msg = msg.split(de).join(t(key));
        }
    }
    return msg;
}

window._logData = [];
window._logSort = { col: 'timestamp', dir: 'desc' };
window._logFilters = {};

async function loadLog() {
    const log = await api('/api/log');
    window._logData = log;
    // Populate type filter dropdown with unique types
    const typeSelect = document.querySelector('.filter-select[data-filter="notification_type"]');
    if (typeSelect) {
        const current = typeSelect.value;
        const types = [...new Set(log.map(l => l.notification_type).filter(Boolean))];
        typeSelect.innerHTML = '<option value="">' + esc(t('log.filter_all')) + '</option>' +
            types.map(ty => {
                const lk = LOG_TYPE_LABELS[ty];
                return '<option value="' + esc(ty) + '">' + esc(lk ? t(lk) : ty) + '</option>';
            }).join('');
        typeSelect.value = current;
    }
    // Update status filter dropdown labels
    const statusSelect = document.querySelector('.filter-select[data-filter="success"]');
    if (statusSelect) {
        const current = statusSelect.value;
        statusSelect.innerHTML = '<option value="">' + esc(t('log.filter_all')) + '</option>' +
            '<option value="1">' + esc(t('log.status_ok')) + '</option>' +
            '<option value="0">' + esc(t('log.status_error')) + '</option>';
        statusSelect.value = current;
    }
    renderLog();
}

function renderLog() {
    const tbody = document.querySelector('#tableLog tbody');
    let data = window._logData.slice();
    if (!data.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">' + esc(t('log.no_entries')) + '</td></tr>';
        return;
    }
    // Apply filters
    const filters = window._logFilters;
    data = data.filter(l => {
        for (const key in filters) {
            const fv = filters[key];
            if (!fv) continue;
            if (key === 'success') {
                if (String(l.success ? 1 : 0) !== fv) return false;
            } else if (key === 'notification_type') {
                if (l.notification_type !== fv) return false;
            } else {
                const val = String(l[key] || '').toLowerCase();
                if (!val.includes(fv.toLowerCase())) return false;
            }
        }
        return true;
    });
    // Apply sort
    const { col, dir } = window._logSort;
    data.sort((a, b) => {
        let va = a[col] ?? '';
        let vb = b[col] ?? '';
        if (col === 'success') { va = va ? 1 : 0; vb = vb ? 1 : 0; }
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return dir === 'asc' ? -1 : 1;
        if (va > vb) return dir === 'asc' ? 1 : -1;
        return 0;
    });
    // Update sort indicators
    document.querySelectorAll('#tableLog th.sortable').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (th.dataset.sort === col) th.classList.add('sort-' + dir);
    });
    if (!data.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">' + esc(t('log.no_entries')) + '</td></tr>';
        return;
    }
    window._logMessages = {};
    tbody.innerHTML = data.map((l, idx) => {
        const typLabelKey = LOG_TYPE_LABELS[l.notification_type];
        const typLabel = typLabelKey ? t(typLabelKey) : l.notification_type;
        const typColor = LOG_TYPE_COLORS[l.notification_type] || 'var(--text-muted)';
        const msgClass = !l.success ? 'log-error-msg' : '';
        const displayMsg = translateLogMessage(l.message);
        if (!l.success) window._logMessages[idx] = displayMsg;
        return `<tr>
            <td>${esc(l.timestamp)}</td>
            <td>${esc(l.product_name || '-')}</td>
            <td><span class="log-type-badge" style="background:${typColor}">${esc(typLabel)}</span></td>
            <td>${esc(l.channel_name)}</td>
            <td class="${msgClass}" ${!l.success ? `title="${esc(t('log.click_details'))}" style="cursor:pointer" onclick="showLogError(${idx})"` : ''}>${esc(displayMsg)}</td>
            <td>${l.success ? '<span style="color:var(--success)">' + esc(t('log.status_ok')) + '</span>' : '<span style="color:var(--danger)">' + esc(t('log.status_error')) + '</span>'}</td>
        </tr>`;
    }).join('');
}

// Log filter & sort event listeners
document.querySelectorAll('#tableLog .filter-input').forEach(input => {
    input.addEventListener('input', () => {
        window._logFilters[input.dataset.filter] = input.value;
        renderLog();
    });
});
document.querySelectorAll('#tableLog .filter-select').forEach(sel => {
    sel.addEventListener('change', () => {
        window._logFilters[sel.dataset.filter] = sel.value;
        renderLog();
    });
});
document.querySelectorAll('#tableLog th.sortable').forEach(th => {
    th.addEventListener('click', () => {
        const col = th.dataset.sort;
        if (window._logSort.col === col) {
            window._logSort.dir = window._logSort.dir === 'asc' ? 'desc' : 'asc';
        } else {
            window._logSort = { col, dir: 'asc' };
        }
        renderLog();
    });
});

async function clearLog() {
    if (!confirm(t('log.confirm_clear'))) return;
    await api('/api/log', 'DELETE');
    toast(t('log.cleared'), 'success');
    loadLog();
}

// Settings
async function loadSettings() {
    const s = await api('/api/settings');
    document.getElementById('setGrocyUrl').value = s.grocy_url || '';
    document.getElementById('setApiKey').value = s.grocy_api_key || '';
    document.getElementById('setDefaultDays').value = s.default_days_before_expiry || 5;
    document.getElementById('setInterval').value = s.check_interval_hours || 6;
    document.getElementById('setNotifyExpiring').checked = s.notify_expiring !== '0';
    document.getElementById('setNotifyExpired').checked = s.notify_expired !== '0';
    document.getElementById('setNotifyMissing').checked = s.notify_missing !== '0';
    document.getElementById('setVerifySsl').checked = s.grocy_verify_ssl !== '0';
    document.getElementById('setRepeatLimit').value = s.notification_repeat_limit || '0';
    // Set language selector to current language
    const langSel = document.getElementById('langSelect');
    if (langSel) langSel.value = currentLang;
}

async function saveSettings(e) {
    e.preventDefault();
    await api('/api/settings', 'POST', {
        grocy_url: document.getElementById('setGrocyUrl').value,
        grocy_api_key: document.getElementById('setApiKey').value,
        default_days_before_expiry: document.getElementById('setDefaultDays').value,
        check_interval_hours: document.getElementById('setInterval').value,
        notify_expiring: document.getElementById('setNotifyExpiring').checked ? '1' : '0',
        notify_expired: document.getElementById('setNotifyExpired').checked ? '1' : '0',
        notify_missing: document.getElementById('setNotifyMissing').checked ? '1' : '0',
        grocy_verify_ssl: document.getElementById('setVerifySsl').checked ? '1' : '0',
        notification_repeat_limit: document.getElementById('setRepeatLimit').value,
    });
    toast(t('set.saved'), 'success');
}

async function testConnection() {
    const status = document.getElementById('connectionStatus');
    status.textContent = t('set.testing');
    status.style.color = 'var(--text-muted)';
    const data = await api('/api/test-connection', 'POST', {
        grocy_url: document.getElementById('setGrocyUrl').value,
        grocy_api_key: document.getElementById('setApiKey').value,
        grocy_verify_ssl: document.getElementById('setVerifySsl').checked ? '1' : '0',
    });
    status.textContent = data.message;
    status.style.color = data.ok ? 'var(--success)' : 'var(--danger)';
}

// CalDAV
function caldavApplyServerType() {
    const sel = document.getElementById('caldavServerType');
    const pathInput = document.getElementById('caldavPath');
    if (sel.value) {
        pathInput.value = sel.value;
    }
}

function caldavSyncServerType(path) {
    const sel = document.getElementById('caldavServerType');
    const options = Array.from(sel.options);
    const match = options.find(o => o.value && o.value === path);
    sel.value = match ? match.value : '';
}

async function loadCaldav() {
    try {
        const status = await api('/api/caldav/status');
        document.getElementById('caldavTasks').textContent = status.tasks_synced || 0;
        document.getElementById('caldavChores').textContent = status.chores_synced || 0;
        document.getElementById('caldavLastSync').textContent = status.last_sync || t('cal.never');
        document.getElementById('caldavLastSync').style.fontSize = status.last_sync ? '.9em' : '';

        const enabled = status.enabled;
        document.getElementById('caldavEnabled').textContent = enabled ? t('cal.active') : t('cal.inactive');
        const statusCard = document.getElementById('caldavStatusCard');
        statusCard.className = 'stat-card ' + (enabled ? 'stat-ok' : 'stat-warning');

        document.getElementById('caldavUrl').value = status.caldav_url || '';
        document.getElementById('caldavPath').value = status.caldav_path || '';
        caldavSyncServerType(status.caldav_path || '');
        document.getElementById('caldavUsername').value = status.caldav_username || '';
        const pwField = document.getElementById('caldavPassword');
        if (status.has_caldav_password && !pwField.value) {
            pwField.placeholder = '••••••••';
        }
        document.getElementById('caldavVerifySsl').checked = status.caldav_verify_ssl !== '0';
        document.getElementById('caldavInterval').value = status.sync_interval || 30;
        document.getElementById('caldavSyncEnabled').checked = enabled;

        if (status.caldav_calendar) {
            const select = document.getElementById('caldavCalendar');
            if (!select.querySelector('option[value="' + status.caldav_calendar + '"]')) {
                const opt = document.createElement('option');
                opt.value = status.caldav_calendar;
                opt.textContent = status.caldav_calendar;
                select.appendChild(opt);
            }
            select.value = status.caldav_calendar;
        }

        loadSyncMap();
    } catch (e) {
        toast(t('cal.load_error') + ': ' + e.message, 'error');
    }
}

async function loadSyncMap() {
    const map = await api('/api/caldav/map');
    const tbody = document.querySelector('#tableSyncMap tbody');
    if (!map.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">' + esc(t('cal.no_entries')) + '</td></tr>';
        return;
    }
    tbody.innerHTML = map.map(m => {
        const dir = m.sync_direction || '';
        const dirClass = dir.includes('grocy') && dir.includes('caldav')
            ? (dir.indexOf('grocy') < dir.indexOf('caldav') ? 'dir-grocy-caldav' : 'dir-caldav-grocy')
            : '';
        return `
        <tr>
            <td><span class="sync-type-badge sync-type-${esc(m.grocy_type)}">${esc(m.grocy_type)}</span></td>
            <td>${m.grocy_id}</td>
            <td class="uid-cell" title="${esc(m.caldav_uid)}">${esc(m.caldav_uid.substring(0, 30))}&hellip;</td>
            <td>${esc(m.last_summary || '-')}</td>
            <td><span class="sync-status-badge sync-status-${m.last_status === 'COMPLETED' ? 'completed' : 'pending'}">${esc(m.last_status)}</span></td>
            <td><span class="sync-dir-badge ${dirClass}">${esc(dir || '-')}</span></td>
            <td>${esc(m.last_synced)}</td>
        </tr>`;
    }).join('');
}

async function caldavTestConnection() {
    const status = document.getElementById('caldavConnectionStatus');
    status.textContent = t('cal.testing');
    status.style.color = 'var(--text-muted)';
    const testData = {
        caldav_url: document.getElementById('caldavUrl').value,
        caldav_path: document.getElementById('caldavPath').value,
        caldav_username: document.getElementById('caldavUsername').value,
        caldav_verify_ssl: document.getElementById('caldavVerifySsl').checked ? '1' : '0',
    };
    const pw = document.getElementById('caldavPassword').value;
    if (pw) testData.caldav_password = pw;
    const data = await api('/api/caldav/test', 'POST', testData);
    status.textContent = data.message;
    status.style.color = data.ok ? 'var(--success)' : 'var(--danger)';
}

async function caldavLoadCalendars() {
    const select = document.getElementById('caldavCalendar');
    select.innerHTML = '<option value="">' + esc(t('cal.calendar_loading')) + '</option>';
    const data = await api('/api/caldav/calendars');
    select.innerHTML = '<option value="">' + esc(t('cal.calendar_select')) + '</option>';
    if (data.ok && data.calendars) {
        data.calendars.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        });
    } else {
        toast(data.message || t('cal.calendar_error'), 'error');
    }
}

async function saveCaldavSettings() {
    const settings = {
        caldav_url: document.getElementById('caldavUrl').value,
        caldav_path: document.getElementById('caldavPath').value,
        caldav_username: document.getElementById('caldavUsername').value,
        caldav_verify_ssl: document.getElementById('caldavVerifySsl').checked ? '1' : '0',
        caldav_calendar: document.getElementById('caldavCalendar').value,
        caldav_sync_enabled: document.getElementById('caldavSyncEnabled').checked ? '1' : '0',
        caldav_sync_interval_minutes: document.getElementById('caldavInterval').value,
    };
    const pw = document.getElementById('caldavPassword').value;
    if (pw) settings.caldav_password = pw;

    await api('/api/settings', 'POST', settings);
    toast(t('cal.saved'), 'success');
    loadCaldav();
}

async function caldavSyncNow() {
    toast(t('cal.sync_running'), 'info');
    const data = await api('/api/caldav/sync-now', 'POST');
    if (data.ok) {
        let msg = data.message;
        if (data.stats) {
            msg += ` (Tasks: ${data.stats.tasks_synced}, Chores: ${data.stats.chores_synced}, CalDAV→Grocy: ${data.stats.caldav_to_grocy})`;
        }
        toast(msg, 'success');
        loadCaldav();
    } else {
        toast(data.message || t('cal.sync_error'), 'error');
    }
}

async function clearSyncMap() {
    if (!confirm(t('cal.confirm_clear_map'))) return;
    await api('/api/caldav/map', 'DELETE');
    toast(t('cal.map_cleared'), 'success');
    loadSyncMap();
}

function showLogError(idx) {
    const msg = (window._logMessages || {})[idx] || t('log.no_details');
    showErrorDetail(t('log.error_title'), msg);
}

// Error Detail Modal
function showErrorDetail(title, detail) {
    let modal = document.getElementById('errorDetailModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'errorDetailModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width:700px">
                <div class="modal-header">
                    <h3 id="errorDetailTitle"></h3>
                    <button class="modal-close" onclick="closeModal('errorDetailModal')">&times;</button>
                </div>
                <pre id="errorDetailText" style="white-space:pre-wrap;word-break:break-all;background:var(--bg-secondary);padding:1em;border-radius:8px;max-height:400px;overflow-y:auto;font-size:.85em;"></pre>
            </div>`;
        document.body.appendChild(modal);
    }
    document.getElementById('errorDetailTitle').textContent = title || t('log.error_title');
    document.getElementById('errorDetailText').textContent = detail;
    openModal('errorDetailModal');
}

// Helpers
function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }
function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// Init
loadDashboard();
