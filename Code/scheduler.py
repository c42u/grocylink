import json
import logging
from datetime import datetime, timedelta
from grocy_client import GrocyClient
from notifiers import get_notifier
from database import (
    get_all_settings, get_channels_decrypted, get_product_overrides,
    add_log_entry, get_tracker_entry, upsert_tracker_entry, cleanup_tracker
)

logger = logging.getLogger(__name__)


TRANSLATIONS = {
    'de': {
        'expiry_date': 'Ablaufdatum (MHD)',
        'use_by_date': 'Verbrauchsdatum',
        'expired_since': 'Abgelaufen seit (MHD)',
        'use_by_since': 'Verbrauchsdatum überschritten seit',
        'missing_amount': 'Fehlmenge',
        'unknown': 'Unbekannt',
        'product_nr': 'Produkt',
        'type_expiring': 'Bald ablaufend',
        'type_expired': 'Abgelaufen',
        'type_missing': 'Mindestbestand unterschritten',
        'title': 'Grocy Warnung: {count} Produkt(e) erfordern Aufmerksamkeit',
    },
    'en': {
        'expiry_date': 'Best before date',
        'use_by_date': 'Use by date',
        'expired_since': 'Best before exceeded since',
        'use_by_since': 'Use by date exceeded since',
        'missing_amount': 'Missing amount',
        'unknown': 'Unknown',
        'product_nr': 'Product',
        'type_expiring': 'Expiring soon',
        'type_expired': 'Expired',
        'type_missing': 'Below minimum stock',
        'title': 'Grocy Warning: {count} product(s) require attention',
    },
}


def _t(lang, key):
    return TRANSLATIONS.get(lang, TRANSLATIONS['de']).get(key, TRANSLATIONS['de'].get(key, key))


