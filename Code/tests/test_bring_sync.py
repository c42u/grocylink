"""Tests fuer die Bring!-Sync-Engine.

Geprueft werden die Soll-Berechnung aus Grocy (Overrides, Einheiten,
Sanitizer) und der Abgleich mit der Bring-Liste. Ein eigener Test haelt
fest, dass ein Sync die Liste nur ein einziges Mal abruft - bis v1.4.x
holte die Engine sie nach jedem neu angelegten Eintrag komplett neu.
"""

import pytest

import bring_sync
from bring_sync import BringSync, BringSyncError, _format_spec, _sanitize_name

from conftest import FakePurchase


# ── Attrappe fuer Grocy ────────────────────────────────────────────────

class FakeGrocy:
    def __init__(self):
        self.quantity_units = [
            {'id': 1, 'name': 'Stueck', 'name_plural': 'Stueck'},
            {'id': 2, 'name': 'Flasche', 'name_plural': 'Flaschen'},
        ]
        self.products = [
            {'id': 10, 'name': 'Milch', 'qu_id_purchase': 2},
            {'id': 11, 'name': 'Butter', 'qu_id_purchase': 1},
            {'id': 12, 'name': 'Sahne 30% Fett', 'qu_id_purchase': 1},
        ]
        self.shopping_list = []
        self.volatile = {'missing_products': []}

    def get_quantity_units(self):
        return self.quantity_units

    def get_all_products(self):
        return self.products

    def get_shopping_list(self):
        return self.shopping_list

    def get_volatile_stock(self, due_soon_days=0):
        return self.volatile


@pytest.fixture
def umgebung(monkeypatch):
    """Verdrahtet bring_sync mit Attrappen statt Datenbank und Grocy."""
    zustand = {
        'settings': {
            'bring_email': 'a@b.de',
            'bring_password': 'geheim',
            'bring_list_uuid': 'list-1',
            'bring_source': 'shopping_list',
            'bring_auto_remove': '0',
            'bring_sync_enabled': '1',
        },
        'sync_map': [],
        'overrides': {},
        'upserts': [],
        'deletes': [],
        'logs': [],
        'grocy': FakeGrocy(),
    }

    monkeypatch.setattr(bring_sync, 'get_all_settings',
                        lambda: dict(zustand['settings']))
    monkeypatch.setattr(bring_sync, 'get_bring_sync_map',
                        lambda: list(zustand['sync_map']))
    monkeypatch.setattr(bring_sync, 'get_bring_overrides',
                        lambda: dict(zustand['overrides']))
    monkeypatch.setattr(bring_sync, 'GrocyClient',
                        lambda *a, **kw: zustand['grocy'])
    monkeypatch.setattr(
        bring_sync, 'upsert_bring_sync_entry',
        lambda pid, uuid, name, spec: zustand['upserts'].append(
            {'product_id': pid, 'uuid': uuid, 'name': name, 'spec': spec}))
    monkeypatch.setattr(
        bring_sync, 'delete_bring_sync_entry',
        lambda pid: zustand['deletes'].append(pid))
    monkeypatch.setattr(
        bring_sync, 'add_log_entry',
        lambda *a, **kw: zustand['logs'].append((a, kw)))

    return zustand


# ── Hilfsfunktionen ────────────────────────────────────────────────────

def test_sanitize_ersetzt_prozentzeichen():
    assert _sanitize_name('Sahne 30% Fett') == 'Sahne 30Prozent Fett'
    assert _sanitize_name('  Milch  ') == 'Milch'
    assert _sanitize_name(None) == ''


def test_format_spec_setzt_teile_zusammen():
    assert _format_spec(2, 'Flaschen') == '2 Flaschen'
    assert _format_spec(None, 'Flaschen') == 'Flaschen'
    assert _format_spec(3, None) == '3'
    assert _format_spec(None, None) == ''


# ── Soll-Berechnung ────────────────────────────────────────────────────

