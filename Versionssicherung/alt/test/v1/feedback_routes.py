"""
Feedback-Modul fuer Grocylink
Ermoeglicht Bug Reports und Feature Requests direkt aus der App,
ohne dass ein GitHub-Account benoetigt wird.

Integration in app.py:
    from feedback_routes import feedback_bp
    app.register_blueprint(feedback_bp)
"""

import logging
from flask import Blueprint, request, jsonify
from database import get_db

logger = logging.getLogger(__name__)

feedback_bp = Blueprint('feedback', __name__)


def init_feedback_db():
    """Erstellt die Feedback-Tabelle falls nicht vorhanden."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'bug',
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            contact TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_note TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()


@feedback_bp.route('/api/feedback', methods=['GET'])
def api_get_feedback():
    """Alle Feedback-Eintraege abrufen (fuer Admin-Ansicht)."""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM feedback ORDER BY created_at DESC LIMIT 200'
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@feedback_bp.route('/api/feedback', methods=['POST'])
def api_submit_feedback():
    """Neues Feedback einreichen."""
    data = request.get_json()

    fb_type = data.get('type', 'bug')
    subject = (data.get('subject') or '').strip()
    description = (data.get('description') or '').strip()
    contact = (data.get('contact') or '').strip()

    if not subject:
        return jsonify({'ok': False, 'message': 'Betreff ist erforderlich'}), 400
    if not description:
        return jsonify({'ok': False, 'message': 'Beschreibung ist erforderlich'}), 400
    if fb_type not in ('bug', 'feature'):
        fb_type = 'bug'

    conn = get_db()
    conn.execute(
        'INSERT INTO feedback (type, subject, description, contact) VALUES (?, ?, ?, ?)',
        (fb_type, subject, description, contact)
    )
    conn.commit()
    conn.close()

    logger.info(f"Neues Feedback: [{fb_type}] {subject}")

    # Optional: Benachrichtigung an konfigurierte Kanaele senden
    try:
        _notify_admin(fb_type, subject, description, contact)
    except Exception as e:
        logger.warning(f"Feedback-Benachrichtigung fehlgeschlagen: {e}")

    return jsonify({'ok': True, 'message': 'Feedback eingereicht'})


@feedback_bp.route('/api/feedback/<int:feedback_id>', methods=['PATCH'])
def api_update_feedback(feedback_id):
    """Feedback-Status oder Admin-Notiz aktualisieren."""
    data = request.get_json()
    conn = get_db()

    updates = []
    params = []

    if 'status' in data and data['status'] in ('open', 'in_progress', 'closed'):
        updates.append('status = ?')
        params.append(data['status'])

    if 'admin_note' in data:
        updates.append('admin_note = ?')
        params.append(data['admin_note'])

    if not updates:
        conn.close()
        return jsonify({'ok': False, 'message': 'Keine Aenderungen'}), 400

    params.append(feedback_id)
    conn.execute(f"UPDATE feedback SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    return jsonify({'ok': True})


@feedback_bp.route('/api/feedback/<int:feedback_id>', methods=['DELETE'])
def api_delete_feedback(feedback_id):
    """Feedback-Eintrag loeschen."""
    conn = get_db()
    conn.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


def _notify_admin(fb_type, subject, description, contact):
    """Sendet eine Benachrichtigung ueber den ersten aktiven Kanal."""
    from database import get_channels_decrypted, get_all_settings
    from notifiers import get_notifier
    import json

    settings = get_all_settings()
    if settings.get('feedback_notify', '0') != '1':
        return

    channels = get_channels_decrypted()
    if not channels:
        return

    ch = channels[0]
    config = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
    notifier = get_notifier(ch['type'], config)

    type_label = 'Bug Report' if fb_type == 'bug' else 'Feature Request'
    contact_info = f"\nKontakt: {contact}" if contact else ''
    message = f"[Grocylink Feedback] {type_label}\n\nBetreff: {subject}\n\n{description}{contact_info}"

    notifier.send('Grocylink Feedback', message)
