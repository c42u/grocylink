import sqlite3
import json
import os
from crypto import (
    encrypt, decrypt, encrypt_channel_config, decrypt_channel_config,
    SENSITIVE_SETTINGS
)

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'grocy_notify.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    # WAL-Checkpoint: eventuelle alte WAL-Daten in die Haupt-DB schreiben
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            config_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS product_overrides (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            custom_days_before_expiry INTEGER NOT NULL,
            custom_repeat_limit INTEGER
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            product_name TEXT,
            notification_type TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            message TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS notification_tracker (
            product_id TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            best_before_date TEXT NOT NULL DEFAULT '',
            sent_count INTEGER NOT NULL DEFAULT 0,
            first_sent TEXT NOT NULL DEFAULT (datetime('now')),
            last_sent TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (product_id, notification_type)
        );

        CREATE TABLE IF NOT EXISTS caldav_sync_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grocy_type TEXT NOT NULL,
            grocy_id INTEGER NOT NULL,
            caldav_uid TEXT NOT NULL,
            last_synced TEXT NOT NULL DEFAULT (datetime('now')),
            last_status TEXT NOT NULL DEFAULT 'pending',
            last_summary TEXT,
            last_due TEXT,
            sync_direction TEXT NOT NULL DEFAULT '',
            UNIQUE(grocy_type, grocy_id)
        );

        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_review',
            extraction_method TEXT,
            store_name TEXT,
            receipt_date TEXT,
            total_amount REAL,
            raw_text TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            confirmed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS receipt_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER NOT NULL,
            raw_name TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 1,
            unit_price REAL,
            total_price REAL,
            tax_category TEXT,
            matched_product_id INTEGER,
            matched_product_name TEXT,
            match_score REAL,
            match_source TEXT,
            confirmed INTEGER NOT NULL DEFAULT 0,
            added_to_grocy INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS receipt_product_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_name TEXT UNIQUE NOT NULL,
            grocy_product_id INTEGER NOT NULL,
            grocy_product_name TEXT NOT NULL,
            use_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_used TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    # Migrationen: fehlende Spalten nachträglich hinzufügen
    for migration in [
        "ALTER TABLE caldav_sync_map ADD COLUMN sync_direction TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE product_overrides ADD COLUMN custom_repeat_limit INTEGER",
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass
    defaults = {
        'grocy_url': '',
        'grocy_api_key': '',
        'default_days_before_expiry': '5',
        'check_interval_hours': '6',
        'notify_expiring': '1',
        'notify_expired': '1',
        'notify_missing': '1',
        'grocy_verify_ssl': '1',
        'caldav_url': '',
        'caldav_username': '',
        'caldav_password': '',
        'caldav_path': '',
        'caldav_calendar': '',
        'caldav_verify_ssl': '1',
        'notification_repeat_limit': '1',
        'notify_product_groups': '',
        'notify_locations': '',
        'caldav_sync_enabled': '0',
        'caldav_sync_interval_minutes': '30',
        'language': 'de',
        'receipt_watch_folder': '/app/receipts',
        'receipt_watch_enabled': '0',
        'receipt_watch_interval_minutes': '5',
        'receipt_match_threshold': '70',
        'receipt_auto_confirm_threshold': '95',
        'receipt_default_location': '',
        'receipt_default_product_group': '',
        'receipt_default_qu_id': '',
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    conn.close()
    _check_encryption_integrity()


def _check_encryption_integrity():
    """Prueft ob der Encryption Key zu den gespeicherten Daten passt."""
    import logging
    logger = logging.getLogger(__name__)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'grocy_api_key'"
        ).fetchone()
        if row and row['value'] and row['value'] != '':
            decrypted = decrypt(row['value'])
            if decrypted == row['value'] and row['value'].startswith('gAAAAA'):
                logger.error(
                    "WARNUNG: Encryption Key passt nicht zur Datenbank! "
                    "Verschluesselte Werte (API-Keys, Passwoerter, Kanalkonfigurationen) "
                    "koennen nicht entschluesselt werden. Bitte alle Zugangsdaten neu eingeben."
                )
        channels = conn.execute("SELECT COUNT(*) as cnt FROM notification_channels").fetchone()
        logger.info(f"Datenbank geladen: {channels['cnt']} Benachrichtigungskanaele konfiguriert")
    except Exception as e:
        logger.warning(f"Integritaetspruefung fehlgeschlagen: {e}")
    finally:
        conn.close()


def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    if not row:
        return None
    value = row['value']
    if key in SENSITIVE_SETTINGS:
        value = decrypt(value)
    return value


def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    result = {}
    for row in rows:
        value = row['value']
        if row['key'] in SENSITIVE_SETTINGS:
            value = decrypt(value)
        result[row['key']] = value
    return result


def save_settings(settings_dict):
    conn = get_db()
    for key, value in settings_dict.items():
        store_value = str(value)
        if key in SENSITIVE_SETTINGS and store_value:
            store_value = encrypt(store_value)
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, store_value)
        )
    conn.commit()
    conn.close()


