"""
grocylink – JSON-Schnittstelle für die App
================================================================================
Die Weboberfläche von grocylink ist schon ein JavaScript-Frontend auf einer
JSON-Schnittstelle: 47 Endpunkte unter `/api/…`. Was ihr fehlt, ist eine
**Absicherung** -- sie ist offen, weil sie im Heimnetz hinter der Oberfläche
liegt.

Dieses Modul legt eine **versionierte, abgesicherte** Schicht darüber:
`/api/v1/…` verlangt einen Geräteschlüssel und ruft **dieselbe** View-Funktion
auf, die die Weboberfläche benutzt. Bewusst so und nicht als zweite
Umsetzung -- zwei Wege, die dasselbe rechnen, laufen mit der Zeit auseinander.

WARUM NICHT DIE VORHANDENEN ENDPUNKTE ABSICHERN
Die Oberfläche ruft sie aus dem Browser ohne Schlüssel auf. Eine Schlüsselpflicht
dort würde sie lahmlegen, und ein Sonderweg für "Anfragen aus dem eigenen
Browser" ist raten. Die alten Pfade bleiben deshalb unverändert; **neu ist nur
der Weg von außen**.

WAS NICHT DABEI IST
Kassenbons und Barcode-Suche -- mit dem Nutzer so festgelegt. Beides lebt von
Kamera und Dateiupload und gehört, wenn überhaupt, in eine eigene Anforderung.

ZUGANG
Je Gerät ein Schlüssel (`gl_…`), in den Einstellungen erzeugt und einzeln
widerrufbar. Als Kopfzeile `X-API-Key` oder `Authorization: Bearer`.

Autor:    c42u
Co-Autor: ClaudeCode
Lizenz:   GPLv3
Version:  1.6.0
"""

import functools

from flask import Blueprint, current_app, g, jsonify, request

from database import check_api_key

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')


def _schluessel_aus_anfrage():
    """Holt den Schlüssel aus der Kopfzeile -- beide üblichen Formen.

    Nachsichtig gegenüber dem, was beim Kopieren mitkommt: Anführungszeichen,
    Leerzeichen, ein versehentliches "Bearer" im falschen Feld.
    """
    def saeubern(wert):
        return (wert or '').strip().strip('"').strip("'").strip()

    kopf = request.headers.get('X-API-Key')
    if kopf:
        sauber = saeubern(kopf)
        if sauber.lower().startswith('bearer '):
            return saeubern(sauber[7:])
        return sauber
    traeger = request.headers.get('Authorization') or ''
    if traeger.lower().startswith('bearer '):
        return saeubern(traeger[7:])
    return ''


def zugang_pflicht(funktion):
    """Lässt nur Anfragen mit gültigem Geräteschlüssel durch."""
    @functools.wraps(funktion)
    def huelle(*args, **kwargs):
        roh = _schluessel_aus_anfrage()
        zugang = check_api_key(roh)
        if not zugang:
            # Unterschieden wird, **ob** ein Schlüssel kam -- das weiß der
            # Anrufer selbst, es verrät nichts über gültige Schlüssel.
            if not roh:
                meldung = ('Kein Schlüssel mitgeschickt. Erwartet wird die '
                           'Kopfzeile „X-API-Key: gl_…" (oder '
                           '„Authorization: Bearer gl_…").')
            else:
                meldung = ('Dieser Schlüssel ist unbekannt oder widerrufen. '
                           'Zugänge stehen je Instanz in deren Einstellungen.')
            return jsonify({'error': meldung}), 401
        g.api_zugang = zugang
        return funktion(*args, **kwargs)
    return huelle


def _weiterreichen(name):
    """Ruft die View-Funktion der Weboberfläche auf.

    `current_app.view_functions` ist Flasks eigene Zuordnung Name → Funktion.
    So laufen App und Oberfläche durch **denselben** Code: Was der Browser
    sieht, sieht auch das iPhone, und eine Änderung wirkt an beiden Stellen.
    """
    return current_app.view_functions[name]()


def _durchreichen(pfad, ziel, methoden=('GET',), name=None):
    """Legt einen abgesicherten Weg auf eine vorhandene View."""
    def sicht(**kwargs):
        return _weiterreichen(ziel)
    sicht.__name__ = name or ('v1_' + ziel)
    api_v1.add_url_rule(pfad, view_func=zugang_pflicht(sicht),
                        methods=list(methoden))


