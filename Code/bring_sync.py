"""Bring!-Sync-Engine fuer Grocylink.

Synchronisiert Eintraege aus Grocy (Shoppinglist oder Mindestbestand-Lueckenliste)
in eine Bring!-Liste. Aktuell unidirektional (Grocy -> Bring) als v1.

Nutzt die inoffizielle aber gut gepflegte miaucl/bring-api (async, aiohttp).
Da Grocylink synchron arbeitet (Flask + APScheduler), laufen alle Aufrufe
ueber ``bring_runtime``: ein dauerhafter Eventloop in einem Daemon-Thread,
der Session und eingeloggten Client zwischen den Aufrufen weiterleben laesst.

Wichtige Eigenheiten der Bring-API:
- Login per Mail/Passwort, danach Bearer-Token im Client. Der Token wird von
  der Library selbst per Refresh-Token erneuert, solange der Client lebt.
- ``save_item(list_uuid, name, spec)`` legt einen Listeneintrag an. Bring matcht
  den Namen gegen einen Katalog (Icons!) - daher kanonische Namen verwenden.
- Anlegen, Aendern und Entfernen sind intern alle ``batch_update_list`` mit
  unterschiedlicher Operation (TO_PURCHASE / REMOVE). Ein Sync bringt daher
  saemtliche Aenderungen in einem einzigen Request unter.
- Die Item-UUID darf beim Anlegen selbst vergeben werden. Das erspart den
  frueheren Vollabruf der Liste nach jedem einzelnen neuen Eintrag.
- Das Zeichen ``%`` wird historisch nicht korrekt verarbeitet -> ``Prozent``.
"""

import logging
import uuid as uuid_lib

from bring_runtime import get_runtime, BringRuntimeError

import sprache
from database import (
    get_all_settings, get_bring_sync_map, upsert_bring_sync_entry,
    delete_bring_sync_entry, clear_bring_sync_map, get_bring_overrides,
    add_log_entry,
)
from grocy_client import GrocyClient

logger = logging.getLogger(__name__)

USER_AGENT = 'Grocylink/1.5.0 (grocylink@c42u.de)'

# Operationen fuer ``batch_update_list``. Bewusst als Strings statt via
# ``BringItemOperation``, damit dieses Modul ohne harten Import von
# ``bring_api`` auskommt - die Library setzt genau diese Werte ein.
BRING_OP_ADD = 'TO_PURCHASE'
BRING_OP_REMOVE = 'REMOVE'


def _sanitize_name(name):
    """Entfernt fuer Bring problematische Zeichen aus Item-Namen."""
    if not name:
        return ''
    name = name.replace('%', 'Prozent')
    return name.strip()


def _format_spec(amount, qu_name=None, prefix_text=None):
    """Baut den Spec-String fuer Bring (z.B. ``2 Stueck``)."""
    parts = []
    if amount is not None and str(amount).strip():
        parts.append(str(amount).strip())
    if qu_name:
        parts.append(qu_name.strip())
    if prefix_text:
        parts.append(prefix_text.strip())
    return ' '.join(parts).strip()


class BringSyncError(Exception):
    """Geworfen, wenn der Sync nicht regulaer durchlaufen kann."""


