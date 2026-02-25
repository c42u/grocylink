import os
import base64
import hashlib
from cryptography.fernet import Fernet

KEY_PATH = os.path.join(os.path.dirname(__file__), 'data', '.encryption_key')

SENSITIVE_SETTINGS = {'grocy_api_key', 'caldav_password'}

SENSITIVE_CHANNEL_KEYS = {
    'password', 'api_token', 'user_key', 'bot_token',
    'webhook_url', 'app_token',
}


def _get_or_create_key():
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, 'rb') as f:
            return f.read()
    key = Fernet.generate_key()
    fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(key)
    return key


def _fernet():
    return Fernet(_get_or_create_key())


def encrypt(plaintext):
    if not plaintext:
        return plaintext
    return _fernet().encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt(ciphertext):
    if not ciphertext:
        return ciphertext
    try:
        return _fernet().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Entschluesselung fehlgeschlagen - Encryption Key passt nicht zum gespeicherten Wert. "
            "Moeglicherweise wurde der Key in /app/data/.encryption_key neu generiert. "
            "Betroffene Einstellungen muessen neu eingegeben werden."
        )
        return ciphertext


def encrypt_channel_config(config):
    encrypted = {}
    for k, v in config.items():
        if k in SENSITIVE_CHANNEL_KEYS and isinstance(v, str) and v:
            encrypted[k] = encrypt(v)
        else:
            encrypted[k] = v
    return encrypted


def decrypt_channel_config(config):
    decrypted = {}
    for k, v in config.items():
        if k in SENSITIVE_CHANNEL_KEYS and isinstance(v, str) and v:
            decrypted[k] = decrypt(v)
        else:
            decrypted[k] = v
    return decrypted
