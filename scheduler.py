import json
import logging
from datetime import datetime, timedelta
from grocy_client import GrocyClient
from notifiers import get_notifier
from database import (
    get_all_settings, get_channels_decrypted, get_product_overrides,
    add_log_entry
)

logger = logging.getLogger(__name__)


TRANSLATIONS = {
    'de': {
        'expiry_date': 'Ablaufdatum',
        'expired_since': 'Abgelaufen seit',
        'missing_amount': 'Fehlmenge',
        'unknown': 'Unbekannt',
        'product_nr': 'Produkt',
        'type_expiring': 'Bald ablaufend',
        'type_expired': 'Abgelaufen',
        'type_missing': 'Mindestbestand unterschritten',
        'title': 'Grocy Warnung: {count} Produkt(e) erfordern Aufmerksamkeit',
    },
    'en': {
        'expiry_date': 'Expiry date',
        'expired_since': 'Expired since',
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

    overrides = {o['product_id']: o['custom_days_before_expiry'] for o in get_product_overrides()}

    alerts = []

    if notify_expiring:
        for item in volatile.get('due_products', []):
            product_id = item.get('product_id') or item.get('product', {}).get('id')
            product_name = item.get('product', {}).get('name', f'{_t(lang, "product_nr")} #{product_id}')
            best_before = item.get('best_before_date', '')

            if product_id in overrides:
                custom_days = overrides[product_id]
                if best_before:
                    try:
                        exp_date = datetime.strptime(best_before, '%Y-%m-%d')
                        if exp_date > datetime.now() + timedelta(days=custom_days):
                            continue
                    except ValueError:
                        pass

            alerts.append({
                'type': 'expiring',
                'name': product_name,
                'detail': f"{_t(lang, 'expiry_date')}: {best_before}",
            })

    if notify_expired:
        for item in volatile.get('overdue_products', []) + volatile.get('expired_products', []):
            product_name = item.get('product', {}).get('name', _t(lang, 'unknown'))
            best_before = item.get('best_before_date', '')
            alerts.append({
                'type': 'expired',
                'name': product_name,
                'detail': f"{_t(lang, 'expired_since')}: {best_before}",
            })

    if notify_missing:
        for item in volatile.get('missing_products', []):
            product_name = item.get('product', {}).get('name', item.get('name', _t(lang, 'unknown')))
            amount_missing = item.get('amount_missing', '?')
            alerts.append({
                'type': 'missing',
                'name': product_name,
                'detail': f"{_t(lang, 'missing_amount')}: {amount_missing}",
            })

    if not alerts:
        logger.info("Keine Warnungen gefunden.")
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