def test_soll_aus_shoppinglist_mit_einheiten(umgebung):
    umgebung['grocy'].shopping_list = [
        {'product_id': 10, 'amount': 2, 'qu_id': 2},
        {'product_id': 11, 'amount': 1, 'qu_id': 1},
    ]
    items = BringSync()._build_target_items()

    assert items == [
        {'product_id': 10, 'name': 'Milch', 'spec': '2 Flaschen'},
        {'product_id': 11, 'name': 'Butter', 'spec': '1 Stueck'},
    ]


def test_soll_nutzt_singular_bei_menge_eins(umgebung):
    umgebung['grocy'].shopping_list = [{'product_id': 10, 'amount': 1, 'qu_id': 2}]
    items = BringSync()._build_target_items()
    assert items[0]['spec'] == '1 Flasche'


def test_soll_ueberspringt_freitext_eintraege(umgebung):
    """Eintraege ohne Produktbindung bleiben aussen vor (bis v1.6.0)."""
    umgebung['grocy'].shopping_list = [
        {'product_id': None, 'amount': 1, 'note': 'Blumen'},
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
    ]
    items = BringSync()._build_target_items()
    assert [i['product_id'] for i in items] == [10]


def test_override_versteckt_produkt(umgebung):
    umgebung['grocy'].shopping_list = [
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
        {'product_id': 11, 'amount': 1, 'qu_id': 1},
    ]
    umgebung['overrides'] = {10: {'hide_from_bring': True}}
    items = BringSync()._build_target_items()
    assert [i['product_id'] for i in items] == [11]


def test_override_setzt_name_und_spec(umgebung):
    umgebung['grocy'].shopping_list = [{'product_id': 10, 'amount': 2, 'qu_id': 2}]
    umgebung['overrides'] = {
        10: {'custom_name': 'Vollmilch', 'custom_spec': 'die im Glas'}
    }
    items = BringSync()._build_target_items()
    assert items[0]['name'] == 'Vollmilch'
    assert items[0]['spec'] == 'die im Glas'


def test_produktname_wird_sanitized(umgebung):
    umgebung['grocy'].shopping_list = [{'product_id': 12, 'amount': 1, 'qu_id': 1}]
    items = BringSync()._build_target_items()
    assert items[0]['name'] == 'Sahne 30Prozent Fett'


def test_soll_aus_mindestbestand(umgebung):
    umgebung['settings']['bring_source'] = 'missing'
    umgebung['grocy'].volatile = {
        'missing_products': [{'id': 11, 'amount_missing': 3}]
    }
    items = BringSync()._build_target_items()
    assert items == [{'product_id': 11, 'name': 'Butter', 'spec': '3 Stueck'}]


def test_unbekannte_quelle_meldet_fehler(umgebung):
    umgebung['settings']['bring_source'] = 'irgendwas'
    with pytest.raises(BringSyncError):
        BringSync()._build_target_items()


def test_nicht_erreichbares_grocy_meldet_klaren_fehler(umgebung):
    def kaputt():
        raise ConnectionError("Grocy URL oder API-Key nicht konfiguriert")

    umgebung['grocy'].get_all_products = kaputt
    with pytest.raises(BringSyncError, match='Produkte'):
        BringSync()._build_target_items()


def test_fehlerhafte_shoppinglist_meldet_klaren_fehler(umgebung):
    def kaputt():
        raise ConnectionError("Zeitueberschreitung")

    umgebung['grocy'].get_shopping_list = kaputt
    with pytest.raises(BringSyncError, match='Shoppinglist'):
        BringSync()._build_target_items()


def test_fehlender_mindestbestand_meldet_klaren_fehler(umgebung):
    def kaputt(due_soon_days=0):
        raise ConnectionError("Zeitueberschreitung")

    umgebung['settings']['bring_source'] = 'missing'
    umgebung['grocy'].get_volatile_stock = kaputt
    with pytest.raises(BringSyncError, match='Volatile'):
        BringSync()._build_target_items()


def test_unbekanntes_produkt_wird_uebersprungen(umgebung):
    """Ein Shoppinglist-Eintrag auf ein geloeschtes Produkt darf nicht stoeren."""
    umgebung['grocy'].shopping_list = [
        {'product_id': 999, 'amount': 1, 'qu_id': 1},
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
    ]
    items = BringSync()._build_target_items()
    assert [i['product_id'] for i in items] == [10]