# ---------------------------------------------------------------------------
# Was die App kann -- alles außer Kassenbons und Barcode
# ---------------------------------------------------------------------------
#
# Die Reihenfolge folgt der Oberfläche: Überblick, Vorrat, Einstellungen,
# Kanäle, Protokoll, CalDAV, Bring.

_WEGE = [
    # Überblick und Vorrat
    ('/status',            'api_status',                ('GET',)),
    ('/products',          'api_get_products',          ('GET',)),
    ('/products/override', 'api_save_override',         ('POST',)),
    ('/stock/add',         'api_grocy_stock_add',       ('POST',)),
    ('/product-groups',    'api_grocy_product_groups',  ('GET',)),
    ('/locations',         'api_grocy_locations',       ('GET',)),
    ('/quantity-units',    'api_grocy_quantity_units',  ('GET',)),

    # Einstellungen
    ('/settings',        'api_get_settings',    ('GET',)),
    ('/settings',        'api_save_settings',   ('POST',)),
    ('/test-connection', 'api_test_connection', ('POST',)),

    # Kanäle
    ('/channels', 'api_get_channels', ('GET',)),
    ('/channels', 'api_save_channel', ('POST',)),

    # Protokoll und Prüfung
    ('/log',       'api_get_log',   ('GET',)),
    ('/log',       'api_clear_log', ('DELETE',)),
    ('/check-now', 'api_check_now', ('POST',)),

    # CalDAV
    ('/caldav/status',    'api_caldav_status',    ('GET',)),
    ('/caldav/test',      'api_caldav_test',      ('POST',)),
    ('/caldav/calendars', 'api_caldav_calendars', ('GET',)),
    ('/caldav/sync-now',  'api_caldav_sync_now',  ('POST',)),
    ('/caldav/map',       'api_caldav_map',       ('GET', 'DELETE')),

    # Bring!
    ('/bring/status',       'api_bring_status',        ('GET',)),
    ('/bring/test',         'api_bring_test',          ('POST',)),
    ('/bring/lists',        'api_bring_lists',         ('GET',)),
    ('/bring/sync-now',     'api_bring_sync_now',      ('POST',)),
    ('/bring/list-items',   'api_bring_list_items',    ('GET',)),
    ('/bring/items/manual', 'api_bring_add_item_manual', ('POST',)),
    ('/bring/overrides',    'api_bring_overrides',     ('GET',)),
    ('/bring/overrides',    'api_save_bring_override', ('POST',)),
    ('/bring/map',          'api_bring_map',           ('GET', 'DELETE')),
]

for _pfad, _ziel, _methoden in _WEGE:
    _durchreichen(_pfad, _ziel, _methoden)


# --- Wege mit Platzhaltern im Pfad -----------------------------------------
# `_durchreichen` gibt die Platzhalter nicht weiter; diese wenigen bekommen
# deshalb eine eigene Hülle.

@api_v1.route('/channels/<int:channel_id>', methods=['DELETE'])
@zugang_pflicht
def kanal_entfernen(channel_id):
    return current_app.view_functions['api_delete_channel'](channel_id)


@api_v1.route('/channels/<int:channel_id>/test', methods=['POST'])
@zugang_pflicht
def kanal_pruefen(channel_id):
    return current_app.view_functions['api_test_channel'](channel_id)


@api_v1.route('/bring/list-items', methods=['PUT'])
@zugang_pflicht
def bring_position_aendern():
    return current_app.view_functions['api_bring_update_list_item']()


@api_v1.route('/info', methods=['GET'])
@zugang_pflicht
def info():
    """Was die App zuerst wissen will: Fassung und Zugangsname.

    Zum Prüfen beim Einrichten -- antwortet er mit 200, stimmen Adresse und
    Schlüssel.
    """
    from database import get_all_settings
    einstellungen = get_all_settings()
    return jsonify({
        'version': current_app.config.get('APP_VERSION', ''),
        'api': 'v1',
        'grocy_konfiguriert': bool(einstellungen.get('grocy_url')
                                   and einstellungen.get('grocy_api_key')),
        'bring_konfiguriert': bool(einstellungen.get('bring_email')
                                   and einstellungen.get('bring_password')),
        'caldav_konfiguriert': bool(einstellungen.get('caldav_url')),
        'zugang': g.api_zugang.get('name'),
    })
