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

        CREATE TABLE IF NOT EXISTS bring_sync_map (
            grocy_product_id INTEGER PRIMARY KEY,
            bring_item_uuid TEXT NOT NULL,
            bring_item_name TEXT NOT NULL,
            last_spec TEXT,
            last_synced TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Zugaenge fuer die App: je Geraet ein Schluessel, einzeln
        -- widerrufbar. Gespeichert wird nur der SHA-256 -- ein Schluessel, der
        -- sich aus der Datenbank zurueckholen laesst, ist kein Schluessel.
        -- (Uebernommen aus grocyplan 0.38.0, bewusst gleich aufgebaut.)
        CREATE TABLE IF NOT EXISTS api_keys (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            hash          TEXT NOT NULL UNIQUE,
            created_at    TEXT NOT NULL,
            last_used_at  TEXT,
            active        INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS bring_item_overrides (
            grocy_product_id INTEGER PRIMARY KEY,
            hide_from_bring INTEGER NOT NULL DEFAULT 0,
            custom_name TEXT,
            custom_spec TEXT
        );
    """)
    # Migrationen: fehlende Spalten nachträglich hinzufügen
    for migration in [
        "ALTER TABLE caldav_sync_map ADD COLUMN sync_direction TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE product_overrides ADD COLUMN custom_repeat_limit INTEGER",
        # Log-Eintraege sprachneutral ablegen: Schluessel + Werte statt fertigem
        # Satz. Sonst bleibt ein einmal geschriebener deutscher Text fuer immer
        # deutsch, auch wenn die Oberflaeche spaeter auf Englisch steht
        # (GitHub-Fehler #1). Der Freitext in `message` bleibt als Rueckfall --
        # fuer Ausnahmetexte und fuer alles, was vor 1.7.0 geschrieben wurde.
        "ALTER TABLE notification_log ADD COLUMN message_key TEXT",
        "ALTER TABLE notification_log ADD COLUMN message_args TEXT",
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
        # Bring!-Sync (eigener Sync-Layer, nicht Notification-Channel)
        'bring_sync_enabled': '0',
        'bring_email': '',
        'bring_password': '',
        'bring_list_uuid': '',
        'bring_sync_interval_minutes': '30',
        'bring_source': 'shopping_list',  # 'shopping_list' | 'missing'
        'bring_sync_direction': 'grocy_to_bring',  # v1: nur unidirektional
        'bring_auto_remove': '0',
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


def add_log_entry(product_name, notification_type, channel_name, message,
                  success=True, key=None, args=None):
    """Schreibt einen Eintrag ins Log der Oberflaeche.

    Args:
        message: fertiger Text -- fuer Ausnahmemeldungen, die sich nicht
            uebersetzen lassen, und als Rueckfall
        key: Schluessel aus `sprache.TEXTE`, wenn der Satz uebersetzbar ist
        args: Werte fuer die Platzhalter des Schluessels

    Mit `key` steht in der Datenbank **kein** fertiger Satz, sondern die
    Bauanleitung. Erst beim Anzeigen entsteht daraus Text -- in der Sprache,
    die dann eingestellt ist. Wer die Sprache wechselt, sieht auch alte
    Eintraege in der neuen Sprache.
    """
    conn = get_db()
    conn.execute(
        "INSERT INTO notification_log (product_name, notification_type, "
        "channel_name, message, success, message_key, message_args) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (product_name, notification_type, channel_name, message,
         1 if success else 0, key,
         json.dumps(args, ensure_ascii=False) if args else None)
    )
    conn.commit()
    conn.close()


def get_log(limit=100, lang=None):
    """Log-Eintraege, uebersetzt in die eingestellte Sprache.

    Eintraege ohne Schluessel (Ausnahmetexte, Altbestand vor 1.7.0) kommen
    unveraendert zurueck: Ein deutscher Fehlertext ist besser als gar keiner.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notification_log ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()

    import sprache
    if lang is None:
        lang = sprache.sprache_lesen()

    eintraege = []
    for r in rows:
        e = dict(r)
        if e.get('message_key'):
            try:
                werte = json.loads(e.get('message_args') or '{}')
            except ValueError:
                werte = {}
            e['message'] = sprache.t(e['message_key'], lang=lang, **werte)
        eintraege.append(e)
    return eintraege


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
    """Liefert alle Mappings als Dict: receipt_name -> mapping-Daten."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM receipt_product_mappings").fetchall()
    conn.close()
    return {r['receipt_name']: dict(r) for r in rows}


def get_mappings_by_product():
    """Liefert alle Mappings gruppiert nach grocy_product_id.

    Ergebnis: {grocy_product_id: [receipt_name1, receipt_name2, ...]}
    Damit koennen alle bekannten Bon-Namens-Varianten eines Produkts abgefragt werden.
    """
    conn = get_db()
    rows = conn.execute("SELECT grocy_product_id, receipt_name FROM receipt_product_mappings").fetchall()
    conn.close()
    result = {}
    for r in rows:
        pid = r['grocy_product_id']
        if pid not in result:
            result[pid] = []
        result[pid].append(r['receipt_name'])
    return result


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


# Bring!-Sync ----------------------------------------------------------

def get_bring_sync_map():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bring_sync_map ORDER BY bring_item_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bring_sync_entry(grocy_product_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM bring_sync_map WHERE grocy_product_id = ?",
        (int(grocy_product_id),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_bring_sync_entry(grocy_product_id, bring_item_uuid, bring_item_name, last_spec=None):
    conn = get_db()
    conn.execute(
        """INSERT INTO bring_sync_map
           (grocy_product_id, bring_item_uuid, bring_item_name, last_spec, last_synced)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(grocy_product_id) DO UPDATE SET
             bring_item_uuid = excluded.bring_item_uuid,
             bring_item_name = excluded.bring_item_name,
             last_spec = excluded.last_spec,
             last_synced = datetime('now')""",
        (int(grocy_product_id), bring_item_uuid, bring_item_name, last_spec)
    )
    conn.commit()
    conn.close()


def delete_bring_sync_entry(grocy_product_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM bring_sync_map WHERE grocy_product_id = ?",
        (int(grocy_product_id),)
    )
    conn.commit()
    conn.close()


def clear_bring_sync_map():
    conn = get_db()
    conn.execute("DELETE FROM bring_sync_map")
    conn.commit()
    conn.close()


def get_bring_overrides():
    """Liefert alle Per-Produkt-Overrides als Dict: product_id -> override-Dict."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM bring_item_overrides").fetchall()
    conn.close()
    return {r['grocy_product_id']: dict(r) for r in rows}


def get_bring_overrides_list():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bring_item_overrides ORDER BY grocy_product_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_bring_override(grocy_product_id, hide_from_bring=0, custom_name=None, custom_spec=None):
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO bring_item_overrides
           (grocy_product_id, hide_from_bring, custom_name, custom_spec)
           VALUES (?, ?, ?, ?)""",
        (int(grocy_product_id), 1 if hide_from_bring else 0,
         custom_name or None, custom_spec or None)
    )
    conn.commit()
    conn.close()


def delete_bring_override(grocy_product_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM bring_item_overrides WHERE grocy_product_id = ?",
        (int(grocy_product_id),)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Zugaenge fuer die App
#
# Der Schluessel selbst wird nie gespeichert, nur sein SHA-256. Beim Anlegen
# bekommt der Nutzer ihn einmal zu sehen; wer ihn verliert, legt einen neuen
# an. Anders als bei den Zugangsdaten in `settings` (Grocy, Bring, SMTP), die
# grocylink selbst wieder braucht und deshalb verschluesselt ablegt.
# ---------------------------------------------------------------------------

def _api_key_hash(key):
    import hashlib
    return hashlib.sha256((key or '').encode()).hexdigest()


def create_api_key(name):
    """Legt einen Zugang an und liefert den Schluessel -- einmalig."""
    import secrets
    from datetime import datetime
    key = 'gl_' + secrets.token_urlsafe(32)
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (name, hash, created_at) VALUES (?, ?, ?)",
        ((name or 'Geraet').strip()[:60], _api_key_hash(key),
         datetime.now().isoformat(timespec='seconds')))
    conn.commit()
    conn.close()
    return key


def check_api_key(key):
    """Prueft einen Schluessel und schreibt die Benutzung fort.

    Returns:
        Der Zugang als dict oder None. Ein widerrufener gilt als unbekannt.
    """
    if not key:
        return None
    from datetime import datetime
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE hash = ? AND active = 1",
        (_api_key_hash(key),)).fetchone()
    if row:
        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                     (datetime.now().isoformat(timespec='seconds'), row['id']))
        conn.commit()
    conn.close()
    return dict(row) if row else None


def get_api_keys():
    """Alle Zugaenge fuer die Oberflaeche -- ohne den Hash."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, created_at, last_used_at, active FROM api_keys "
        "ORDER BY active DESC, id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def revoke_api_key(key_id):
    """Setzt einen Zugang still. Liefert seinen Namen."""
    conn = get_db()
    row = conn.execute("SELECT name FROM api_keys WHERE id = ?",
                       (int(key_id),)).fetchone()
    conn.execute("UPDATE api_keys SET active = 0 WHERE id = ?", (int(key_id),))
    conn.commit()
    conn.close()
    return row['name'] if row else ''