# ── Abgleich mit der Bring-Liste ───────────────────────────────────────

def test_neues_item_wird_gebuendelt_angelegt(umgebung, fake_bring):
    umgebung['grocy'].shopping_list = [{'product_id': 10, 'amount': 2, 'qu_id': 2}]

    stats = BringSync().sync_all()

    assert stats['added'] == 1
    client = fake_bring.instances[0]
    assert client.count('batch_update_list') == 1
    (_, list_uuid, items, _) = next(
        c for c in client.calls if c[0] == 'batch_update_list')
    assert list_uuid == 'list-1'
    assert items[0]['itemId'] == 'Milch'
    assert items[0]['spec'] == '2 Flaschen'
    assert items[0]['operation'] == bring_sync.BRING_OP_ADD
    assert items[0]['uuid'], "die UUID muss selbst vergeben werden"


def test_sync_ruft_die_liste_nur_einmal_ab(umgebung, fake_bring):
    """Regression: frueher folgte auf jedes neue Item ein Vollabruf."""
    umgebung['grocy'].shopping_list = [
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
        {'product_id': 11, 'amount': 1, 'qu_id': 1},
        {'product_id': 12, 'amount': 1, 'qu_id': 1},
    ]

    stats = BringSync().sync_all()

    client = fake_bring.instances[0]
    assert stats['added'] == 3
    assert client.count('get_list') == 1
    assert client.count('batch_update_list') == 1


def test_unveraendertes_item_loest_keinen_request_aus(umgebung, fake_bring):
    umgebung['grocy'].shopping_list = [{'product_id': 10, 'amount': 2, 'qu_id': 2}]
    umgebung['sync_map'] = [{
        'grocy_product_id': 10, 'bring_item_uuid': 'uuid-10',
        'bring_item_name': 'Milch', 'bring_item_spec': '2 Flaschen',
    }]

    def mit_bestand(bring):
        bring.purchase = [FakePurchase('Milch', '2 Flaschen', 'uuid-10')]
        return bring

    _vorbereiten(fake_bring, mit_bestand, umgebung)
    stats = BringSync().sync_all()

    assert stats == {'added': 0, 'updated': 0, 'skipped': 1,
                     'removed': 0, 'errors': 0}
    assert fake_bring.instances[0].count('batch_update_list') == 0


def test_geaenderte_menge_wird_aktualisiert(umgebung, fake_bring):
    umgebung['grocy'].shopping_list = [{'product_id': 10, 'amount': 5, 'qu_id': 2}]
    umgebung['sync_map'] = [{
        'grocy_product_id': 10, 'bring_item_uuid': 'uuid-10',
        'bring_item_name': 'Milch', 'bring_item_spec': '2 Flaschen',
    }]

    def mit_bestand(bring):
        bring.purchase = [FakePurchase('Milch', '2 Flaschen', 'uuid-10')]
        return bring

    _vorbereiten(fake_bring, mit_bestand, umgebung)
    stats = BringSync().sync_all()

    assert stats['updated'] == 1
    client = fake_bring.instances[0]
    (_, _, items, _) = next(
        c for c in client.calls if c[0] == 'batch_update_list')
    assert items[0]['spec'] == '5 Flaschen'
    assert items[0]['uuid'] == 'uuid-10', "bestehende UUID beibehalten"


def test_auto_remove_entfernt_verwaiste_items(umgebung, fake_bring):
    umgebung['settings']['bring_auto_remove'] = '1'
    umgebung['grocy'].shopping_list = []
    umgebung['sync_map'] = [{
        'grocy_product_id': 10, 'bring_item_uuid': 'uuid-10',
        'bring_item_name': 'Milch', 'bring_item_spec': '2 Flaschen',
    }]

    stats = BringSync().sync_all()

    assert stats['removed'] == 1
    assert umgebung['deletes'] == [10]
    client = fake_bring.instances[0]
    (_, _, items, _) = next(
        c for c in client.calls if c[0] == 'batch_update_list')
    assert items[0]['operation'] == bring_sync.BRING_OP_REMOVE


