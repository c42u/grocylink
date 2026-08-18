"""Die abgesicherte Schnittstelle fuer die App.

Geprueft wird, was sie von der offenen Weboberflaechen-Schnittstelle
unterscheidet: der Zugang. Dass die Endpunkte selbst richtig rechnen, pruefen
die vorhandenen Tests -- App und Oberflaeche laufen durch dieselbe Funktion.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def anwendung(monkeypatch):
    verzeichnis = tempfile.mkdtemp()
    os.makedirs(os.path.join(verzeichnis, "data"), exist_ok=True)
    import database
    monkeypatch.setattr(database, "DB_PATH",
                        os.path.join(verzeichnis, "data", "test.db"))
    database.init_db()
    import app as anwendungsmodul
    anwendungsmodul.app.config["TESTING"] = True
    return anwendungsmodul, database


def test_ohne_schluessel_kein_zugang(anwendung):
    anwendungsmodul, _ = anwendung
    client = anwendungsmodul.app.test_client()
    for pfad in ("/api/v1/info", "/api/v1/status", "/api/v1/settings",
                 "/api/v1/log", "/api/v1/bring/status"):
        antwort = client.get(pfad)
        assert antwort.status_code == 401, pfad
        assert "Kein Schlüssel mitgeschickt" in antwort.get_json()["error"]


def test_falscher_schluessel(anwendung):
    anwendungsmodul, _ = anwendung
    client = anwendungsmodul.app.test_client()
    antwort = client.get("/api/v1/info", headers={"X-API-Key": "gl_erfunden"})
    assert antwort.status_code == 401
    assert "unbekannt oder widerrufen" in antwort.get_json()["error"]


def test_zugang_anlegen_pruefen_widerrufen(anwendung):
    anwendungsmodul, database = anwendung
    schluessel = database.create_api_key("iPhone")
    assert schluessel.startswith("gl_")

    # Der Schluessel selbst darf nicht in der Datenbank stehen
    verbindung = database.get_db()
    roh = " ".join(str(z) for z in
                   verbindung.execute("SELECT * FROM api_keys").fetchall())
    verbindung.close()
    assert schluessel not in roh

    client = anwendungsmodul.app.test_client()
    antwort = client.get("/api/v1/info", headers={"X-API-Key": schluessel})
    assert antwort.status_code == 200
    daten = antwort.get_json()
    assert daten["zugang"] == "iPhone"
    assert daten["api"] == "v1"
    assert daten["grocy_konfiguriert"] is False

    # Benutzung wird fortgeschrieben
    assert database.get_api_keys()[0]["last_used_at"]

    # Widerrufen: gilt wie unbekannt
    database.revoke_api_key(database.get_api_keys()[0]["id"])
    assert client.get("/api/v1/info",
                      headers={"X-API-Key": schluessel}).status_code == 401


def test_bearer_und_kopierfehler(anwendung):
    """Anfuehrungszeichen, Leerzeichen und ein Bearer im falschen Feld."""
    anwendungsmodul, database = anwendung
    schluessel = database.create_api_key("iPad")
    client = anwendungsmodul.app.test_client()
    for kopf in ({"Authorization": "Bearer %s" % schluessel},
                 {"X-API-Key": '"%s"' % schluessel},
                 {"X-API-Key": " %s " % schluessel},
                 {"X-API-Key": "Bearer %s" % schluessel}):
        assert client.get("/api/v1/info", headers=kopf).status_code == 200, kopf


def test_dieselbe_funktion_wie_die_oberflaeche(anwendung):
    """Der neue Weg ruft die View der Oberflaeche auf -- keine Zweitfassung."""
    anwendungsmodul, database = anwendung
    schluessel = database.create_api_key("Probe")
    client = anwendungsmodul.app.test_client()

    # Ohne Grocy-Zugang antworten beide Wege gleich (400 mit derselben Meldung)
    offen = client.get("/api/settings")
    gesichert = client.get("/api/v1/settings", headers={"X-API-Key": schluessel})
    assert offen.status_code == gesichert.status_code == 200
    assert offen.get_json() == gesichert.get_json()


def test_kassenbon_und_barcode_bleiben_draussen(anwendung):
    """Mit dem Nutzer so festgelegt -- beide leben von Kamera und Upload."""
    anwendungsmodul, _ = anwendung
    wege = {str(r) for r in anwendungsmodul.app.url_map.iter_rules()
            if "/api/v1" in str(r)}
    for verboten in ("receipt", "barcode", "openfoodfacts"):
        assert not [w for w in wege if verboten in w], verboten