def get_channels():
    conn = get_db()
    rows = conn.execute("SELECT * FROM notification_channels ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_channels_decrypted():
    channels = get_channels()
    for ch in channels:
        config = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
        ch['config_json'] = json.dumps(decrypt_channel_config(config))
    return channels


def save_channel(channel):
    conn = get_db()
    config = channel.get('config', {})
    encrypted_config = encrypt_channel_config(config)
    if channel.get('id'):
        conn.execute(
            "UPDATE notification_channels SET type=?, name=?, enabled=?, config_json=? WHERE id=?",
            (channel['type'], channel['name'], channel['enabled'],
             json.dumps(encrypted_config), channel['id'])
        )
    else:
        conn.execute(
            "INSERT INTO notification_channels (type, name, enabled, config_json) VALUES (?, ?, ?, ?)",
            (channel['type'], channel['name'], channel.get('enabled', 1),
             json.dumps(encrypted_config))
        )
    conn.commit()
    conn.close()


def delete_channel(channel_id):
    conn = get_db()
    conn.execute("DELETE FROM notification_channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()


def get_product_overrides():
    conn = get_db()
    rows = conn.execute("SELECT * FROM product_overrides ORDER BY product_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_product_override(product_id, product_name, days, repeat_limit=None):
    """Speichert ein Produkt-Override. days=-1 bedeutet 'globalen Standard verwenden'.
    repeat_limit=None bedeutet 'globales Wiederholungslimit verwenden'."""
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO product_overrides "
        "(product_id, product_name, custom_days_before_expiry, custom_repeat_limit) VALUES (?, ?, ?, ?)",
        (product_id, product_name, days, repeat_limit)
    )
    conn.commit()
    conn.close()


def delete_product_override(product_id):
    conn = get_db()
    conn.execute("DELETE FROM product_overrides WHERE product_id = ?", (product_id,))
    conn.commit()
    conn.close()


def add_log_entry(product_name, notification_type, channel_name, message, success=True):
    conn = get_db()
    conn.execute(
        "INSERT INTO notification_log (product_name, notification_type, channel_name, message, success) VALUES (?, ?, ?, ?, ?)",
        (product_name, notification_type, channel_name, message, 1 if success else 0)
    )
    conn.commit()
    conn.close()


def get_log(limit=100):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notification_log ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_log():
    conn = get_db()
    conn.execute("DELETE FROM notification_log")
    conn.commit()
    conn.close()


def clear_sync_map():
    conn = get_db()
    conn.execute("DELETE FROM caldav_sync_map")
    conn.commit()
    conn.close()


def get_sync_map():
    conn = get_db()
    rows = conn.execute("SELECT * FROM caldav_sync_map ORDER BY grocy_type, grocy_id").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if 'sync_direction' not in d:
            d['sync_direction'] = ''
        result.append(d)
    return result


def get_sync_entry(grocy_type, grocy_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM caldav_sync_map WHERE grocy_type = ? AND grocy_id = ?",
        (grocy_type, grocy_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sync_entry_by_uid(caldav_uid):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM caldav_sync_map WHERE caldav_uid = ?",
        (caldav_uid,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_sync_entry(grocy_type, grocy_id, caldav_uid, status, summary=None, due=None, direction=''):
    conn = get_db()
    conn.execute(
        """INSERT INTO caldav_sync_map (grocy_type, grocy_id, caldav_uid, last_status, last_summary, last_due, last_synced, sync_direction)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
           ON CONFLICT(grocy_type, grocy_id) DO UPDATE SET
             caldav_uid=excluded.caldav_uid,
             last_status=excluded.last_status,
             last_summary=excluded.last_summary,
             last_due=excluded.last_due,
             last_synced=datetime('now'),
             sync_direction=excluded.sync_direction""",
        (grocy_type, grocy_id, caldav_uid, status, summary, due, direction)
    )
    conn.commit()
    conn.close()


def delete_sync_entry(grocy_type, grocy_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM caldav_sync_map WHERE grocy_type = ? AND grocy_id = ?",
        (grocy_type, grocy_id)
    )
    conn.commit()
    conn.close()


def get_tracker_entry(product_id, notification_type):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM notification_tracker WHERE product_id = ? AND notification_type = ?",
        (str(product_id), notification_type)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_tracker_entry(product_id, notification_type, best_before_date):
    conn = get_db()
    existing = conn.execute(
        "SELECT best_before_date, sent_count FROM notification_tracker WHERE product_id = ? AND notification_type = ?",
        (str(product_id), notification_type)
    ).fetchone()
    if existing and existing['best_before_date'] == best_before_date:
        conn.execute(
            "UPDATE notification_tracker SET sent_count = sent_count + 1, last_sent = datetime('now') "
            "WHERE product_id = ? AND notification_type = ?",
            (str(product_id), notification_type)
        )
    else:
        conn.execute(
            "INSERT OR REPLACE INTO notification_tracker "
            "(product_id, notification_type, best_before_date, sent_count, first_sent, last_sent) "
            "VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))",
            (str(product_id), notification_type, best_before_date)
        )
    conn.commit()
    conn.close()


def cleanup_tracker(active_keys):
    """Entfernt Tracker-Eintraege fuer Produkte, die nicht mehr im Alert-Zustand sind."""
    if not active_keys:
        conn = get_db()
        conn.execute("DELETE FROM notification_tracker")
        conn.commit()
        conn.close()
        return
    conn = get_db()
    rows = conn.execute("SELECT product_id, notification_type FROM notification_tracker").fetchall()
    to_delete = [(r['product_id'], r['notification_type']) for r in rows
                 if (r['product_id'], r['notification_type']) not in active_keys]
    for pid, ntype in to_delete:
        conn.execute(
            "DELETE FROM notification_tracker WHERE product_id = ? AND notification_type = ?",
            (pid, ntype)
        )
    if to_delete:
        conn.commit()
    conn.close()


# ── Kassenbon-Funktionen ──────────────────────────────────────────────

def save_receipt(filename, filepath, status='pending_review', extraction_method=None,
                 store_name=None, receipt_date=None, total_amount=None, raw_text=None,
                 error_message=None):
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO receipts (filename, filepath, status, extraction_method,
           store_name, receipt_date, total_amount, raw_text, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (filename, filepath, status, extraction_method, store_name, receipt_date,
         total_amount, raw_text, error_message)
    )
    receipt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return receipt_id


def get_receipts():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM receipts ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_receipt(receipt_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    if not row:
        conn.close()
        return None
    receipt = dict(row)
    items = conn.execute(
        "SELECT * FROM receipt_items WHERE receipt_id = ? ORDER BY id", (receipt_id,)
    ).fetchall()
    receipt['items'] = [dict(i) for i in items]
    conn.close()
    return receipt


def update_receipt_status(receipt_id, status, error_message=None):
    conn = get_db()
    if status == 'confirmed':
        conn.execute(
            "UPDATE receipts SET status = ?, confirmed_at = datetime('now') WHERE id = ?",
            (status, receipt_id)
        )
    elif error_message:
        conn.execute(
            "UPDATE receipts SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, receipt_id)
        )
    else:
        conn.execute(
            "UPDATE receipts SET status = ? WHERE id = ?",
            (status, receipt_id)
        )
    conn.commit()
    conn.close()


def delete_receipt(receipt_id):
    conn = get_db()
    conn.execute("DELETE FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
    conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
    conn.commit()
    conn.close()


def save_receipt_items(receipt_id, items):
    conn = get_db()
    conn.execute("DELETE FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
    for item in items:
        conn.execute(
            """INSERT INTO receipt_items (receipt_id, raw_name, quantity, unit_price,
               total_price, tax_category, matched_product_id, matched_product_name,
               match_score, match_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (receipt_id, item.get('raw_name', ''), item.get('quantity', 1),
             item.get('unit_price'), item.get('total_price'), item.get('tax_category'),
             item.get('matched_product_id'), item.get('matched_product_name'),
             item.get('match_score'), item.get('match_source'))
        )
    conn.commit()
    conn.close()


def update_receipt_item(item_id, matched_product_id, matched_product_name,
                        match_score=100, match_source='manual'):
    conn = get_db()
    conn.execute(
        """UPDATE receipt_items SET matched_product_id = ?, matched_product_name = ?,
           match_score = ?, match_source = ?, confirmed = 1 WHERE id = ?""",
        (matched_product_id, matched_product_name, match_score, match_source, item_id)
    )
    conn.commit()
    conn.close()


def get_receipt_item(item_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM receipt_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_product_mappings_dict():
    conn = get_db()
    rows = conn.execute("SELECT * FROM receipt_product_mappings").fetchall()
    conn.close()
    return {r['receipt_name']: dict(r) for r in rows}


def get_product_mappings():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM receipt_product_mappings ORDER BY use_count DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_product_mapping(receipt_name, grocy_product_id, grocy_product_name):
    conn = get_db()
    conn.execute(
        """INSERT INTO receipt_product_mappings (receipt_name, grocy_product_id, grocy_product_name)
           VALUES (?, ?, ?)
           ON CONFLICT(receipt_name) DO UPDATE SET
             grocy_product_id = excluded.grocy_product_id,
             grocy_product_name = excluded.grocy_product_name,
             use_count = use_count + 1,
             last_used = datetime('now')""",
        (receipt_name, grocy_product_id, grocy_product_name)
    )
    conn.commit()
    conn.close()


def delete_product_mapping(mapping_id):
    conn = get_db()
    conn.execute("DELETE FROM receipt_product_mappings WHERE id = ?", (mapping_id,))
    conn.commit()
    conn.close()


def receipt_filepath_exists(filepath):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM receipts WHERE filepath = ?", (filepath,)
    ).fetchone()
    conn.close()
    return row is not None
