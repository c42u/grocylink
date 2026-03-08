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
    else if (page === 'receipts') loadReceipts();
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
        tbody.innerHTML = '<tr class="empty-row"><td colspan="3">' + esc(t('dash.no_entries')) + '</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const p = item.product || item;
        const pid = item.id || item.product_id || (item.product && item.product.id) || '';
        const pname = p.name || item.name || t('dash.unknown');
        return `<tr>
            <td>${esc(pname)}</td>
            <td>${item.amount_missing || '-'}</td>
            <td><button class="btn btn-sm btn-primary" onclick="openAddStockModal(this)" data-pid="${esc(String(pid))}" data-pname="${esc(pname)}">${esc(t('dash.add_stock'))}</button></td>
        </tr>`;
    }).join('');
}

function openAddStockModal(btn) {
    document.getElementById('addStockProductId').value = btn.dataset.pid;
    document.getElementById('addStockTitle').textContent = t('dash.add_stock') + ': ' + btn.dataset.pname;
    document.getElementById('addStockAmount').value = '';
    document.getElementById('addStockBestBefore').value = '';
    document.getElementById('addStockPrice').value = '';
    document.getElementById('addStockModal').style.display = 'flex';
    setTimeout(() => document.getElementById('addStockAmount').focus(), 50);
}

function closeAddStockModal() {
    document.getElementById('addStockModal').style.display = 'none';
}

