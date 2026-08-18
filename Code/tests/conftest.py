"""Gemeinsame Fixtures und Attrappen fuer die Bring!-Tests.

Die Tests laufen ohne Netzwerk und ohne Datenbank: Der Bring-Client wird
durch ``FakeBring`` ersetzt, die Datenbankfunktionen werden in den
Testmodulen einzeln umgebogen. Damit fassen die Tests weder die echte
SQLite-Datei unter ``Code/data`` noch die Bring-API an.
"""

import os
import sys

import pytest

# Die Module liegen eine Ebene ueber diesem Verzeichnis
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Attrappen fuer die Antworttypen der Library ────────────────────────

class FakePurchase:
    """Entspricht ``BringPurchase``: ein Eintrag auf der Einkaufsliste."""

    def __init__(self, item_id, specification='', uuid=''):
        self.itemId = item_id
        self.specification = specification
        self.uuid = uuid


class FakeItems:
    def __init__(self, purchase=None, recently=None):
        self.purchase = purchase or []
        self.recently = recently or []


class FakeItemsResponse:
    def __init__(self, purchase=None, recently=None):
        self.items = FakeItems(purchase, recently)


class FakeList:
    def __init__(self, list_uuid, name, theme=''):
        self.listUuid = list_uuid
        self.name = name
        self.theme = theme


class FakeListResponse:
    def __init__(self, lists=None):
        self.lists = lists or []


# ── Attrappe fuer den Bring-Client ─────────────────────────────────────

class FakeBring:
    """Ersetzt ``bring_api.Bring`` und protokolliert alle Aufrufe.

    ``calls`` enthaelt Tupel ``(methode, argumente...)`` in der Reihenfolge
    des Aufrufs - damit laesst sich pruefen, wie viele Requests ein
    Vorgang tatsaechlich ausgeloest haette.
    """

    # Klassenweite Aufzeichnung, damit Tests auch die Login-Zahl sehen,
    # ohne an die im Runtime versteckte Instanz zu kommen.
    instances = []

    # Von Tests setzbar: Liste von Exceptions/None, die login() abarbeitet
    login_side_effects = []

    def __init__(self, session, email, password):
        self.session = session
        self.email = email
        self.password = password
        self.calls = []
        self.login_count = 0
        self.lists = [FakeList('list-1', 'Haushalt')]
        self.purchase = []
        self.batch_should_fail = False
        FakeBring.instances.append(self)

    @classmethod
    def reset(cls):
        cls.instances = []
        cls.login_side_effects = []

    async def login(self):
        self.login_count += 1
        self.calls.append(('login',))
        if FakeBring.login_side_effects:
            effect = FakeBring.login_side_effects.pop(0)
            if effect is not None:
                raise effect
        return None

    async def load_lists(self):
        self.calls.append(('load_lists',))
        return FakeListResponse(self.lists)

    async def get_list(self, list_uuid):
        self.calls.append(('get_list', list_uuid))
        return FakeItemsResponse(list(self.purchase))

    async def save_item(self, list_uuid, item_name, specification='',
                        item_uuid=None):
        self.calls.append(('save_item', list_uuid, item_name, specification,
                           item_uuid))
        self.purchase.append(FakePurchase(item_name, specification,
                                          item_uuid or 'generated'))

    async def update_item(self, list_uuid, item_name, specification='',
                          item_uuid=None):
        self.calls.append(('update_item', list_uuid, item_name, specification,
                           item_uuid))

    async def remove_item(self, list_uuid, item_name, item_uuid=None):
        self.calls.append(('remove_item', list_uuid, item_name, item_uuid))

    async def batch_update_list(self, list_uuid, items, operation=None):
        self.calls.append(('batch_update_list', list_uuid, list(items),
                           operation))
        if self.batch_should_fail:
            raise RuntimeError("Sammelrequest abgelehnt")

    def count(self, method):
        """Zaehlt, wie oft eine Methode aufgerufen wurde."""
        return sum(1 for c in self.calls if c[0] == method)


@pytest.fixture
def fake_bring(monkeypatch):
    """Biegt ``bring_api.Bring`` auf die Attrappe um und raeumt danach auf."""
    import bring_api

    from bring_runtime import get_runtime

    FakeBring.reset()
    monkeypatch.setattr(bring_api, 'Bring', FakeBring)
    yield FakeBring
    # Gecachten Client verwerfen, damit der naechste Test frisch einloggt
    get_runtime().invalidate()
    FakeBring.reset()