def test_auto_remove_bleibt_ohne_einstellung_aus(umgebung, fake_bring):
    umgebung['grocy'].shopping_list = []
    umgebung['sync_map'] = [{
        'grocy_product_id': 10, 'bring_item_uuid': 'uuid-10',
        'bring_item_name': 'Milch', 'bring_item_spec': '2 Flaschen',
    }]

    stats = BringSync().sync_all()

    assert stats['removed'] == 0
    assert umgebung['deletes'] == []


def test_fehlgeschlagener_sammelrequest_faellt_auf_einzelaufrufe_zurueck(
        umgebung, fake_bring):
    umgebung['grocy'].shopping_list = [
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
        {'product_id': 11, 'amount': 1, 'qu_id': 1},
    ]

    def batch_kaputt(bring):
        bring.batch_should_fail = True
        return bring

    _vorbereiten(fake_bring, batch_kaputt, umgebung)
    stats = BringSync().sync_all()

    client = fake_bring.instances[0]
    assert stats['added'] == 2
    assert stats['errors'] == 0
    assert client.count('batch_update_list') == 1
    assert client.count('save_item') == 2, "beide Items einzeln nachgereicht"


def test_scheitert_ein_einzelaufruf_wird_der_eintrag_nicht_gespeichert(
        umgebung, fake_bring):
    """Die sync_map darf nichts fuehren, was auf Bring nie ankam."""
    umgebung['grocy'].shopping_list = [
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
        {'product_id': 11, 'amount': 1, 'qu_id': 1},
    ]

    def alles_kaputt(bring):
        bring.batch_should_fail = True

        async def save_item(list_uuid, item_name, specification='',
                            item_uuid=None):
            bring.calls.append(('save_item', list_uuid, item_name,
                                specification, item_uuid))
            if item_name == 'Milch':
                raise RuntimeError("Bring mag keine Milch")

        bring.save_item = save_item
        return bring

    _vorbereiten(fake_bring, alles_kaputt, umgebung)
    stats = BringSync().sync_all()

    assert stats['added'] == 1
    assert stats['errors'] == 1
    gespeicherte_ids = [u['product_id'] for u in umgebung['upserts']]
    assert gespeicherte_ids == [11], "nur das erfolgreiche Produkt merken"
    assert umgebung['logs'], "der Fehler gehoert ins Log"


def test_sync_ohne_liste_meldet_fehler(umgebung, fake_bring):
    umgebung['settings']['bring_list_uuid'] = ''
    with pytest.raises(BringSyncError):
        BringSync().sync_all()


def test_sync_ohne_zugangsdaten_meldet_fehler(umgebung, fake_bring):
    umgebung['settings']['bring_password'] = ''
    with pytest.raises(BringSyncError):
        BringSync().sync_all()


# ── Einzelaktionen aus der Oberflaeche ─────────────────────────────────

def test_manuelles_item_bekommt_eigene_uuid(umgebung, fake_bring):
    ergebnis = BringSync().add_item_manual('Brot', '1 Laib')

    assert ergebnis['name'] == 'Brot'
    client = fake_bring.instances[0]
    (_, _, name, spec, item_uuid) = next(
        c for c in client.calls if c[0] == 'save_item')
    assert (name, spec) == ('Brot', '1 Laib')
    assert item_uuid, "auch hier vergeben wir die UUID selbst"


def test_manuelles_item_ohne_namen_meldet_fehler(umgebung, fake_bring):
    with pytest.raises(BringSyncError):
        BringSync().add_item_manual('   ')


def test_umbenennen_legt_neu_an_und_entfernt_alt(umgebung, fake_bring):
    """Beim Umbenennen faellt der frueher noetige Vollabruf weg."""
    ergebnis = BringSync().update_list_item(
        'list-1', 'uuid-alt', 'Vollmilch', '1 Flasche', old_name='Milch')

    client = fake_bring.instances[0]
    assert client.count('get_list') == 0, "kein Vollabruf mehr noetig"
    assert client.count('save_item') == 1
    assert client.count('remove_item') == 1
    assert ergebnis['uuid'] and ergebnis['uuid'] != 'uuid-alt'