async function submitAddStock() {
    const productId = document.getElementById('addStockProductId').value;
    const amount = parseFloat(document.getElementById('addStockAmount').value);
    if (!productId || isNaN(amount) || amount <= 0) return;
    const bestBefore = document.getElementById('addStockBestBefore').value || null;
    const priceVal = document.getElementById('addStockPrice').value;
    const price = priceVal ? parseFloat(priceVal) : null;
    try {
        await api('/api/grocy/stock/add', 'POST', {
            product_id: productId, amount,
            best_before_date: bestBefore,
            price,
        });
        toast(t('dash.stock_added'), 'success');
        closeAddStockModal();
        loadDashboard();
    } catch (e) {
        toast(t('dash.stock_error') + ': ' + e.message, 'error');
    }
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
        tbody.innerHTML = products.map(p => {
            const hasDays = p.custom_days !== undefined && p.custom_days !== null;
            const hasRepeat = p.custom_repeat_limit !== undefined && p.custom_repeat_limit !== null;
            const hasOverride = hasDays || hasRepeat;
            return `
            <tr>
                <td>${esc(p.name)}</td>
                <td>${p.amount !== '-' && p.amount !== null ? p.amount : '-'}</td>
                <td>${p.best_before_date || '-'}</td>
                <td>
                    <input type="number" class="days-override-input" min="0" max="365"
                        value="${hasDays ? p.custom_days : ''}"
                        style="width:120px" placeholder="${esc(t('prod.placeholder'))}"
                        data-pid="${p.product_id}" data-pname="${esc(p.name)}"
                        onchange="saveProductOverride(this)">
                </td>
                <td>
                    <input type="number" class="repeat-override-input" min="0" max="999"
                        value="${hasRepeat ? p.custom_repeat_limit : ''}"
                        style="width:120px" placeholder="${esc(t('prod.repeat_ph'))}"
                        data-pid="${p.product_id}" data-pname="${esc(p.name)}"
                        onchange="saveProductOverride(this)">
                </td>
                <td>
                    ${hasOverride ? '<button class="btn btn-sm btn-secondary" onclick="removeProductOverride(' + p.product_id + ')">' + esc(t('prod.reset')) + '</button>' : ''}
                </td>
            </tr>`;
        }).join('');
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

async function saveProductOverride(el) {
    const row = el.closest('tr');
    const daysInput = row.querySelector('.days-override-input');
    const repeatInput = row.querySelector('.repeat-override-input');
    const pid = parseInt(el.dataset.pid);
    const pname = el.dataset.pname;

    const daysVal = daysInput ? daysInput.value.trim() : '';
    const repeatVal = repeatInput ? repeatInput.value.trim() : '';

    if (daysVal === '' && repeatVal === '') {
        // Beide leer → Override entfernen
        await api('/api/products/override', 'POST', { product_id: pid, delete: true });
        toast(t('prod.override_removed'), 'success');
    } else {
        // -1 als Sentinel: "globalen Standard-Warntag verwenden"
        const daysInt = daysVal !== '' ? parseInt(daysVal) : -1;
        const repeatInt = repeatVal !== '' ? parseInt(repeatVal) : null;
        if (isNaN(daysInt) || (repeatInt !== null && isNaN(repeatInt))) return;
        await api('/api/products/override', 'POST', {
            product_id: pid,
            product_name: pname,
            days: daysInt,
            repeat_limit: repeatInt,
        });
        toast(t('prod.saved'), 'success');
    }
    loadProducts();
}

async function removeProductOverride(pid) {
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
    document.getElementById('setRepeatLimit').value = s.notification_repeat_limit !== undefined ? s.notification_repeat_limit : '1';
    const langSel = document.getElementById('langSelect');
    if (langSel) langSel.value = currentLang;
    document.getElementById('setReceiptFolder').value = s.receipt_watch_folder || '/app/receipts';
    document.getElementById('setReceiptInterval').value = s.receipt_watch_interval_minutes || 5;
    document.getElementById('setReceiptThreshold').value = s.receipt_match_threshold || 70;
    document.getElementById('setReceiptAutoThreshold').value = s.receipt_auto_confirm_threshold || 95;
    document.getElementById('setReceiptWatch').checked = s.receipt_watch_enabled === '1';
    const groupIds = (s.notify_product_groups || '').split(',').filter(x => x.trim());
    const locationIds = (s.notify_locations || '').split(',').filter(x => x.trim());
    loadFilterGroups(groupIds);
    loadFilterLocations(locationIds);
    loadReceiptDefaults(s);
}

async function loadReceiptDefaults(s) {
    await loadGrocyMetadata();
    // Kategorien
    const grpSel = document.getElementById('setReceiptDefaultGroup');
    if (grpSel) {
        grpSel.innerHTML = '<option value="">--</option>' + (window._grocyProductGroups || [])
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
            .map(g => '<option value="' + g.id + '"' + (String(g.id) === s.receipt_default_product_group ? ' selected' : '') + '>' + esc(g.name) + '</option>')
            .join('');
    }
    // Lagerorte
    const locSel = document.getElementById('setReceiptDefaultLocation');
    if (locSel) {
        locSel.innerHTML = '<option value="">--</option>' + (window._grocyLocations || [])
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
            .map(l => '<option value="' + l.id + '"' + (String(l.id) === s.receipt_default_location ? ' selected' : '') + '>' + esc(l.name) + '</option>')
            .join('');
    }
    // Mengeneinheiten
    const quSel = document.getElementById('setReceiptDefaultQu');
    if (quSel) {
        quSel.innerHTML = '<option value="">--</option>' + (window._grocyQuantityUnits || [])
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
            .map(u => '<option value="' + u.id + '"' + (String(u.id) === s.receipt_default_qu_id ? ' selected' : '') + '>' + esc(u.name) + '</option>')
            .join('');
    }
}

async function loadFilterGroups(selectedIds) {
    const container = document.getElementById('filterGroupsContainer');
    if (!container) return;
    container.innerHTML = '<span class="text-muted">' + t('set.filter_loading') + '</span>';
    try {
        const groups = await api('/api/grocy/product-groups');
        if (!Array.isArray(groups) || !groups.length) {
            container.innerHTML = '<span class="text-muted">-</span>';
            return;
        }
        // Alphabetisch sortieren
        groups.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        container.innerHTML = groups.map(g =>
            `<label><input type="checkbox" value="${esc(String(g.id))}" ${selectedIds.includes(String(g.id)) ? 'checked' : ''}> ${esc(g.name)}</label>`
        ).join('');
    } catch (e) {
        container.innerHTML = '<span class="text-muted">' + t('set.filter_error') + '</span>';
    }
}

async function loadFilterLocations(selectedIds) {
    const container = document.getElementById('filterLocationsContainer');
    if (!container) return;
    container.innerHTML = '<span class="text-muted">' + t('set.filter_loading') + '</span>';
    try {
        const locations = await api('/api/grocy/locations');
        if (!Array.isArray(locations) || !locations.length) {
            container.innerHTML = '<span class="text-muted">-</span>';
            return;
        }
        // Alphabetisch sortieren
        locations.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        container.innerHTML = locations.map(l =>
            `<label><input type="checkbox" value="${esc(String(l.id))}" ${selectedIds.includes(String(l.id)) ? 'checked' : ''}> ${esc(l.name)}</label>`
        ).join('');
    } catch (e) {
        container.innerHTML = '<span class="text-muted">' + t('set.filter_error') + '</span>';
    }
}

function getSelectedFilterIds(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return '';
    return Array.from(container.querySelectorAll('input[type=checkbox]:checked')).map(cb => cb.value).join(',');
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
        notify_product_groups: getSelectedFilterIds('filterGroupsContainer'),
        notify_locations: getSelectedFilterIds('filterLocationsContainer'),
        receipt_watch_folder: document.getElementById('setReceiptFolder').value,
        receipt_watch_interval_minutes: document.getElementById('setReceiptInterval').value,
        receipt_match_threshold: document.getElementById('setReceiptThreshold').value,
        receipt_auto_confirm_threshold: document.getElementById('setReceiptAutoThreshold').value,
        receipt_watch_enabled: document.getElementById('setReceiptWatch').checked ? '1' : '0',
        receipt_default_product_group: document.getElementById('setReceiptDefaultGroup')?.value || '',
        receipt_default_location: document.getElementById('setReceiptDefaultLocation')?.value || '',
        receipt_default_qu_id: document.getElementById('setReceiptDefaultQu')?.value || '',
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

// ── Kassenbons ──────────────────────────────────────────────────────

window._currentReceiptId = null;
window._grocyProducts = [];

const RECEIPT_STATUS_LABELS = {
    'pending_review': 'rcpt.status_pending',
    'confirmed': 'rcpt.status_confirmed',
    'rejected': 'rcpt.status_rejected',
    'error': 'rcpt.status_error',
};
const RECEIPT_STATUS_COLORS = {
    'pending_review': 'var(--warning)',
    'confirmed': 'var(--success)',
    'rejected': 'var(--text-muted)',
    'error': 'var(--danger)',
};

async function loadReceipts() {
    try {
        const receipts = await api('/api/receipts');
        const tbody = document.querySelector('#tableReceipts tbody');
        if (!receipts.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="7">' + esc(t('rcpt.no_receipts')) + '</td></tr>';
        } else {
            tbody.innerHTML = receipts.map(r => {
                const statusKey = RECEIPT_STATUS_LABELS[r.status] || r.status;
                const statusColor = RECEIPT_STATUS_COLORS[r.status] || 'var(--text-muted)';
                return `<tr>
                    <td>${esc(r.receipt_date || '-')}</td>
                    <td>${esc(r.filename)}</td>
                    <td>${esc(r.store_name || '-')}</td>
                    <td>-</td>
                    <td>${r.total_amount != null ? r.total_amount.toFixed(2) + ' €' : '-'}</td>
                    <td><span class="receipt-status-badge" style="background:${statusColor}">${esc(t(statusKey))}</span></td>
                    <td>
                        ${r.status === 'pending_review' ? '<button class="btn btn-sm btn-primary" onclick="openReceiptReview(' + r.id + ')">' + esc(t('rcpt.review')) + '</button> ' : ''}
                        <button class="btn btn-sm btn-secondary" onclick="reprocessReceipt(${r.id})">${esc(t('rcpt.reprocess'))}</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteReceipt(${r.id})">${esc(t('rcpt.delete'))}</button>
                    </td>
                </tr>`;
            }).join('');
        }
        loadMappings();
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

async function uploadReceipt(file) {
    const formData = new FormData();
    formData.append('file', file);
    toast(t('rcpt.uploading'), 'info');
    try {
        const resp = await fetch('/api/receipts/upload', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.ok) {
            toast(data.items_count + ' ' + t('rcpt.th_items'), 'success');
            loadReceipts();
        } else {
            toast(data.error || t('gen.error'), 'error');
        }
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

// Upload-Zone Event-Handler
(function() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('receiptFileInput');
    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());
    input.addEventListener('change', () => {
        if (input.files.length) uploadReceipt(input.files[0]);
        input.value = '';
    });

    zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length && files[0].name.toLowerCase().endsWith('.pdf')) {
            uploadReceipt(files[0]);
        }
    });
})();

async function openReceiptReview(receiptId) {
    window._currentReceiptId = receiptId;
    try {
        const receipt = await api('/api/receipts/' + receiptId);
        const info = document.getElementById('receiptReviewInfo');
        info.innerHTML = [
            receipt.store_name ? '<strong>' + esc(receipt.store_name) + '</strong>' : '',
            receipt.receipt_date || '',
            receipt.total_amount != null ? receipt.total_amount.toFixed(2) + ' €' : '',
            receipt.extraction_method ? '(' + esc(receipt.extraction_method) + ')' : '',
        ].filter(Boolean).join(' &mdash; ');

        // Grocy-Produkte laden fuer Dropdown
        if (!window._grocyProducts.length) {
            try {
                const pdata = await api('/api/products');
                window._grocyProducts = (pdata.products || []).map(p => ({ id: p.product_id, name: p.name }));
            } catch(e) { /* ignore */ }
        }

        // Grocy-Daten fuer neue Produkte vorladen
        await loadGrocyMetadata();
        const settings = await api('/api/settings');
        const defaultGroupId = settings.receipt_default_product_group || '';
        const defaultLocId = settings.receipt_default_location || '';
        const defaultQuId = settings.receipt_default_qu_id || '';

        const tbody = document.querySelector('#tableReviewItems tbody');
        const items = receipt.items || [];
        if (!items.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="5">' + esc(t('rcpt.no_receipts')) + '</td></tr>';
        } else {
            tbody.innerHTML = items.map(item => {
                const scoreClass = item.match_score >= 90 ? 'score-high' :
                                   item.match_score >= 70 ? 'score-mid' : 'score-low';

                // Produkt-Dropdown mit __NEW__ Option
                const productOptions = window._grocyProducts.map(p =>
                    '<option value="' + p.id + '"' + (p.id === item.matched_product_id ? ' selected' : '') + '>' + esc(p.name) + '</option>'
                ).join('');

                const isUnmatched = !item.matched_product_id;
                const selectValue = isUnmatched ? '__NEW__' : (item.matched_product_id || '');

                // Kategorien-Dropdown
                const groupOptions = (window._grocyProductGroups || []).map(g =>
                    '<option value="' + g.id + '"' + (String(g.id) === defaultGroupId ? ' selected' : '') + '>' + esc(g.name) + '</option>'
                ).join('');
                // Lagerorte-Dropdown
                const locOptions = (window._grocyLocations || []).map(l =>
                    '<option value="' + l.id + '"' + (String(l.id) === defaultLocId ? ' selected' : '') + '>' + esc(l.name) + '</option>'
                ).join('');
                // Mengeneinheiten-Dropdown
                const quOptions = (window._grocyQuantityUnits || []).map(u =>
                    '<option value="' + u.id + '"' + (String(u.id) === defaultQuId ? ' selected' : '') + '>' + esc(u.name) + '</option>'
                ).join('');

                return `<tr data-item-id="${item.id}">
                    <td>${esc(item.raw_name)}</td>
                    <td>${item.quantity}</td>
                    <td>${item.unit_price != null ? item.unit_price.toFixed(2) + ' €' : '-'}</td>
                    <td>
                        <select class="receipt-match-select" data-item-id="${item.id}" onchange="onItemMatchChange(this, ${receiptId})">
                            <option value="">-- ${esc(t('rcpt.search_product'))} --</option>
                            <option value="__NEW__"${isUnmatched ? ' selected' : ''}>${esc(t('rcpt.create_new'))}</option>
                            ${productOptions}
                        </select>
                        <div class="new-product-fields" data-item-id="${item.id}" style="${isUnmatched ? '' : 'display:none'}">
                            <div class="np-preview-row" data-item-id="${item.id}"></div>
                            <div class="np-field-group">
                                <span class="np-label">${esc(t('rcpt.product_name'))}</span>
                                <input type="text" class="np-name" value="${esc(item.raw_name)}" placeholder="${esc(t('rcpt.product_name'))}">
                            </div>
                            <div class="np-field-group">
                                <span class="np-label">${esc(t('rcpt.category'))}</span>
                                <select class="np-group"><option value="">${esc(t('rcpt.select_default'))}</option>${groupOptions}</select>
                            </div>
                            <div class="np-field-group">
                                <span class="np-label">${esc(t('rcpt.location'))}</span>
                                <select class="np-location"><option value="">${esc(t('rcpt.select_default'))}</option>${locOptions}</select>
                            </div>
                            <div class="np-field-group">
                                <span class="np-label">${esc(t('rcpt.quantity_unit'))}</span>
                                <select class="np-qu"><option value="">${esc(t('rcpt.select_default'))}</option>${quOptions}</select>
                            </div>
                            <div class="np-field-group">
                                <span class="np-label">${esc(t('rcpt.barcode'))}</span>
                                <select class="np-barcode-select" data-item-id="${item.id}">
                                    <option value="">${esc(t('rcpt.barcode_select'))}</option>
                                </select>
                            </div>
                            <div class="np-actions">
                                <button type="button" class="btn btn-sm btn-secondary btn-suggest" onclick="suggestCategory(${item.id})">${esc(t('rcpt.suggest_category'))}</button>
                            </div>
                        </div>
                    </td>
                    <td><span class="match-score ${scoreClass}">${item.match_score > 0 ? Math.round(item.match_score) + '%' : '-'}</span></td>
                </tr>`;
            }).join('');
        }
        openModal('receiptReviewModal');
        // Automatische Vorauswahl via OpenFoodFacts fuer ungematchte Items
        autoSuggestAll();
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

function onItemMatchChange(sel, receiptId) {
    const itemId = sel.dataset.itemId;
    const fields = document.querySelector('.new-product-fields[data-item-id="' + itemId + '"]');
    if (sel.value === '__NEW__') {
        if (fields) fields.style.display = '';
    } else {
        if (fields) fields.style.display = 'none';
        updateItemMatch(sel, receiptId);
    }
}

async function updateItemMatch(sel, receiptId) {
    const itemId = sel.dataset.itemId;
    const productId = sel.value ? parseInt(sel.value) : null;
    const productName = sel.options[sel.selectedIndex]?.text || '';
    if (!productId) return;
    try {
        await api('/api/receipts/' + receiptId + '/items/' + itemId, 'PUT', {
            matched_product_id: productId,
            matched_product_name: productName,
        });
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

// Lazy-load Grocy metadata (product groups, locations, quantity units)
async function loadGrocyMetadata() {
    if (!window._grocyProductGroups) {
        try { window._grocyProductGroups = await api('/api/grocy/product-groups'); } catch(e) { window._grocyProductGroups = []; }
    }
    if (!window._grocyLocations) {
        try { window._grocyLocations = await api('/api/grocy/locations'); } catch(e) { window._grocyLocations = []; }
    }
    if (!window._grocyQuantityUnits) {
        try { window._grocyQuantityUnits = await api('/api/grocy/quantity-units'); } catch(e) { window._grocyQuantityUnits = []; }
    }
}

async function suggestCategory(itemId) {
    const fields = document.querySelector('.new-product-fields[data-item-id="' + itemId + '"]');
    if (!fields) return;
    const nameInput = fields.querySelector('.np-name');
    const groupSelect = fields.querySelector('.np-group');
    const btn = fields.querySelector('.btn-suggest');
    const previewRow = fields.querySelector('.np-preview-row');
    const name = nameInput.value.trim();
    if (!name) return;
    btn.textContent = t('rcpt.suggesting');
    btn.disabled = true;
    try {
        const data = await api('/api/openfoodfacts/suggest', 'POST', { name });
        if (data.product_group_id) {
            groupSelect.value = String(data.product_group_id);
            btn.textContent = data.category || t('rcpt.suggest_category');
        } else {
            btn.textContent = t('rcpt.no_suggestion');
        }
        // Produktbild und Barcode anzeigen
        if (previewRow && (data.image_url || data.barcode)) {
            let html = '';
            if (data.image_url) {
                html += '<img class="np-preview-img" src="' + esc(data.image_url) + '" alt="">';
            }
            if (data.off_product_name) {
                html += '<span>' + esc(data.off_product_name) + '</span>';
            }
            if (data.barcode) {
                html += '<span class="np-barcode">EAN: ' + esc(data.barcode) + '</span>';
            }
            previewRow.innerHTML = html;
        }
        // Barcode-Dropdown befuellen via separate Suche
        searchBarcodes(itemId, name);
    } catch (e) {
        btn.textContent = t('rcpt.no_suggestion');
    }
    btn.disabled = false;
    setTimeout(() => { btn.textContent = t('rcpt.suggest_category'); }, 3000);
}

// Barcode-Suche: Dropdown mit Vorschlaegen befuellen
async function searchBarcodes(itemId, productName) {
    const fields = document.querySelector('.new-product-fields[data-item-id="' + itemId + '"]');
    if (!fields) return;
    const barcodeSelect = fields.querySelector('.np-barcode-select');
    if (!barcodeSelect) return;
    // Lade-Zustand
    barcodeSelect.innerHTML = '<option value="">' + esc(t('rcpt.barcode_searching')) + '</option>';
    try {
        const data = await api('/api/barcode/search', 'POST', { name: productName });
        const suggestions = data.suggestions || [];
        let html = '<option value="">' + esc(t('rcpt.barcode_select')) + '</option>';
        if (suggestions.length === 0) {
            html += '<option value="" disabled>' + esc(t('rcpt.barcode_none')) + '</option>';
        }
        for (const s of suggestions) {
            const label = s.barcode + ' – ' + s.product_name + ' (' + s.source + ')';
            html += '<option value="' + esc(s.barcode) + '">' + esc(label) + '</option>';
        }
        barcodeSelect.innerHTML = html;
        // Ersten Barcode automatisch vorauswaehlen wenn vorhanden
        if (suggestions.length > 0) {
            barcodeSelect.value = suggestions[0].barcode;
        }
    } catch (e) {
        barcodeSelect.innerHTML = '<option value="">' + esc(t('rcpt.barcode_none')) + '</option>';
    }
}

// Automatische Vorauswahl: fuer alle ungematchten Items den Suggest ausfuehren
async function autoSuggestAll() {
    const rows = document.querySelectorAll('#tableReviewItems tbody tr[data-item-id]');
    for (const row of rows) {
        const sel = row.querySelector('.receipt-match-select');
        if (sel && sel.value === '__NEW__') {
            const itemId = row.getAttribute('data-item-id');
            await suggestCategory(parseInt(itemId));
        }
    }
}

async function confirmCurrentReceipt() {
    if (!window._currentReceiptId) return;
    try {
        // Neue Produkte sammeln
        const newProducts = {};
        document.querySelectorAll('#tableReviewItems tbody tr[data-item-id]').forEach(row => {
            const itemId = row.getAttribute('data-item-id');
            const sel = row.querySelector('.receipt-match-select');
            if (sel && sel.value === '__NEW__') {
                const fields = row.querySelector('.new-product-fields');
                if (fields) {
                    newProducts[itemId] = {
                        name: (fields.querySelector('.np-name')?.value || '').trim(),
                        product_group_id: fields.querySelector('.np-group')?.value || null,
                        location_id: fields.querySelector('.np-location')?.value || null,
                        qu_id: fields.querySelector('.np-qu')?.value || null,
                        barcode: fields.querySelector('.np-barcode-select')?.value || null,
                    };
                }
            }
        });
        const body = Object.keys(newProducts).length ? { new_products: newProducts } : {};
        const data = await api('/api/receipts/' + window._currentReceiptId + '/confirm', 'POST', body);
        if (data.ok) {
            let msg = data.added + ' ' + t('rcpt.confirmed_count');
            if (data.created > 0) {
                msg += ', ' + data.created + ' ' + t('rcpt.created_count');
            }
            toast(msg, 'success');
            if (data.errors && data.errors.length) {
                data.errors.forEach(e => toast(e, 'error'));
            }
            closeModal('receiptReviewModal');
            loadReceipts();
            // Produkt-Cache invalidieren
            window._grocyProducts = [];
        } else {
            toast(data.error || t('rcpt.confirm_error'), 'error');
        }
    } catch (e) {
        toast(t('rcpt.confirm_error') + ': ' + e.message, 'error');
    }
}

async function rejectCurrentReceipt() {
    if (!window._currentReceiptId) return;
    await api('/api/receipts/' + window._currentReceiptId + '/reject', 'POST');
    toast(t('rcpt.rejected'), 'success');
    closeModal('receiptReviewModal');
    loadReceipts();
}

async function deleteReceipt(id) {
    if (!confirm(t('rcpt.confirm_delete'))) return;
    await api('/api/receipts/' + id, 'DELETE');
    toast(t('rcpt.deleted'), 'success');
    loadReceipts();
}

async function reprocessReceipt(id) {
    try {
        const data = await api('/api/receipts/reprocess/' + id, 'POST');
        if (data.ok) {
            toast(t('rcpt.reprocessed'), 'success');
            loadReceipts();
        } else {
            toast(data.error || t('gen.error'), 'error');
        }
    } catch (e) {
        toast(t('gen.error') + ': ' + e.message, 'error');
    }
}

async function loadMappings() {
    try {
        const mappings = await api('/api/receipts/mappings');
        const tbody = document.querySelector('#tableMappings tbody');
        if (!mappings.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="4">' + esc(t('rcpt.no_mappings')) + '</td></tr>';
            return;
        }
        tbody.innerHTML = mappings.map(m => `<tr>
            <td>${esc(m.receipt_name)}</td>
            <td>${esc(m.grocy_product_name)}</td>
            <td>${m.use_count}</td>
            <td><button class="btn btn-sm btn-danger" onclick="deleteMapping(${m.id})">${esc(t('rcpt.delete'))}</button></td>
        </tr>`).join('');
    } catch (e) {
        /* silent */
    }
}

async function deleteMapping(id) {
    await api('/api/receipts/mappings/' + id, 'DELETE');
    toast(t('rcpt.mapping_deleted'), 'success');
    loadMappings();
}

// Init
loadDashboard();