class BringSync:
    """Sync-Engine: Quelle (Grocy) -> Ziel (Bring)."""

    # Maximale Anzahl Items pro batch_update_list-Request. Bring selbst nennt
    # kein Limit; wir stueckeln trotzdem, damit ein einzelner fehlschlagender
    # Request nicht den kompletten Sync mitreisst.
    BATCH_CHUNK_SIZE = 50

    def __init__(self):
        self.settings = get_all_settings()
        self.grocy = GrocyClient()

    # ── Zugriff auf den Runtime ────────────────────────────────────────

    def _credentials(self, email=None, password=None):
        """Liefert die zu verwendenden Zugangsdaten (Argument vor Setting)."""
        email = email if email else self.settings.get('bring_email', '')
        password = password if password else self.settings.get('bring_password', '')
        if not email or not password:
            raise BringSyncError(
                "Bring-Zugangsdaten nicht vollstaendig konfiguriert"
            )
        return email, password

    def _execute(self, coro_factory, email=None, password=None):
        """Fuehrt ``coro_factory(bring)`` mit eingeloggtem Client aus."""
        email, password = self._credentials(email, password)
        try:
            return get_runtime().execute(coro_factory, email, password)
        except BringRuntimeError as e:
            raise BringSyncError(str(e))

    # ── Async-Hilfsmethoden (bekommen den Client vom Runtime) ──────────

    async def _async_test(self, bring):
        lists_resp = await bring.load_lists()
        names = [l.name for l in lists_resp.lists]
        return True, f"Verbunden. Listen: {', '.join(names) if names else '(keine)'}"

    async def _async_get_lists(self, bring):
        resp = await bring.load_lists()
        return [
            {'uuid': l.listUuid, 'name': l.name, 'theme': getattr(l, 'theme', '') or ''}
            for l in resp.lists
        ]

    async def _async_get_list_items(self, bring, list_uuid):
        """Liefert die aktuell auf einer Bring-Liste stehenden Items."""
        resp = await bring.get_list(list_uuid)
        return [
            {
                'name': p.itemId,
                'spec': getattr(p, 'specification', '') or '',
                'uuid': getattr(p, 'uuid', '') or '',
            }
            for p in (resp.items.purchase or [])
        ]

    async def _async_update_list_item(self, bring, list_uuid, item_uuid, name,
                                      spec, old_name=None):
        """Updated ein bestehendes Bring-Item.

        Wenn nur die Spec sich aendert: ``update_item`` (uuid-basiert).
        Wenn sich auch der Name aendert: neues Item anlegen, altes entfernen.
        Bring zeigt umbenannte Items in der App erst nach Reload an, daher
        ist save+remove zuverlaessiger als update_item mit neuem Namen.

        Die UUID des neuen Eintrags vergeben wir selbst, damit kein
        Vollabruf der Liste noetig ist, nur um sie wieder herauszusuchen.
        """
        clean_name = _sanitize_name(name)
        clean_spec = _sanitize_name(spec or '')
        if not clean_name:
            raise BringSyncError("Item-Name darf nicht leer sein")

        name_changed = old_name and clean_name.lower() != (old_name or '').lower()

        if name_changed:
            new_uuid = str(uuid_lib.uuid4())
            # Neuen Eintrag anlegen, alten loeschen - der Reihenfolge wegen.
            # Ein Fehler beim Entfernen darf das Anlegen nicht entwerten.
            await bring.save_item(list_uuid, clean_name, clean_spec,
                                  item_uuid=new_uuid)
            try:
                await bring.remove_item(list_uuid, old_name, item_uuid=item_uuid)
            except Exception as e:
                logger.warning(f"Bring-Item alter Name '{old_name}' "
                               f"konnte nicht entfernt werden: {e}")
            return {'name': clean_name, 'spec': clean_spec, 'uuid': new_uuid}
        else:
            await bring.update_item(list_uuid, clean_name, clean_spec,
                                    item_uuid=item_uuid)
            return {'name': clean_name, 'spec': clean_spec, 'uuid': item_uuid}

    async def _async_add_item_manual(self, bring, name, spec, target_uuid):
        """Legt ein einzelnes Item auf eine Bring-Liste, ohne sync_map-Eintrag.

        Beim Hinzufuegen wird der Item-Name sanitized (z.B. ``%`` -> ``Prozent``).
        """
        clean_name = _sanitize_name(name)
        clean_spec = _sanitize_name(spec or '')
        await bring.save_item(target_uuid, clean_name, clean_spec,
                              item_uuid=str(uuid_lib.uuid4()))
        return {'name': clean_name, 'spec': clean_spec, 'list_uuid': target_uuid}

    async def _async_sync_all(self, bring, list_uuid):
        """Gleicht die Bring-Liste an den Soll-Stand aus Grocy an.

        Ablauf: Soll bauen, Ist holen, Differenz als Aenderungsliste sammeln
        und in moeglichst wenigen Requests schicken. Die Datenbank wird erst
        nach erfolgreicher Uebertragung nachgezogen, damit die sync_map keine
        Eintraege fuehrt, die es auf der Bring-Liste gar nicht gibt.
        """
        # 1) Soll-Items aus Grocy bauen
        target_items = self._build_target_items()

        # 2) Aktueller Stand auf der Bring-Liste
        current = await bring.get_list(list_uuid)
        existing_purchase = list(current.items.purchase or [])
        by_uuid = {p.uuid: p for p in existing_purchase if getattr(p, 'uuid', None)}
        by_name = {p.itemId.lower(): p for p in existing_purchase}

        sync_map = {m['grocy_product_id']: m for m in get_bring_sync_map()}
        seen_product_ids = set()
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'removed': 0, 'errors': 0}
        changes = []

        # 3) Soll-Items mit dem Ist abgleichen (noch ohne Requests)
        for item in target_items:
            pid = item['product_id']
            seen_product_ids.add(pid)
            bring_name = item['name']
            spec = item['spec']

            map_entry = sync_map.get(pid)
            purchase = None
            if map_entry:
                purchase = by_uuid.get(map_entry['bring_item_uuid'])
            if purchase is None:
                purchase = by_name.get(bring_name.lower())

            if purchase is None:
                # UUID selbst vergeben - erspart den Vollabruf nach dem Anlegen
                changes.append({
                    'kind': 'added',
                    'product_id': pid,
                    'name': bring_name,
                    'spec': spec,
                    'uuid': str(uuid_lib.uuid4()),
                    'operation': BRING_OP_ADD,
                })
            else:
                purchase_spec = getattr(purchase, 'specification', '') or ''
                purchase_uuid = getattr(purchase, 'uuid', '') or ''
                if purchase_spec != spec:
                    changes.append({
                        'kind': 'updated',
                        'product_id': pid,
                        'name': bring_name,
                        'spec': spec,
                        'uuid': purchase_uuid,
                        'operation': BRING_OP_ADD,
                    })
                else:
                    # Unveraendert: kein Request noetig, nur sync_map auffrischen
                    stats['skipped'] += 1
                    upsert_bring_sync_entry(pid, purchase_uuid, bring_name, spec)

        # 4) Auto-Remove: Items aus sync_map, die nicht mehr im Soll sind
        if self.settings.get('bring_auto_remove', '0') == '1':
            for pid, map_entry in sync_map.items():
                if pid in seen_product_ids:
                    continue
                changes.append({
                    'kind': 'removed',
                    'product_id': pid,
                    'name': map_entry['bring_item_name'],
                    'spec': '',
                    'uuid': map_entry.get('bring_item_uuid') or '',
                    'operation': BRING_OP_REMOVE,
                })

        # 5) Aenderungen uebertragen und Datenbank nachziehen
        for chunk in _chunked(changes, self.BATCH_CHUNK_SIZE):
            applied = await self._apply_changes(bring, list_uuid, chunk, stats)
            for change in applied:
                if change['kind'] == 'removed':
                    delete_bring_sync_entry(change['product_id'])
                else:
                    upsert_bring_sync_entry(
                        change['product_id'], change['uuid'],
                        change['name'], change['spec'],
                    )

        return stats

    async def _apply_changes(self, bring, list_uuid, chunk, stats):
        """Schickt einen Block Aenderungen und liefert die geglueckten zurueck.

        Erst als Sammelrequest. Faellt der um, wird jede Aenderung einzeln
        nachgereicht - so kostet ein einzelnes stoerendes Item nicht den
        ganzen Block und der Fehler laesst sich dem Produkt zuordnen.
        """
        payload = [
            {
                'itemId': c['name'],
                'spec': c['spec'],
                'uuid': c['uuid'] or None,
                'operation': c['operation'],
            }
            for c in chunk
        ]
        try:
            await bring.batch_update_list(list_uuid, payload)
            for c in chunk:
                stats[c['kind']] += 1
            return chunk
        except Exception as e:
            logger.warning(
                f"Bring-Sammelrequest fuer {len(chunk)} Aenderung(en) "
                f"fehlgeschlagen ({e}), versuche einzeln"
            )

        applied = []
        for c in chunk:
            try:
                if c['operation'] == BRING_OP_REMOVE:
                    await bring.remove_item(list_uuid, c['name'],
                                            item_uuid=c['uuid'] or None)
                else:
                    await bring.save_item(list_uuid, c['name'], c['spec'],
                                          item_uuid=c['uuid'] or None)
                stats[c['kind']] += 1
                applied.append(c)
            except Exception as e:
                logger.error(f"Bring-Sync Fehler fuer Produkt "
                             f"{c['product_id']} ({c['name']}): {e}")
                add_log_entry(c['name'], 'bring_sync', 'Bring!', str(e),
                              success=False)
                stats['errors'] += 1
        return applied

    # ── oeffentliche Schnittstellen (synchron) ─────────────────────────

    def test_connection(self, email=None, password=None):
        try:
            email, password = self._credentials(email, password)
        except BringSyncError:
            return False, "Bring-Zugangsdaten nicht vollstaendig"
        try:
            return self._execute(self._async_test, email=email, password=password)
        except Exception as e:
            return False, str(e)

    def get_lists(self):
        return self._execute(self._async_get_lists)

    def sync_all(self):
        list_uuid = self.settings.get('bring_list_uuid', '')
        if not list_uuid:
            raise BringSyncError("Keine Bring-Liste ausgewaehlt")
        return self._execute(
            lambda bring: self._async_sync_all(bring, list_uuid)
        )

    def add_item_manual(self, name, spec='', list_uuid=None):
        if not name or not name.strip():
            raise BringSyncError("Item-Name darf nicht leer sein")
        target_uuid = list_uuid or self.settings.get('bring_list_uuid', '')
        if not target_uuid:
            raise BringSyncError(
                "Keine Bring-Liste angegeben und keine globale Liste konfiguriert"
            )
        return self._execute(
            lambda bring: self._async_add_item_manual(bring, name, spec, target_uuid)
        )

    def get_list_items(self, list_uuid):
        if not list_uuid:
            raise BringSyncError("list_uuid erforderlich")
        return self._execute(
            lambda bring: self._async_get_list_items(bring, list_uuid)
        )

    def update_list_item(self, list_uuid, item_uuid, name, spec, old_name=None):
        if not list_uuid or not item_uuid:
            raise BringSyncError("list_uuid und item_uuid erforderlich")
        return self._execute(
            lambda bring: self._async_update_list_item(
                bring, list_uuid, item_uuid, name, spec, old_name=old_name
            )
        )

    # ── Soll-Berechnung aus Grocy ──────────────────────────────────────

    def _build_target_items(self):
        """Liefert die Liste der Items, die auf der Bring-Liste stehen sollen.

        Quelle: ``bring_source`` Setting (``shopping_list`` oder ``missing``).
        Items respektieren ``hide_from_bring`` und Per-Produkt-Override-Namen.
        """
        source = self.settings.get('bring_source', 'shopping_list')
        overrides = get_bring_overrides()

        # Quantity-Units in einem Lookup zwischenspeichern
        try:
            qu_map = {q['id']: q for q in self.grocy.get_quantity_units()}
        except Exception:
            qu_map = {}

        # Alle Produkte fuer Namen + QU-Defaults
        try:
            products = self.grocy.get_all_products()
        except Exception as e:
            raise BringSyncError(f"Grocy-Produkte konnten nicht geladen werden: {e}")
        product_map = {p['id']: p for p in products}

        items = []
        if source == 'shopping_list':
            try:
                rows = self.grocy.get_shopping_list()
            except Exception as e:
                raise BringSyncError(f"Grocy-Shoppinglist konnte nicht geladen werden: {e}")
            for row in rows:
                pid = row.get('product_id')
                if not pid:
                    # Eintraege ohne Produktbindung (Freitext) ignorieren - v1
                    continue
                pid = int(pid)
                product = product_map.get(pid)
                if not product:
                    continue
                amount = row.get('amount')
                qu_id = row.get('qu_id') or product.get('qu_id_purchase')
                items.append(self._mk_item(pid, product, amount, qu_id, qu_map, overrides))
        elif source == 'missing':
            try:
                volatile = self.grocy.get_volatile_stock(due_soon_days=0)
            except Exception as e:
                raise BringSyncError(f"Grocy-Volatile-Stock konnte nicht geladen werden: {e}")
            for row in volatile.get('missing_products', []):
                pid = row.get('id') or row.get('product_id')
                if not pid:
                    continue
                pid = int(pid)
                product = product_map.get(pid) or row.get('product') or {}
                amount = row.get('amount_missing')
                qu_id = product.get('qu_id_purchase')
                items.append(self._mk_item(pid, product, amount, qu_id, qu_map, overrides))
        else:
            raise BringSyncError(f"Unbekannte Bring-Quelle: {source}")

        # ``hide_from_bring`` filtert vollstaendig raus
        return [i for i in items if i is not None]

    def _mk_item(self, pid, product, amount, qu_id, qu_map, overrides):
        ov = overrides.get(pid, {})
        if ov.get('hide_from_bring'):
            return None

        name = ov.get('custom_name') or product.get('name') or f'Produkt #{pid}'
        name = _sanitize_name(name)
        if not name:
            return None

        if ov.get('custom_spec'):
            spec = ov['custom_spec']
        else:
            qu_name = ''
            qu = qu_map.get(qu_id) if qu_id else None
            if qu:
                # Wenn amount > 1 und Plural-Form gepflegt, diese nutzen
                try:
                    is_plural = float(amount or 0) > 1
                except (TypeError, ValueError):
                    is_plural = False
                qu_name = (qu.get('name_plural') if is_plural else qu.get('name')) or qu.get('name', '')
            spec = _format_spec(amount, qu_name)
        spec = _sanitize_name(spec)

        return {
            'product_id': pid,
            'name': name,
            'spec': spec,
        }


