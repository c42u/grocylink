"""Prueft die serverseitige Sprache (GitHub-Fehler #1).

Gemeldet war: Oberflaeche auf Englisch gestellt, aber der Toast nach "Jetzt
pruefen" und die Testnachricht an Discord kamen auf Deutsch -- und in einem
neuen Fenster stand die ganze Seite wieder auf Deutsch.
"""

import json
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sprache


# ── Die Tabelle selbst ────────────────────────────────────────────────

def test_beide_sprachen_kennen_dieselben_schluessel():
    """Ein Schluessel, der nur auf Deutsch existiert, faellt sonst nie auf."""
    assert set(sprache.TEXTE['de']) == set(sprache.TEXTE['en'])


def test_uebersetzt_nach_sprache():
    assert sprache.t('msg.check_done', lang='de') == 'Check durchgeführt!'
    assert sprache.t('msg.check_done', lang='en') == 'Check completed!'


def test_platzhalter_werden_gefuellt():
    text = sprache.t('log.bring_sync', lang='en', added=3, updated=1,
                     removed=0, errors=2)
    assert '+3 new' in text and '2 errors' in text


def test_unbekannte_sprache_faellt_auf_deutsch_zurueck():
    assert sprache.t('msg.check_done', lang='kl') == 'Check durchgeführt!'


def test_unbekannter_schluessel_wirft_nicht():
    """Ein fehlender Text darf keine Benachrichtigung ausfallen lassen."""
    assert sprache.t('gibt.es.nicht', lang='en') == 'gibt.es.nicht'


def test_fehlender_platzhalter_wirft_nicht():
    assert sprache.t('log.bring_manual', lang='en') == 'Added manually: {name}'


# ── Die Testnachricht an einen Kanal ──────────────────────────────────

def test_testnachricht_folgt_der_einstellung(monkeypatch):
    """Der Kern der Meldung: Discord bekam Deutsch trotz englischer Oberflaeche.

    Die Nachricht entsteht ohne Browser -- die Sprache kann also nur aus den
    Einstellungen kommen.
    """
    import notifiers

    monkeypatch.setattr(sprache, 'sprache_lesen', lambda: 'en')

    gesendet = []

    class Kanal(notifiers.BaseNotifier):
        def send(self, title, message):
            gesendet.append((title, message))
            return True

    Kanal({}).test()
    assert gesendet, "es wurde nichts gesendet"
    titel, text = gesendet[0]
    assert text == 'This is a test notification from Grocylink.'
    assert 'Test' in titel


# ── Log-Eintraege ─────────────────────────────────────────────────────

@pytest.fixture
def datenbank(monkeypatch):
    """Frische SQLite-Datei je Test."""
    import database
    ordner = tempfile.mkdtemp()
    pfad = os.path.join(ordner, 'test.db')
    monkeypatch.setattr(database, 'DB_PATH', pfad, raising=False)

    def get_db():
        conn = sqlite3.connect(pfad)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(database, 'get_db', get_db)
    database.init_db()
    return database


def test_logeintrag_wechselt_die_sprache_mit(datenbank, monkeypatch):
    """Auch **alte** Eintraege erscheinen in der neu gewaehlten Sprache.

    Deshalb steht in der Datenbank der Schluessel und nicht der fertige Satz.
    """
    datenbank.add_log_entry(None, 'test', 'Discord',
                            sprache.t('log.test_sent', lang='de'),
                            key='log.test_sent')

    deutsch = datenbank.get_log(lang='de')[0]['message']
    englisch = datenbank.get_log(lang='en')[0]['message']
    assert deutsch == 'Testnachricht erfolgreich gesendet'
    assert englisch == 'Test notification sent successfully'


def test_logeintrag_mit_werten(datenbank):
    werte = {'added': 2, 'updated': 1, 'removed': 0, 'errors': 0}
    datenbank.add_log_entry(None, 'bring_sync', 'Bring!',
                            sprache.t('log.bring_sync', **werte),
                            key='log.bring_sync', args=werte)
    text = datenbank.get_log(lang='en')[0]['message']
    assert '+2 new' in text and '1 updated' in text


def test_eintrag_ohne_schluessel_bleibt_wie_er_ist(datenbank):
    """Ausnahmetexte und alles vor 1.7.0 haben keinen Schluessel."""
    datenbank.add_log_entry(None, 'error', 'Discord',
                            'Connection refused', success=False)
    assert datenbank.get_log(lang='en')[0]['message'] == 'Connection refused'


def test_sprache_kommt_aus_den_einstellungen(datenbank):
    datenbank.save_settings({'language': 'en'})
    assert sprache.sprache_lesen() == 'en'
    datenbank.save_settings({'language': 'de'})
    assert sprache.sprache_lesen() == 'de'