def run_check():
    logger.info("Starte Grocy Stock-Check...")
    settings = get_all_settings()
    lang = settings.get('language', 'de')

    grocy_url = settings.get('grocy_url', '')
    api_key = settings.get('grocy_api_key', '')
    if not grocy_url or not api_key:
        logger.warning("Grocy nicht konfiguriert, Check übersprungen.")
        return

    default_days = int(settings.get('default_days_before_expiry', 5))
    notify_expiring = settings.get('notify_expiring', '1') == '1'
    notify_expired = settings.get('notify_expired', '1') == '1'
    notify_missing = settings.get('notify_missing', '1') == '1'

    client = GrocyClient(grocy_url, api_key)

    try:
        volatile = client.get_volatile_stock(due_soon_days=default_days)
    except Exception as e:
        logger.error(f"Grocy API Fehler: {e}")
        return

    # Overrides als vollstaendige Dicts laden (inkl. custom_repeat_limit)
    overrides = {o['product_id']: o for o in get_product_overrides()}

    # Kategorie- und Lagerort-Filter (leer = alle)
    allowed_groups_raw = settings.get('notify_product_groups', '')
    allowed_locations_raw = settings.get('notify_locations', '')
    allowed_groups = [int(x) for x in allowed_groups_raw.split(',') if x.strip().lstrip('-').isdigit()]
    allowed_locations = [int(x) for x in allowed_locations_raw.split(',') if x.strip().lstrip('-').isdigit()]

    def _is_filtered(item, product_id):
        """Gibt True zurueck wenn das Produkt durch Kategorie/Lagerort-Filter ausgeschlossen wird.
        Produkte mit explizitem Per-Produkt-Wiederholungslimit umgehen den Filter (Vorrang-Regel)."""
        override = overrides.get(product_id)
        # Wenn ein individuelles Wiederholungslimit gesetzt ist, Filter umgehen
        if override is not None and override.get('custom_repeat_limit') is not None:
            return False
        product = item.get('product', item)
        if allowed_groups:
            pg = product.get('product_group_id')
            if pg is not None and int(pg) not in allowed_groups:
                return True
        if allowed_locations:
            loc = product.get('location_id')
            if loc is not None and int(loc) not in allowed_locations:
                return True
        return False

    alerts = []

    if notify_expiring:
        for item in volatile.get('due_products', []):
            product_id = item.get('product_id') or item.get('product', {}).get('id')
            product = item.get('product', {})
            product_name = product.get('name', f'{_t(lang, "product_nr")} #{product_id}')
            best_before = item.get('best_before_date', '')

            if _is_filtered(item, product_id):
                continue

            if product_id in overrides:
                custom_days = overrides[product_id]['custom_days_before_expiry']
                if custom_days == 0:
                    continue  # Benachrichtigungen fuer dieses Produkt deaktiviert
                if custom_days > 0 and best_before:
                    # Positiver Wert: individuelle Wartschwelle pruefen
                    try:
                        exp_date = datetime.strptime(best_before, '%Y-%m-%d')
                        if exp_date > datetime.now() + timedelta(days=custom_days):
                            continue
                    except ValueError:
                        pass
                # custom_days == -1: globalen Standard verwenden (kein zusaetzlicher Check)

            due_type = product.get('due_type', 1)
            date_label = _t(lang, 'use_by_date') if due_type == 2 else _t(lang, 'expiry_date')
            alerts.append({
                'type': 'expiring',
                'name': product_name,
                'detail': f"{date_label}: {best_before}",
                'product_id': str(product_id or ''),
                'best_before': best_before,
            })

    if notify_expired:
        for item in volatile.get('overdue_products', []) + volatile.get('expired_products', []):
            product_id = item.get('product_id') or item.get('product', {}).get('id')
            product = item.get('product', {})
            product_name = product.get('name', _t(lang, 'unknown'))
            best_before = item.get('best_before_date', '')

            if _is_filtered(item, product_id):
                continue

            if product_id in overrides and overrides[product_id]['custom_days_before_expiry'] == 0:
                continue  # Benachrichtigungen fuer dieses Produkt deaktiviert

            due_type = product.get('due_type', 1)
            date_label = _t(lang, 'use_by_since') if due_type == 2 else _t(lang, 'expired_since')
            alerts.append({
                'type': 'expired',
                'name': product_name,
                'detail': f"{date_label}: {best_before}",
                'product_id': str(product_id or ''),
                'best_before': best_before,
            })

    if notify_missing:
        for item in volatile.get('missing_products', []):
            product_id = item.get('id') or item.get('product_id') or item.get('product', {}).get('id')
            product_name = item.get('product', {}).get('name', item.get('name', _t(lang, 'unknown')))
            amount_missing = item.get('amount_missing', '?')

            if _is_filtered(item, product_id):
                continue

            if product_id in overrides and overrides[product_id]['custom_days_before_expiry'] == 0:
                continue  # Benachrichtigungen fuer dieses Produkt deaktiviert

            alerts.append({
                'type': 'missing',
                'name': product_name,
                'detail': f"{_t(lang, 'missing_amount')}: {amount_missing}",
                'product_id': str(product_id or ''),
                'best_before': '',
            })

    if not alerts:
        logger.info("Keine Warnungen gefunden.")
        return

    global_repeat_limit = int(settings.get('notification_repeat_limit', '1'))

    # Tracker bereinigen: Eintraege fuer Produkte, die nicht mehr im Alert-Zustand sind, loeschen
    active_keys = {(a['product_id'], a['type']) for a in alerts}
    cleanup_tracker(active_keys)

    # Alerts nach Wiederholungslimit filtern
    # Prioritaet: Per-Produkt-Limit > Globales Limit (0 = unbegrenzt)
    filtered = []
    for alert in alerts:
        override = overrides.get(alert['product_id'])
        # Effektives Limit bestimmen: Per-Produkt hat Vorrang
        if override is not None and override.get('custom_repeat_limit') is not None:
            effective_limit = override['custom_repeat_limit']
        else:
            effective_limit = global_repeat_limit
        if effective_limit > 0:
            entry = get_tracker_entry(alert['product_id'], alert['type'])
            if entry and entry['best_before_date'] == alert['best_before'] and entry['sent_count'] >= effective_limit:
                logger.debug(
                    f"Wiederholungslimit ({effective_limit}) erreicht fuer "
                    f"{alert['name']} ({alert['type']}), uebersprungen"
                )
                continue
        filtered.append(alert)
    alerts = filtered

    if not alerts:
        logger.info("Keine neuen Warnungen (Wiederholungslimit fuer alle Produkte erreicht).")
        return

    type_labels = {
        'expiring': _t(lang, 'type_expiring'),
        'expired': _t(lang, 'type_expired'),
        'missing': _t(lang, 'type_missing'),
    }
    lines = []
    for a in alerts:
        lines.append(f"[{type_labels.get(a['type'], a['type'])}] {a['name']} - {a['detail']}")

    title = _t(lang, 'title').replace('{count}', str(len(alerts)))
    message = "\n".join(lines)

    channels = get_channels_decrypted()
    for ch in channels:
        if not ch['enabled']:
            continue
        try:
            config = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
            notifier = get_notifier(ch['type'], config)
            notifier.send(title, message)
            for a in alerts:
                add_log_entry(a['name'], a['type'], ch['name'], a['detail'], success=True)
            logger.info(f"Benachrichtigung via {ch['name']} gesendet.")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"Fehler bei Kanal {ch['name']}: {error_detail}")
            add_log_entry(None, 'error', ch['name'], str(e), success=False)

    # Tracker aktualisieren: gesendete Alerts zaehlen
    for alert in alerts:
        upsert_tracker_entry(alert['product_id'], alert['type'], alert['best_before'])
