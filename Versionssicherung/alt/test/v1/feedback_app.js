/**
 * Feedback-Modul JavaScript
 *
 * Integration in app.js:
 * 1. Diesen Code am Ende von app.js einfuegen oder als separate Datei laden
 * 2. In loadPageData() den Case 'feedback' hinzufuegen:
 *    case 'feedback': loadFeedbackList(); break;
 */

async function submitFeedback() {
    const type = document.getElementById('fbType').value;
    const subject = document.getElementById('fbSubject').value.trim();
    const description = document.getElementById('fbDescription').value.trim();
    const contact = document.getElementById('fbContact').value.trim();

    if (!subject) {
        toast(t('fb.error_subject'), 'error');
        return;
    }
    if (!description) {
        toast(t('fb.error_description'), 'error');
        return;
    }

    try {
        const res = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, subject, description, contact })
        });
        const data = await res.json();
        if (data.ok) {
            toast(t('fb.success'), 'success');
            document.getElementById('fbSubject').value = '';
            document.getElementById('fbDescription').value = '';
            document.getElementById('fbContact').value = '';
            loadFeedbackList();
        } else {
            toast(data.message || t('fb.error_generic'), 'error');
        }
    } catch (e) {
        toast(t('fb.error_generic'), 'error');
    }
}

async function loadFeedbackList() {
    try {
        const res = await fetch('/api/feedback');
        const list = await res.json();
        const tbody = document.getElementById('feedbackBody');
        if (!tbody) return;

        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="empty-state">${t('fb.empty')}</td></tr>`;
            return;
        }

        tbody.innerHTML = list.map(fb => {
            const typeLabel = fb.type === 'bug' ? t('fb.type_bug') : t('fb.type_feature');
            const typeBadge = fb.type === 'bug'
                ? '<span class="badge badge-danger">' + typeLabel + '</span>'
                : '<span class="badge badge-info">' + typeLabel + '</span>';

            const statusBadge = fb.status === 'open'
                ? `<span class="badge badge-warning">${t('fb.status_open')}</span>`
                : fb.status === 'in_progress'
                ? `<span class="badge badge-info">${t('fb.status_progress')}</span>`
                : `<span class="badge badge-success">${t('fb.status_closed')}</span>`;

            const date = fb.created_at ? new Date(fb.created_at + 'Z').toLocaleString() : '';
            const contact = fb.contact ? `<a href="mailto:${fb.contact}">${fb.contact}</a>` : '-';

            return `<tr>
                <td>${fb.id}</td>
                <td>${typeBadge}</td>
                <td title="${fb.description.replace(/"/g, '&quot;')}">${fb.subject}</td>
                <td>${statusBadge}</td>
                <td>${contact}</td>
                <td>${date}</td>
                <td>
                    <select onchange="updateFeedbackStatus(${fb.id}, this.value)" style="font-size:.85em;padding:2px 4px;">
                        <option value="open" ${fb.status === 'open' ? 'selected' : ''}>${t('fb.status_open')}</option>
                        <option value="in_progress" ${fb.status === 'in_progress' ? 'selected' : ''}>${t('fb.status_progress')}</option>
                        <option value="closed" ${fb.status === 'closed' ? 'selected' : ''}>${t('fb.status_closed')}</option>
                    </select>
                    <button class="btn btn-danger btn-sm" onclick="deleteFeedback(${fb.id})" style="margin-left:4px;padding:2px 8px;">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/></svg>
                    </button>
                </td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Feedback laden fehlgeschlagen:', e);
    }
}

async function updateFeedbackStatus(id, status) {
    try {
        await fetch(`/api/feedback/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        toast(t('fb.status_updated'), 'success');
    } catch (e) {
        toast(t('fb.error_generic'), 'error');
    }
}

async function deleteFeedback(id) {
    if (!confirm(t('fb.confirm_delete'))) return;
    try {
        await fetch(`/api/feedback/${id}`, { method: 'DELETE' });
        toast(t('fb.deleted'), 'success');
        loadFeedbackList();
    } catch (e) {
        toast(t('fb.error_generic'), 'error');
    }
}
