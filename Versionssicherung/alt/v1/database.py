import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'grocy_notify.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
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
            custom_days_before_expiry INTEGER NOT NULL
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
    """)
    defaults = {
        'grocy_url': '',
        'grocy_api_key': '',
        'default_days_before_expiry': '5',
        'check_interval_hours': '6',
        'notify_expiring': '1',
        'notify_expired': '1',
        'notify_missing': '1',
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else None


def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}


def save_settings(settings_dict):
    conn = get_db()
    for key, value in settings_dict.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
    conn.commit()
    conn.close()


def get_channels():
    conn = get_db()
    rows = conn.execute("SELECT * FROM notification_channels ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_channel(channel):
    conn = get_db()
    if channel.get('id'):
        conn.execute(
            "UPDATE notification_channels SET type=?, name=?, enabled=?, config_json=? WHERE id=?",
            (channel['type'], channel['name'], channel['enabled'],
             json.dumps(channel.get('config', {})), channel['id'])
        )
    else:
        conn.execute(
            "INSERT INTO notification_channels (type, name, enabled, config_json) VALUES (?, ?, ?, ?)",
            (channel['type'], channel['name'], channel.get('enabled', 1),
             json.dumps(channel.get('config', {})))
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


def save_product_override(product_id, product_name, days):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO product_overrides (product_id, product_name, custom_days_before_expiry) VALUES (?, ?, ?)",
        (product_id, product_name, days)
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