def test_reine_specaenderung_nutzt_update(umgebung, fake_bring):
    ergebnis = BringSync().update_list_item(
        'list-1', 'uuid-10', 'Milch', '3 Flaschen', old_name='Milch')

    client = fake_bring.instances[0]
    assert client.count('update_item') == 1
    assert client.count('save_item') == 0
    assert ergebnis['uuid'] == 'uuid-10'


def test_listen_werden_gemappt(umgebung, fake_bring):
    listen = BringSync().get_lists()
    assert listen == [{'uuid': 'list-1', 'name': 'Haushalt', 'theme': ''}]


def test_verbindungstest_meldet_listennamen(umgebung, fake_bring):
    ok, meldung = BringSync().test_connection()
    assert ok is True
    assert 'Haushalt' in meldung


def test_verbindungstest_ohne_zugangsdaten(umgebung, fake_bring):
    umgebung['settings']['bring_email'] = ''
    ok, meldung = BringSync().test_connection()
    assert ok is False
    assert 'nicht vollstaendig' in meldung


# ── Scheduler-Einstieg ─────────────────────────────────────────────────

def test_scheduler_laeuft_nur_bei_aktiviertem_sync(umgebung, fake_bring):
    umgebung['settings']['bring_sync_enabled'] = '0'
    assert bring_sync.run_bring_sync() is None
    assert fake_bring.instances == [], "es darf kein Login stattfinden"


def test_scheduler_protokolliert_das_ergebnis(umgebung, fake_bring):
    umgebung['grocy'].shopping_list = [{'product_id': 10, 'amount': 1, 'qu_id': 2}]

    stats = bring_sync.run_bring_sync()

    assert stats['added'] == 1
    (args, kwargs) = umgebung['logs'][-1]
    assert args[1] == 'bring_sync'
    assert kwargs['success'] is True


def test_scheduler_faengt_konfigurationsfehler_ab(umgebung, fake_bring):
    umgebung['settings']['bring_list_uuid'] = ''

    assert bring_sync.run_bring_sync() is None
    (args, kwargs) = umgebung['logs'][-1]
    assert kwargs['success'] is False


def test_scheduler_faengt_unerwartete_fehler_ab(umgebung, fake_bring, monkeypatch):
    def kaputt(self):
        raise RuntimeError("Grocy nicht erreichbar")

    monkeypatch.setattr(BringSync, 'sync_all', kaputt)

    assert bring_sync.run_bring_sync() is None
    (args, kwargs) = umgebung['logs'][-1]
    assert kwargs['success'] is False
    assert 'Grocy nicht erreichbar' in args[3]


# ── Stueckelung grosser Aenderungsmengen ───────────────────────────────

def test_grosse_mengen_werden_gestueckelt(umgebung, fake_bring, monkeypatch):
    """Mehr Aenderungen als BATCH_CHUNK_SIZE ergeben mehrere Requests."""
    monkeypatch.setattr(BringSync, 'BATCH_CHUNK_SIZE', 2)
    umgebung['grocy'].shopping_list = [
        {'product_id': 10, 'amount': 1, 'qu_id': 2},
        {'product_id': 11, 'amount': 1, 'qu_id': 1},
        {'product_id': 12, 'amount': 1, 'qu_id': 1},
    ]

    stats = BringSync().sync_all()

    assert stats['added'] == 3
    assert fake_bring.instances[0].count('batch_update_list') == 2


def test_chunked_zerlegt_korrekt():
    assert list(bring_sync._chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(bring_sync._chunked([], 2)) == []


# ── Hilfsfunktion fuer Tests, die den Client vorbereiten muessen ───────

def _vorbereiten(fake_bring, anpassen, umgebung):
    """Laesst ``anpassen`` auf dem Client laufen, bevor der Sync startet.

    Der Client entsteht erst beim ersten Aufruf im Runtime. Wir provozieren
    ihn deshalb mit einem harmlosen Aufruf und veraendern ihn danach.
    """
    BringSync().get_lists()
    anpassen(fake_bring.instances[0])
