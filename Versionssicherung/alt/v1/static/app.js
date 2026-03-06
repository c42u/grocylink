// Theme
const theme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
document.documentElement.setAttribute('data-theme', theme);

document.getElementById('themeToggle').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
});

// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
        e.preventDefault();
        const page = link.dataset.page;
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById('page-' + page).classList.add('active');
        loadPageData(page);
    });
});

function loadPageData(page) {
    if (page === 'dashboard') loadDashboard();
    else if (page === 'channels') loadChannels();
    else if (page === 'products') loadProducts();
    else if (page === 'log') loadLog();
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
        toast('Fehler beim Laden des Dashboards: ' + e.message, 'error');
    }
}

function fillProductTable(tableId, items, fields) {
    const tbody = document.querySelector('#' + tableId + ' tbody');
    if (!items.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="3">Keine Einträge</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const p = item.product || item;
        return `<tr>
            <td>${esc(p.name || 'Unbekannt')}</td>
            <td>${item.amount || p.amount || '-'}</td>
            <td>${item.best_before_date || '-'}</td>
        </tr>`;
    }).join('');
}

function fillMissingTable(tableId, items) {
    const tbody = document.querySelector('#' + tableId + ' tbody');
    if (!items.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="2">Keine Einträge</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const p = item.product || item;
        return `<tr>
            <td>${esc(p.name || item.name || 'Unbekannt')}</td>
            <td>${item.amount_missing || '-'}</td>
        </tr>`;
    }).join('');
}

async function checkNow() {
    toast('Check wird durchgeführt...', 'info');
    const data = await api('/api/check-now', 'POST');
    if (data.ok) {
        toast(data.message, 'success');
        loadDashboard();
    } else {
        toast(data.message || 'Fehler', 'error');
    }
}

// Channels
const CHANNEL_FIELDS = {
    email: [
        { key: 'smtp_host', label: 'SMTP Host', type: 'text', placeholder: 'smtp.gmail.com' },
        { key: 'smtp_port', label: 'SMTP Port', type: 'number', placeholder: '587' },
        { key: 'username', label: 'Benutzername', type: 'text' },
        { key: 'password', label: 'Passwort', type: 'password' },
        { key: 'from_email', label: 'Absender-Email', type: 'email' },
        { key: 'to_email', label: 'Empfänger-Email', type: 'email' },
        { key: 'use_tls', label: 'TLS verwenden', type: 'checkbox', default: true },
    ],
    pushover: [
        { key: 'api_token', label: 'API Token', type: 'text' },
        { key: 'user_key', label: 'User Key', type: 'text' },
        { key: 'priority', label: 'Priorität (-2 bis 2)', type: 'number', placeholder: '0' },
    ],
    telegram: [
        { key: 'bot_token', label: 'Bot Token', type: 'text' },
        { key: 'chat_id', label: 'Chat ID', type: 'text' },
    ],
    slack: [
        { key: 'webhook_url', label: 'Webhook URL', type: 'url' },
    ],
    discord: [
        { key: 'webhook_url', label: 'Webhook URL', type: 'url' },
    ],
    gotify: [
        { key: 'server_url', label: 'Server URL', type: 'url', placeholder: 'https://gotify.example.com' },
        { key: 'app_token', label: 'App Token', type: 'text' },
        { key: 'priority', label: 'Priorität', type: 'number', placeholder: '5' },
    ],
};