# ── Module-Level-Helfer ────────────────────────────────────────────────

def _chunked(seq, size):
    """Zerlegt eine Sequenz in Bloecke fester Groesse."""
    for start in range(0, len(seq), size):
        yield seq[start:start + size]


def run_bring_sync():
    """Scheduler-Entry-Point: fuehrt einen Sync aus, fasst Fehler in Logs zusammen."""
    settings = get_all_settings()
    if settings.get('bring_sync_enabled', '0') != '1':
        logger.debug("Bring-Sync deaktiviert, ueberspringe.")
        return None
    try:
        sync = BringSync()
        stats = sync.sync_all()
        # Das Anwendungsprotokoll bleibt deutsch (Betriebsdiagnostik), der
        # Eintrag im Log der Oberflaeche wird uebersetzt -- der ist Nutzertext.
        logger.info(f"Bring-Sync OK: +{stats['added']} aktualisiert={stats['updated']} "
                    f"unveraendert={stats['skipped']} entfernt={stats['removed']} "
                    f"fehler={stats['errors']}")
        werte = {'added': stats['added'], 'updated': stats['updated'],
                 'skipped': stats['skipped'], 'removed': stats['removed'],
                 'errors': stats['errors']}
        add_log_entry(None, 'bring_sync', 'Bring!',
                      sprache.t('log.bring_sync_job', **werte),
                      success=stats['errors'] == 0,
                      key='log.bring_sync_job', args=werte)
        return stats
    except BringSyncError as e:
        logger.error(f"Bring-Sync Konfigurationsfehler: {e}")
        add_log_entry(None, 'bring_sync', 'Bring!', str(e), success=False)
    except Exception as e:
        logger.exception("Bring-Sync unerwarteter Fehler")
        add_log_entry(None, 'bring_sync', 'Bring!', str(e), success=False)
    return None