async function loadChannels() {
    const channels = await api('/api/channels');
    const list = document.getElementById('channelsList');
    if (!channels.length) {
        list.innerHTML = '<div class="card"><p class="hint" style="margin:0">Noch keine Kanäle konfiguriert. Fügen Sie einen hinzu!</p></div>';
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
                <button class="btn btn-sm btn-secondary" onclick="testChannel(${ch.id})">Test</button>
                <button class="btn btn-sm btn-secondary" onclick="editChannel(${ch.id})">Bearbeiten</button>
                <button class="btn btn-sm btn-danger" onclick="deleteChannel(${ch.id})">Löschen</button>
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
    document.getElementById('channelModalTitle').textContent = 'Kanal hinzufügen';
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
    document.getElementById('channelModalTitle').textContent = 'Kanal bearbeiten';
    updateChannelFields(ch.config || {});
    openModal('channelModal');
}

function updateChannelFields(existingConfig = {}) {
    const type = document.getElementById('channelType').value;
    const fields = CHANNEL_FIELDS[type] || [];
    const container = document.getElementById('channelConfigFields');
    container.innerHTML = fields.map(f => {
        const val = existingConfig[f.key] ?? f.default ?? '';
        if (f.type === 'checkbox') {
            return `<div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="cfg_${f.key}" ${val ? 'checked' : ''}>
                    ${esc(f.label)}
                </label>
            </div>`;
        }
        return `<div class="form-group">
            <label>${esc(f.label)}</label>
            <input type="${f.type}" id="cfg_${f.key}" value="${esc(String(val))}" placeholder="${esc(f.placeholder || '')}">
        </div>`;
    }).join('');
}

async function saveChannel(e) {
    e.preventDefault();
    const type = document.getElementById('channelType').value;
    const fields = CHANNEL_FIELDS[type] || [];
    const config = {};
    fields.forEach(f => {
        const el = document.getElementById('cfg_' + f.key);
        config[f.key] = f.type === 'checkbox' ? el.checked : el.value;
    });
    const data = {
        id: document.getElementById('channelId').value || undefined,
        type,
        name: document.getElementById('channelName').value,
        enabled: document.getElementById('channelEnabled').checked ? 1 : 0,
        config,
    };
    await api('/api/channels', 'POST', data);
    closeModal('channelModal');
    toast('Kanal gespeichert!', 'success');
    loadChannels();
}

async function deleteChannel(id) {
    if (!confirm('Kanal wirklich löschen?')) return;
    await api('/api/channels/' + id, 'DELETE');
    toast('Kanal gelöscht.', 'success');
    loadChannels();
}

async function testChannel(id) {
    toast('Sende Testnachricht...', 'info');
    const data = await api('/api/channels/' + id + '/test', 'POST');
    toast(data.message || (data.ok ? 'Gesendet!' : 'Fehler'), data.ok ? 'success' : 'error');
}

// Products
async function loadProducts() {
    try {
        const data = await api('/api/products');
        if (data.error) { toast(data.error, 'error'); return; }
        const tbody = document.querySelector('#tableProducts tbody');
        const products = data.products || [];
        if (!products.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="5">Keine Produkte gefunden. Bitte Grocy konfigurieren.</td></tr>';
            return;
        }
        tbody.innerHTML = products.map(p => `
            <tr>
                <td>${esc(p.name)}</td>
                <td>${p.amount}</td>
                <td>${p.best_before_date || '-'}</td>
                <td>
                    <input type="number" min="1" max="365" value="${p.custom_days || ''}"
                        style="width:80px" placeholder="Standard"
                        data-pid="${p.product_id}" data-pname="${esc(p.name)}"
                        onchange="saveOverride(this)">
                </td>
                <td>
                    ${p.custom_days ? '<button class="btn btn-sm btn-secondary" onclick="removeOverride(' + p.product_id + ')">Reset</button>' : ''}
                </td>
            </tr>
        `).join('');
    } catch (e) {
        toast('Fehler: ' + e.message, 'error');
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
    toast('Warntage gespeichert.', 'success');
}

async function removeOverride(pid) {
    await api('/api/products/override', 'POST', { product_id: pid, delete: true });
    toast('Override entfernt.', 'success');
    loadProducts();
}

// Log
async function loadLog() {
    const log = await api('/api/log');
    const tbody = document.querySelector('#tableLog tbody');
    if (!log.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Keine Log-Einträge vorhanden.</td></tr>';
        return;
    }
    tbody.innerHTML = log.map(l => `
        <tr>
            <td>${esc(l.timestamp)}</td>
            <td>${esc(l.product_name || '-')}</td>
            <td>${esc(l.notification_type)}</td>
            <td>${esc(l.channel_name)}</td>
            <td>${esc(l.message)}</td>
            <td>${l.success ? '<span style="color:var(--success)">OK</span>' : '<span style="color:var(--danger)">Fehler</span>'}</td>
        </tr>
    `).join('');
}

async function clearLog() {
    if (!confirm('Log wirklich leeren?')) return;
    await api('/api/log', 'DELETE');
    toast('Log geleert.', 'success');
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
    });
    toast('Einstellungen gespeichert!', 'success');
}

async function testConnection() {
    const status = document.getElementById('connectionStatus');
    status.textContent = 'Teste...';
    status.style.color = 'var(--text-muted)';
    const data = await api('/api/test-connection', 'POST', {
        grocy_url: document.getElementById('setGrocyUrl').value,
        grocy_api_key: document.getElementById('setApiKey').value,
    });
    status.textContent = data.message;
    status.style.color = data.ok ? 'var(--success)' : 'var(--danger)';
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
