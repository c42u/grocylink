import json
import logging
import os
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

import sprache
from database import (
    init_db, get_all_settings, save_settings,
    get_channels, get_channels_decrypted, save_channel, delete_channel,
    get_product_overrides, save_product_override, delete_product_override,
    get_log, clear_log, get_sync_map, clear_sync_map, add_log_entry,
    save_receipt, get_receipts, get_receipt, update_receipt_status,
    delete_receipt as db_delete_receipt, save_receipt_items, update_receipt_item,
    get_receipt_item, get_product_mappings_dict, get_product_mappings,
    save_product_mapping, delete_product_mapping, receipt_filepath_exists,
    get_bring_sync_map, clear_bring_sync_map, get_bring_overrides_list,
    save_bring_override, delete_bring_override,
)
from grocy_client import GrocyClient
from notifiers import get_notifier
from scheduler import run_check
from caldav_sync import CalDAVSync, run_caldav_sync
from bring_sync import BringSync, run_bring_sync, BringSyncError
from bring_runtime import invalidate_runtime
from receipt_scanner import process_receipt, scan_receipt_folder

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

APP_VERSION = '1.7.1'

# Grocy-Userfield, in dem Grocylink den Stueckpreis aus Bring! ablegt.
# Hat Vorrang vor `last_price`/`avg_price` aus dem Stock-Log.
BRING_UNIT_PRICE_FIELD = 'grocylink_unit_price'

# Erkennt Bring-Specs der Form "3x Vollmilch" / "2,5 x Bio Quark" / "5X bla".
# Anzahl + 'x' am Anfang = Quantity, der Rest = Info. Funktioniert auch
# wenn nur die Anzahl gesetzt ist (z.B. "3x") -> Info ist dann leer.
# \s erfasst auch NBSP ( ) und Tabs.
import re as _re
_SPEC_QTY_RE = _re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s*[xX]\s*(.*)$')


def _parse_spec(spec):
    """Zerlegt einen Spec-String in (quantity:float|None, info:str)."""
    if not spec:
        return None, ''
    # NBSP zu normalem Space, dann trim
    normalized = spec.replace(' ', ' ').strip()
    if not normalized:
        return None, ''
    m = _SPEC_QTY_RE.match(normalized)
    if not m:
        return None, normalized
    try:
        qty = float(m.group(1).replace(',', '.'))
    except ValueError:
        return None, normalized
    return qty, (m.group(2) or '').strip()


def _build_spec(quantity, info):
    """Baut Spec-String fuer Bring aus Anzahl + Info: '3x Vollmilch'."""
    info = (info or '').strip()
    if quantity is None:
        return info
    # Huebsche Formatierung: 3 statt 3.0, aber 2.5 bleibt 2.5
    if float(quantity).is_integer():
        qty_str = str(int(quantity))
    else:
        qty_str = str(quantity).rstrip('0').rstrip('.')
    return (qty_str + 'x' + (' ' + info if info else '')).strip()

app = Flask(__name__)

init_db()

bg_scheduler = BackgroundScheduler(daemon=True)
bg_scheduler.start()


def schedule_check():
    bg_scheduler.remove_all_jobs()
    settings = get_all_settings()
    hours = int(settings.get('check_interval_hours', 6))
    if hours > 0:
        bg_scheduler.add_job(run_check, 'interval', hours=hours, id='grocy_check', replace_existing=True)
        logger.info(f"Check geplant: alle {hours} Stunden")


@app.route('/')
def index():
    """Startseite -- mit der **eingestellten** Sprache im HTML.

    Vorher stand dort fest `lang="de"`, und das Frontend holte seine Sprache
    aus dem `localStorage` des Browsers. Wer die Seite in einem anderen Fenster
    oder auf einem anderen Geraet oeffnete, sah wieder Deutsch, obwohl in den
    Einstellungen Englisch stand (GitHub-Fehler #1). Jetzt kommt die Sprache
    vom Server -- und zwar schon im ausgelieferten HTML, damit die Seite nicht
    erst auf Deutsch aufblitzt.
    """
    return render_template('index.html', version=APP_VERSION,
                           lang=sprache.sprache_lesen())


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(get_all_settings())


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.get_json()
    save_settings(data)
    # Geaenderte Bring-Zugangsdaten: gecachten Client sofort verwerfen,
    # damit keine Session mit veralteten Daten offen bleibt
    if any(k in data for k in ('bring_email', 'bring_password')):
        invalidate_runtime()
    schedule_check()
    schedule_caldav_sync()
    schedule_bring_sync()
    schedule_receipt_watch()
    return jsonify({'ok': True})


@app.route('/api/test-connection', methods=['POST'])
def api_test_connection():
    data = request.get_json()
    client = GrocyClient(data.get('grocy_url'), data.get('grocy_api_key'))
    client.verify_ssl = data.get('grocy_verify_ssl', '1') != '0'
    ok, msg = client.test_connection()
    return jsonify({'ok': ok, 'message': msg})


@app.route('/api/status', methods=['GET'])
def api_status():
    settings = get_all_settings()
    if not settings.get('grocy_url') or not settings.get('grocy_api_key'):
        return jsonify({'error': sprache.t('msg.grocy_missing')}), 400
    try:
        client = GrocyClient()
        days = int(settings.get('default_days_before_expiry', 5))
        volatile = client.get_volatile_stock(due_soon_days=days)
        stock = client.get_all_stock()
        return jsonify({
            'due_products': volatile.get('due_products', []),
            'overdue_products': volatile.get('overdue_products', []),
            'expired_products': volatile.get('expired_products', []),
            'missing_products': volatile.get('missing_products', []),
            'total_products': len(stock),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/channels', methods=['GET'])
def api_get_channels():
    channels = get_channels_decrypted()
    for ch in channels:
        ch['config'] = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
        del ch['config_json']
    return jsonify(channels)


@app.route('/api/channels', methods=['POST'])
def api_save_channel():
    data = request.get_json()
    save_channel(data)
    return jsonify({'ok': True})


@app.route('/api/channels/<int:channel_id>', methods=['DELETE'])
def api_delete_channel(channel_id):
    delete_channel(channel_id)
    return jsonify({'ok': True})


@app.route('/api/channels/<int:channel_id>/test', methods=['POST'])
def api_test_channel(channel_id):
    channels = get_channels_decrypted()
    ch = next((c for c in channels if c['id'] == channel_id), None)
    if not ch:
        return jsonify({'ok': False, 'message': sprache.t('msg.channel_missing')}), 404
    try:
        config = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
        notifier = get_notifier(ch['type'], config)
        notifier.test()
        add_log_entry(None, 'test', ch['name'], sprache.t('log.test_sent'),
                      success=True, key='log.test_sent')
        return jsonify({'ok': True, 'message': sprache.t('msg.test_sent')})
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Testfehler bei Kanal {ch['name']}: {error_detail}")
        add_log_entry(None, 'test', ch['name'], str(e), success=False)
        return jsonify({'ok': False, 'message': str(e), 'detail': error_detail})


@app.route('/api/products', methods=['GET'])
def api_get_products():
    """Liefert ALLE in Grocy definierten Produkte (nicht nur Produkte mit Bestand),
    ergaenzt um Bestandsdaten und individuelle Override-Einstellungen."""
    settings = get_all_settings()
    overrides = {o['product_id']: o for o in get_product_overrides()}
    products = []
    if settings.get('grocy_url') and settings.get('grocy_api_key'):
        try:
            client = GrocyClient()
            # Alle Produkte aus Grocy laden (unabhaengig vom Bestand)
            all_prods = client.get_all_products()
            # Bestandsdaten fuer Menge und MHD laden
            stock_by_id = {}
            try:
                for item in client.get_all_stock():
                    pid = item.get('product_id') or item.get('product', {}).get('id')
                    if pid is not None:
                        stock_by_id[pid] = item
            except Exception:
                pass
            # Alphabetisch sortieren
            all_prods.sort(key=lambda p: (p.get('name') or '').lower())
            for prod in all_prods:
                pid = prod.get('id')
                name = prod.get('name', f'Produkt #{pid}')
                stock_item = stock_by_id.get(pid)
                override = overrides.get(pid)
                # custom_days == -1 bedeutet "globalen Standard verwenden" (nur repeat gesetzt)
                cdays = override['custom_days_before_expiry'] if override else None
                products.append({
                    'product_id': pid,
                    'name': name,
                    'amount': stock_item.get('amount', '-') if stock_item else '-',
                    'best_before_date': stock_item.get('best_before_date', '') if stock_item else '',
                    'custom_days': cdays if cdays is not None and cdays >= 0 else None,
                    'custom_repeat_limit': override.get('custom_repeat_limit') if override else None,
                })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'products': products, 'overrides': list(overrides.values())})


@app.route('/api/products/override', methods=['POST'])
def api_save_override():
    data = request.get_json()
    if data.get('delete'):
        delete_product_override(data['product_id'])
    else:
        # repeat_limit: None = globales Limit verwenden, 0 = immer, 1+ = N-mal
        repeat_limit = data.get('repeat_limit')
        if repeat_limit is not None:
            repeat_limit = int(repeat_limit)
        save_product_override(
            data['product_id'], data['product_name'],
            data['days'], repeat_limit=repeat_limit
        )
    return jsonify({'ok': True})


@app.route('/api/grocy/stock/add', methods=['POST'])
def api_grocy_stock_add():
    data = request.get_json()
    product_id = data.get('product_id')
    amount = data.get('amount')
    if not product_id or not amount:
        return jsonify({'error': sprache.t('msg.need_product_amount')}), 400
    try:
        client = GrocyClient()
        result = client.add_stock(
            product_id, amount,
            best_before_date=data.get('best_before_date') or None,
            price=data.get('price') or None,
        )
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocy/product-groups', methods=['GET'])
def api_grocy_product_groups():
    try:
        client = GrocyClient()
        groups = client.get_product_groups()
        return jsonify(groups)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocy/locations', methods=['GET'])
def api_grocy_locations():
    try:
        client = GrocyClient()
        locations = client.get_locations()
        return jsonify(locations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocy/quantity-units', methods=['GET'])
def api_grocy_quantity_units():
    try:
        client = GrocyClient()
        units = client.get_quantity_units()
        return jsonify(units)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/openfoodfacts/suggest', methods=['POST'])
def api_openfoodfacts_suggest():
    """Sucht bei OpenFoodFacts und liefert mehrere Produktvorschlaege
    mit Bild, Barcode, Naehrwerten und Kategorie-Match zurueck.

    Antwort: {suggestions: [...], category, product_group_id, raw_categories}
    Jeder Suggestion-Eintrag: {product_name, image_url, barcode, score,
      nutrition: {energy_kcal, fat, saturated_fat, carbs, sugars, protein, salt, fiber}}
    """
    data = request.get_json()
    name = (data.get('name') or '').strip()
    receipt_price = data.get('price')  # Preis vom Kassenbon fuer Score-Berechnung
    if not name:
        return jsonify({'suggestions': [], 'category': None, 'product_group_id': None, 'raw_categories': []})
    empty = {'suggestions': [], 'category': None, 'product_group_id': None, 'raw_categories': [],
             'image_url': None, 'barcode': None, 'off_product_name': None}
    try:
        import requests as req
        from rapidfuzz import fuzz
        resp = req.get(
            'https://de.openfoodfacts.org/cgi/search.pl',
            params={'search_terms': name, 'search_simple': 1, 'action': 'process', 'json': 1, 'page_size': 8},
            headers={'User-Agent': 'Grocylink/1.5.0 (grocylink@c42u.de)'},
            timeout=10,
        )
        resp.raise_for_status()
        products = resp.json().get('products', [])
        if not products:
            return jsonify(empty)

        # Alle Produkte als Vorschlaege aufbereiten
        suggestions = []
        for p in products:
            p_name = (p.get('product_name_de') or p.get('product_name') or '').strip()
            if not p_name:
                continue
            barcode = p.get('code') or None
            image_url = p.get('image_front_small_url') or p.get('image_front_url') or None

            # Naehrwerte extrahieren
            nutriments = p.get('nutriments', {})
            nutrition = {
                'energy_kcal': nutriments.get('energy-kcal_100g'),
                'fat': nutriments.get('fat_100g'),
                'saturated_fat': nutriments.get('saturated-fat_100g'),
                'carbs': nutriments.get('carbohydrates_100g'),
                'sugars': nutriments.get('sugars_100g'),
                'protein': nutriments.get('proteins_100g'),
                'salt': nutriments.get('salt_100g'),
                'fiber': nutriments.get('fiber_100g'),
            }

            # Namens-Score berechnen (wie gut passt der OFF-Name zum Bon-Namen)
            name_score = round(fuzz.token_sort_ratio(name.upper(), p_name.upper()), 1)

            # Preis-Score: wenn Bon-Preis vorhanden und OFF hat Preisvergleich
            price_score = None
            if receipt_price:
                # Kein Preis in OFF vorhanden, daher nur Name-Score
                price_score = None

            suggestions.append({
                'product_name': p_name,
                'brand': (p.get('brands') or '').strip(),
                'image_url': image_url,
                'barcode': barcode,
                'name_score': name_score,
                'nutrition': nutrition,
                'quantity_text': p.get('quantity') or '',
            })

        # Nach Score sortieren (beste Uebereinstimmung zuerst)
        suggestions.sort(key=lambda s: s['name_score'], reverse=True)

        # Bestes Produkt fuer Rueckwaertskompatibilitaet
        best = suggestions[0] if suggestions else {}
        image_url = best.get('image_url')
        barcode = best.get('barcode')
        off_name = best.get('product_name')

        raw_categories = []
        for p in products:
            cats = p.get('categories_tags_de') or p.get('categories_tags') or []
            if isinstance(cats, str):
                cats = [c.strip() for c in cats.split(',')]
            raw_categories.extend(cats)
        raw_categories = list(dict.fromkeys(raw_categories))

        result = {
            'suggestions': suggestions,
            'raw_categories': raw_categories,
            'image_url': image_url,
            'barcode': barcode,
            'off_product_name': off_name,
        }

        if not raw_categories:
            result.update({'category': None, 'product_group_id': None})
            return jsonify(result)

        # Fuzzy-Match gegen Grocy-Produktgruppen
        client = GrocyClient()
        groups = client.get_product_groups()
        best_match = None
        best_score = 0
        best_group_id = None
        for cat in raw_categories:
            cat_clean = cat.split(':')[-1].strip() if ':' in cat else cat.strip()
            for g in groups:
                score = fuzz.token_sort_ratio(cat_clean.lower(), g['name'].lower())
                if score > best_score:
                    best_score = score
                    best_match = g['name']
                    best_group_id = g['id']
        if best_score < 40:
            result.update({'category': None, 'product_group_id': None})
        else:
            result.update({'category': best_match, 'product_group_id': best_group_id})
        return jsonify(result)
    except Exception as e:
        logger.error(f"OpenFoodFacts Fehler: {e}")
        empty['error'] = str(e)
        return jsonify(empty)


@app.route('/api/grocy/userfields', methods=['GET'])
def api_grocy_userfields():
    """Liefert alle Benutzerfelder fuer Produkte."""
    try:
        client = GrocyClient()
        fields = client.get_userfields('products')
        return jsonify(fields)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/grocy/products/<int:product_id>/userfields', methods=['PUT'])
def api_set_product_userfields(product_id):
    """Setzt Benutzerfelder (z.B. Naehrwerte) fuer ein Produkt."""
    data = request.get_json()
    try:
        client = GrocyClient()
        client.set_product_userfields(product_id, data)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/barcode/search', methods=['POST'])
def api_barcode_search():
    """Sucht Barcodes fuer ein Produkt ueber externe Datenbanken (OpenFoodFacts).

    Gibt eine Liste von Barcode-Vorschlaegen zurueck, jeweils mit EAN,
    Produktname, Bild-URL und Quelle.
    """
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'suggestions': []})
    suggestions = []
    try:
        import requests as req
        resp = req.get(
            'https://de.openfoodfacts.org/cgi/search.pl',
            params={'search_terms': name, 'search_simple': 1,
                    'action': 'process', 'json': 1, 'page_size': 8},
            headers={'User-Agent': 'Grocylink/1.5.0 (grocylink@c42u.de)'},
            timeout=10,
        )
        resp.raise_for_status()
        products = resp.json().get('products', [])
        seen_barcodes = set()
        for p in products:
            barcode = p.get('code') or ''
            if not barcode or barcode in seen_barcodes:
                continue
            seen_barcodes.add(barcode)
            p_name = (p.get('product_name_de') or p.get('product_name') or '').strip()
            if not p_name:
                continue
            suggestions.append({
                'barcode': barcode,
                'product_name': p_name,
                'image_url': p.get('image_front_small_url') or p.get('image_front_url') or None,
                'source': 'OpenFoodFacts',
            })
    except Exception as e:
        logger.error(f"Barcode-Suche Fehler: {e}")
    return jsonify({'suggestions': suggestions})


@app.route('/api/barcode/lookup', methods=['POST'])
def api_barcode_lookup():
    """Sucht ein Produkt in Grocy anhand eines EAN/Barcodes.

    Falls kein Grocy-Treffer, wird OpenFoodFacts als Fallback abgefragt.
    """
    data = request.get_json()
    barcode = (data.get('barcode') or '').strip()
    if not barcode:
        return jsonify({'grocy_products': [], 'off_product': None})
    try:
        client = _get_grocy_client()
        grocy_products = client.search_product_by_barcode(barcode)
        grocy_results = [{'product_id': p.get('id'), 'name': p.get('name')} for p in grocy_products]
    except Exception as e:
        logger.error(f"Grocy-Barcode-Lookup Fehler: {e}")
        grocy_results = []
    off_product = None
    if not grocy_results:
        try:
            import requests as req
            resp = req.get(
                f'https://world.openfoodfacts.org/api/v2/product/{barcode}.json',
                headers={'User-Agent': 'Grocylink/1.5.0 (grocylink@c42u.de)'},
                timeout=10,
            )
            if resp.status_code == 200:
                pdata = resp.json().get('product', {})
                p_name = (pdata.get('product_name_de') or pdata.get('product_name') or '').strip()
                if p_name:
                    off_product = {
                        'barcode': barcode,
                        'name': p_name,
                        'brand': (pdata.get('brands') or '').strip(),
                        'image_url': pdata.get('image_front_small_url') or pdata.get('image_front_url'),
                    }
        except Exception as e:
            logger.error(f"OFF-Barcode-Lookup Fehler: {e}")
    return jsonify({'grocy_products': grocy_results, 'off_product': off_product})


@app.route('/api/log', methods=['GET'])
def api_get_log():
    return jsonify(get_log(limit=200))


@app.route('/api/log', methods=['DELETE'])
def api_clear_log():
    clear_log()
    return jsonify({'ok': True})


@app.route('/api/check-now', methods=['POST'])
def api_check_now():
    try:
        run_check()
        return jsonify({'ok': True, 'message': sprache.t('msg.check_done')})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)})


@app.route('/api/caldav/status', methods=['GET'])
def api_caldav_status():
    settings = get_all_settings()
    sync_map = get_sync_map()
    tasks_synced = sum(1 for s in sync_map if s['grocy_type'] == 'task')
    chores_synced = sum(1 for s in sync_map if s['grocy_type'] == 'chore')
    last_sync = max((s['last_synced'] for s in sync_map), default=None)
    return jsonify({
        'enabled': settings.get('caldav_sync_enabled', '0') == '1',
        'caldav_url': settings.get('caldav_url', ''),
        'caldav_path': settings.get('caldav_path', ''),
        'caldav_username': settings.get('caldav_username', ''),
        'caldav_verify_ssl': settings.get('caldav_verify_ssl', '1'),
        'has_caldav_password': bool(settings.get('caldav_password', '')),
        'caldav_calendar': settings.get('caldav_calendar', ''),
        'sync_interval': settings.get('caldav_sync_interval_minutes', '30'),
        'tasks_synced': tasks_synced,
        'chores_synced': chores_synced,
        'last_sync': last_sync,
        'total_synced': len(sync_map),
    })


@app.route('/api/caldav/test', methods=['POST'])
def api_caldav_test():
    data = request.get_json()
    to_save = {
        'caldav_url': data.get('caldav_url', ''),
        'caldav_path': data.get('caldav_path', ''),
        'caldav_username': data.get('caldav_username', ''),
        'caldav_verify_ssl': data.get('caldav_verify_ssl', '1'),
    }
    if data.get('caldav_password'):
        to_save['caldav_password'] = data['caldav_password']
    save_settings(to_save)
    try:
        sync = CalDAVSync()
        ok, msg = sync.test_connection()
        return jsonify({'ok': ok, 'message': msg})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)})


@app.route('/api/caldav/calendars', methods=['GET'])
def api_caldav_calendars():
    try:
        sync = CalDAVSync()
        calendars = sync.get_calendars()
        return jsonify({'ok': True, 'calendars': calendars})
    except Exception as e:
        return jsonify({'ok': False, 'calendars': [], 'message': str(e)})


@app.route('/api/caldav/sync-now', methods=['POST'])
def api_caldav_sync_now():
    try:
        sync = CalDAVSync()
        stats = sync.sync_all()
        return jsonify({'ok': True, 'message': sprache.t('msg.sync_done'), 'stats': stats})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)})


@app.route('/api/caldav/map', methods=['GET', 'DELETE'])
def api_caldav_map():
    if request.method == 'DELETE':
        clear_sync_map()
        return jsonify({'ok': True})
    return jsonify(get_sync_map())


def schedule_caldav_sync():
    settings = get_all_settings()
    bg_scheduler.remove_job('caldav_sync', jobstore='default')  if bg_scheduler.get_job('caldav_sync') else None
    if settings.get('caldav_sync_enabled', '0') == '1':
        minutes = int(settings.get('caldav_sync_interval_minutes', 30))
        if minutes > 0:
            bg_scheduler.add_job(run_caldav_sync, 'interval', minutes=minutes,
                                 id='caldav_sync', replace_existing=True)
            logger.info(f"CalDAV Sync geplant: alle {minutes} Minuten")


# ── Bring!-Endpunkte ─────────────────────────────────────────────────

@app.route('/api/bring/status', methods=['GET'])
def api_bring_status():
    settings = get_all_settings()
    sync_map = get_bring_sync_map()
    last_sync = max((s['last_synced'] for s in sync_map), default=None)
    return jsonify({
        'enabled': settings.get('bring_sync_enabled', '0') == '1',
        'bring_email': settings.get('bring_email', ''),
        'has_bring_password': bool(settings.get('bring_password', '')),
        'bring_list_uuid': settings.get('bring_list_uuid', ''),
        'sync_interval': settings.get('bring_sync_interval_minutes', '30'),
        'source': settings.get('bring_source', 'shopping_list'),
        'auto_remove': settings.get('bring_auto_remove', '0') == '1',
        'sync_direction': settings.get('bring_sync_direction', 'grocy_to_bring'),
        'items_synced': len(sync_map),
        'last_sync': last_sync,
    })


@app.route('/api/bring/test', methods=['POST'])
def api_bring_test():
    data = request.get_json() or {}
    to_save = {'bring_email': data.get('bring_email', '')}
    if data.get('bring_password'):
        to_save['bring_password'] = data['bring_password']
    save_settings(to_save)
    invalidate_runtime()
    try:
        sync = BringSync()
        ok, msg = sync.test_connection(
            email=data.get('bring_email'),
            password=data.get('bring_password'),
        )
        return jsonify({'ok': ok, 'message': msg})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)})


@app.route('/api/bring/lists', methods=['GET'])
def api_bring_lists():
    try:
        sync = BringSync()
        lists = sync.get_lists()
        return jsonify({'ok': True, 'lists': lists})
    except BringSyncError as e:
        return jsonify({'ok': False, 'lists': [], 'message': str(e)})
    except Exception as e:
        return jsonify({'ok': False, 'lists': [], 'message': str(e)})


@app.route('/api/bring/sync-now', methods=['POST'])
def api_bring_sync_now():
    try:
        sync = BringSync()
        stats = sync.sync_all()
        werte = {'added': stats['added'], 'updated': stats['updated'],
                 'removed': stats['removed'], 'errors': stats['errors']}
        msg = sprache.t('log.bring_sync', **werte)
        add_log_entry(None, 'bring_sync', 'Bring!', msg,
                      success=stats['errors'] == 0,
                      key='log.bring_sync', args=werte)
        return jsonify({'ok': True, 'message': msg, 'stats': stats})
    except BringSyncError as e:
        add_log_entry(None, 'bring_sync', 'Bring!', str(e), success=False)
        return jsonify({'ok': False, 'message': str(e)})
    except Exception as e:
        logger.exception("Bring-Sync Fehler")
        add_log_entry(None, 'bring_sync', 'Bring!', str(e), success=False)
        return jsonify({'ok': False, 'message': str(e)})


@app.route('/api/bring/map', methods=['GET', 'DELETE'])
def api_bring_map():
    if request.method == 'DELETE':
        clear_bring_sync_map()
        return jsonify({'ok': True})
    return jsonify(get_bring_sync_map())


@app.route('/api/bring/overrides', methods=['GET'])
def api_bring_overrides():
    return jsonify(get_bring_overrides_list())


@app.route('/api/bring/list-items', methods=['GET'])
def api_bring_list_items():
    """Liefert die aktuell auf einer Bring!-Liste stehenden Produkte,
    angereichert um Grocy-Match (sync_map oder Name) und letzten Preis.

    Query: ?list_uuid=<uuid>
    """
    list_uuid = (request.args.get('list_uuid') or '').strip()
    if not list_uuid:
        return jsonify({'ok': False, 'message': sprache.t('msg.need_list_uuid')}), 400
    try:
        sync = BringSync()
        bring_items = sync.get_list_items(list_uuid)

        # Grocy-Lookups vorbereiten
        client = GrocyClient()
        currency = client.get_currency()
        try:
            all_products = client.get_all_products()
        except Exception:
            all_products = []
        products_by_id = {p.get('id'): p for p in all_products}
        products_by_name = {(p.get('name') or '').lower(): p for p in all_products}
        sync_map_by_uuid = {m['bring_item_uuid']: m for m in get_bring_sync_map()}

        # Fuzzy-Match-Vorbereitung: alle Produkt-Namen in eine Liste
        all_product_names = [(p.get('name') or '', p) for p in all_products if p.get('name')]

        # Pass 1: Bring-Items auf Grocy-Produkte mappen (UUID > exact name >
        # fuzzy). Userfield-Werte kommen direkt aus dem product-Dict, weil
        # show_as_column_in_tables=1 - kein zusaetzlicher API-Call noetig.
        prelim = []
        from rapidfuzz import process, fuzz
        fuzzy_names = [n for n, _ in all_product_names]
        for item in bring_items:
            grocy_pid = None
            grocy_name = None
            unit_price = None
            map_entry = sync_map_by_uuid.get(item['uuid']) if item['uuid'] else None
            if map_entry:
                grocy_pid = map_entry['grocy_product_id']
            else:
                p = products_by_name.get(item['name'].lower())
                if p:
                    grocy_pid = p.get('id')
                elif fuzzy_names:
                    try:
                        best = process.extractOne(
                            item['name'], fuzzy_names,
                            scorer=fuzz.token_set_ratio, score_cutoff=75,
                        )
                        if best:
                            for name, prod in all_product_names:
                                if name == best[0]:
                                    grocy_pid = prod.get('id')
                                    break
                    except Exception as e:
                        logger.debug(f"Fuzzy-Match fuer '{item['name']}': {e}")
            if grocy_pid:
                product = products_by_id.get(grocy_pid) or {}
                grocy_name = product.get('name')
                # Userfield aus Produkt-Dict holen (Grocy serialisiert
                # show_as_column_in_tables-Userfields direkt mit aus).
                raw = product.get(BRING_UNIT_PRICE_FIELD)
                if raw in (None, '', 'null'):
                    raw = (product.get('userfields') or {}).get(BRING_UNIT_PRICE_FIELD)
                if raw not in (None, '', 'null'):
                    try:
                        unit_price = float(str(raw).replace(',', '.'))
                    except (ValueError, TypeError):
                        pass
            prelim.append({
                'item': item, 'grocy_pid': grocy_pid,
                'grocy_name': grocy_name, 'unit_price': unit_price,
            })

        # Pass 2: last_price/avg_price fuer alle Produkte parallel holen.
        # Sequentielle Calls bei 30 Items wuerden 5-10 Sekunden brauchen,
        # parallel mit 8 Workern <= 1 Sekunde.
        unique_pids = sorted({p['grocy_pid'] for p in prelim if p['grocy_pid']})
        last_price_by_pid = {}
        if unique_pids:
            from concurrent.futures import ThreadPoolExecutor
            def _fetch(pid):
                try:
                    details = client.get_product_details(pid)
                    val = details.get('last_price') or details.get('avg_price')
                    return pid, (float(val) if val is not None else None)
                except Exception as e:
                    logger.debug(f"Preis-Lookup {pid}: {e}")
                    return pid, None
            with ThreadPoolExecutor(max_workers=min(8, len(unique_pids))) as ex:
                for pid, lp in ex.map(_fetch, unique_pids):
                    last_price_by_pid[pid] = lp

        # Pass 3: Result zusammensetzen
        result_items = []
        for p in prelim:
            item = p['item']
            grocy_pid = p['grocy_pid']
            unit_price = p['unit_price']
            last_price = last_price_by_pid.get(grocy_pid) if grocy_pid else None
            price = unit_price if unit_price is not None else last_price
            quantity, info = _parse_spec(item['spec'])
            total_price = (quantity or 1) * price if price is not None else None
            result_items.append({
                'name': item['name'],
                'spec': item['spec'],
                'quantity': quantity,
                'info': info,
                'uuid': item['uuid'],
                'grocy_product_id': grocy_pid,
                'grocy_product_name': p['grocy_name'],
                'price': price,
                'unit_price': unit_price,
                'last_price': last_price,
                'total_price': total_price,
            })
        return jsonify({'ok': True, 'items': result_items, 'currency': currency})
    except BringSyncError as e:
        return jsonify({'ok': False, 'message': str(e)}), 400
    except Exception as e:
        logger.exception("Bring list-items Fehler")
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/bring/list-items', methods=['PUT'])
def api_bring_update_list_item():
    """Updated ein einzelnes Bring-Item: Name, Spec, Stueckpreis.

    Body: {
        list_uuid, item_uuid,
        name?, quantity?|spec?, info?, old_name?,    # Bring-Update (alle optional)
        grocy_product_id?, unit_price?                # Grocy-Update (optional)
    }
    Felder werden nur dann geupdated wenn sie im Body vorhanden sind.
    Reine Preis-Updates (nur unit_price) loesen kein Bring-Update aus.
    """
    data = request.get_json() or {}
    list_uuid = (data.get('list_uuid') or '').strip()
    item_uuid = (data.get('item_uuid') or '').strip()
    if not list_uuid or not item_uuid:
        return jsonify({'ok': False, 'message': sprache.t('msg.need_item')}), 400

    has_bring_update = any(k in data for k in ('name', 'spec', 'quantity', 'info'))
    has_price_update = 'unit_price' in data

    response = {'ok': True, 'bring': None, 'grocy': None}

    # 1) Bring nur updaten wenn Felder gegeben
    if has_bring_update:
        name = (data.get('name') or '').strip()
        old_name = (data.get('old_name') or '').strip() or None
        if not name:
            return jsonify({'ok': False, 'message': sprache.t('msg.need_name')}), 400
        # Spec aus quantity+info bauen, wenn die einzeln gegeben sind
        if 'quantity' in data or 'info' in data:
            qty_raw = data.get('quantity')
            try:
                qty = float(qty_raw) if qty_raw not in (None, '', 'null') else None
            except (TypeError, ValueError):
                qty = None
            spec = _build_spec(qty, data.get('info', ''))
        else:
            spec = (data.get('spec') or '').strip()
        try:
            sync = BringSync()
            bring_result = sync.update_list_item(
                list_uuid, item_uuid, name, spec, old_name=old_name
            )
            response['bring'] = bring_result
        except BringSyncError as e:
            return jsonify({'ok': False, 'message': str(e)}), 400
        except Exception as e:
            logger.exception("Bring-Item-Update Fehler")
            return jsonify({'ok': False, 'message': str(e)}), 500

    # 2) Grocy-Userfield aktualisieren (nur wenn Produkt zugeordnet UND Preis gesetzt)
    if has_price_update:
        grocy_pid = data.get('grocy_product_id')
        unit_price_raw = data.get('unit_price')
        if not grocy_pid:
            # Klares Feedback an den User: ohne Grocy-Match koennen wir den
            # Preis nirgends speichern. Der Bring-Update-Teil oben kann
            # erfolgreich gewesen sein, das melden wir trotzdem zurueck.
            response['ok'] = False
            response['message'] = (
                'Kein Grocy-Produkt verknuepft - der Stueckpreis kann '
                'erst gespeichert werden, wenn es ein passendes Produkt '
                'in Grocy gibt (gleicher oder aehnlicher Name).'
            )
            response['grocy'] = {'skipped': True, 'reason': 'no_grocy_match'}
            return jsonify(response), 400
        else:
            try:
                client = GrocyClient()
                try:
                    client.ensure_userfield(
                        'products', BRING_UNIT_PRICE_FIELD,
                        'Stueckpreis (Grocylink)',
                        ftype='number-decimal',
                        show_as_column_in_tables=1,
                    )
                except Exception as e:
                    logger.warning(f"Userfield-Definition konnte nicht angelegt werden: {e}")
                if unit_price_raw in (None, '', 'null'):
                    client.set_product_userfields(grocy_pid, {BRING_UNIT_PRICE_FIELD: ''})
                    response['grocy'] = {'unit_price': None}
                else:
                    client.set_product_userfields(grocy_pid, {
                        BRING_UNIT_PRICE_FIELD: str(unit_price_raw),
                    })
                    response['grocy'] = {'unit_price': unit_price_raw}
            except Exception as e:
                logger.exception("Grocy-Userfield-Update Fehler")
                response['ok'] = False
                response['message'] = str(e)
                return jsonify(response), 500

    return jsonify(response)


@app.route('/api/bring/items/manual', methods=['POST'])
def api_bring_add_item_manual():
    """Legt ein einzelnes Bring-Item manuell an (ohne Grocy-Bindung).

    Body: {name: str, spec?: str, list_uuid?: str}
    Wenn list_uuid leer/fehlend, wird die global konfigurierte Liste benutzt.
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    spec = (data.get('spec') or '').strip()
    list_uuid = (data.get('list_uuid') or '').strip() or None
    if not name:
        return jsonify({'ok': False, 'message': sprache.t('msg.need_name')}), 400
    try:
        sync = BringSync()
        result = sync.add_item_manual(name, spec, list_uuid)
        schluessel = ('log.bring_manual_spec' if result['spec']
                      else 'log.bring_manual')
        werte = {'name': result['name'], 'spec': result['spec'] or ''}
        msg = sprache.t(schluessel, **werte)
        add_log_entry(result['name'], 'bring_manual', 'Bring!', msg,
                      success=True, key=schluessel, args=werte)
        return jsonify({'ok': True, 'message': msg, 'item': result})
    except BringSyncError as e:
        add_log_entry(name, 'bring_manual', 'Bring!', str(e), success=False)
        return jsonify({'ok': False, 'message': str(e)}), 400
    except Exception as e:
        logger.exception("Bring manuell-Add Fehler")
        add_log_entry(name, 'bring_manual', 'Bring!', str(e), success=False)
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/bring/overrides', methods=['POST'])
def api_save_bring_override():
    data = request.get_json() or {}
    pid = data.get('product_id')
    if not pid:
        return jsonify({'ok': False, 'message': sprache.t('msg.need_product')}), 400
    if data.get('delete'):
        delete_bring_override(pid)
    else:
        save_bring_override(
            grocy_product_id=pid,
            hide_from_bring=bool(data.get('hide_from_bring')),
            custom_name=data.get('custom_name') or None,
            custom_spec=data.get('custom_spec') or None,
        )
    return jsonify({'ok': True})


def schedule_bring_sync():
    settings = get_all_settings()
    if bg_scheduler.get_job('bring_sync'):
        bg_scheduler.remove_job('bring_sync', jobstore='default')
    if settings.get('bring_sync_enabled', '0') == '1':
        minutes = int(settings.get('bring_sync_interval_minutes', 30))
        if minutes > 0:
            bg_scheduler.add_job(run_bring_sync, 'interval', minutes=minutes,
                                 id='bring_sync', replace_existing=True)
            logger.info(f"Bring-Sync geplant: alle {minutes} Minuten")


# ── Kassenbon-Endpunkte ──────────────────────────────────────────────

@app.route('/api/receipts', methods=['GET'])
def api_get_receipts():
    return jsonify(get_receipts())


@app.route('/api/receipts/<int:receipt_id>', methods=['GET'])
def api_get_receipt(receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return jsonify({'error': sprache.t('msg.receipt_missing')}), 404
    return jsonify(receipt)


@app.route('/api/receipts/upload', methods=['POST'])
def api_upload_receipt():
    if 'file' not in request.files:
        return jsonify({'error': sprache.t('msg.no_file')}), 400
    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': sprache.t('msg.pdf_only')}), 400

    upload_dir = os.path.join(os.path.dirname(__file__), 'data', 'receipts')
    os.makedirs(upload_dir, exist_ok=True)
    filename = file.filename
    filepath = os.path.join(upload_dir, filename)

    # Duplikatpruefung
    counter = 1
    while os.path.exists(filepath) or receipt_filepath_exists(filepath):
        name, ext = os.path.splitext(filename)
        filepath = os.path.join(upload_dir, f"{name}_{counter}{ext}")
        counter += 1

    file.save(filepath)

    try:
        settings = get_all_settings()
        threshold = int(settings.get('receipt_match_threshold', 70))
        client = GrocyClient()
        grocy_products = client.get_all_products()
        mappings = get_product_mappings_dict()
        result = process_receipt(filepath, grocy_products, mappings, threshold=threshold)

        receipt_id = save_receipt(
            filename=os.path.basename(filepath),
            filepath=filepath,
            status=result['status'],
            extraction_method=result['extraction_method'],
            store_name=result['parsed']['store_name'] if result['parsed'] else None,
            receipt_date=result['parsed']['receipt_date'] if result['parsed'] else None,
            total_amount=result['parsed']['total_amount'] if result['parsed'] else None,
            raw_text=result['raw_text'],
            error_message=result['error_message'],
        )

        if result['items']:
            save_receipt_items(receipt_id, result['items'])

        return jsonify({'ok': True, 'receipt_id': receipt_id, 'items_count': len(result['items'])})
    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten des Kassenbons: {e}")
        receipt_id = save_receipt(
            filename=os.path.basename(filepath), filepath=filepath,
            status='error', error_message=str(e),
        )
        return jsonify({'ok': False, 'error': str(e), 'receipt_id': receipt_id}), 500


@app.route('/api/receipts/<int:receipt_id>', methods=['DELETE'])
def api_delete_receipt(receipt_id):
    db_delete_receipt(receipt_id)
    return jsonify({'ok': True})


@app.route('/api/receipts/<int:receipt_id>/items/<int:item_id>', methods=['PUT'])
def api_update_receipt_item(receipt_id, item_id):
    data = request.get_json()
    product_id = data.get('matched_product_id')
    product_name = data.get('matched_product_name', '')
    update_receipt_item(item_id, product_id, product_name)
    return jsonify({'ok': True})


@app.route('/api/receipts/<int:receipt_id>/confirm', methods=['POST'])
def api_confirm_receipt(receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return jsonify({'error': sprache.t('msg.receipt_missing')}), 404

    body = request.get_json(silent=True) or {}
    new_products = body.get('new_products', {})

    errors = []  # detaillierte Fehler-Objekte fuer's Log + Frontend
    added = 0
    created = 0
    skipped = 0
    client = GrocyClient()

    receipt_label = (
        f"Bon #{receipt_id} "
        f"({receipt.get('store_name') or '?'} {receipt.get('receipt_date') or ''})"
    ).strip()

    def _record_error(item_name, exc):
        """Fehler ins notification_log schreiben + im logger mit Traceback."""
        import traceback as _tb
        tb = _tb.format_exc()
        msg = f"{item_name}: {exc}"
        logger.error(f"Receipt-Confirm-Fehler ({receipt_label}) - {msg}\n{tb}")
        try:
            werte = {'receipt': receipt_label, 'error': str(exc)}
            add_log_entry(
                item_name, 'receipt_error', 'Kassenbon',
                sprache.t('log.receipt_error', **werte), success=False,
                key='log.receipt_error', args=werte,
            )
        except Exception:
            pass
        errors.append({'item': item_name, 'message': str(exc)})

    for item in receipt.get('items', []):
        item_id_str = str(item['id'])

        # Neues Produkt erstellen?
        if item_id_str in new_products:
            np = new_products[item_id_str]
            try:
                result = client.create_product(
                    np['name'],
                    location_id=np.get('location_id'),
                    product_group_id=np.get('product_group_id'),
                    qu_id_purchase=np.get('qu_id'),
                )
                new_pid = result.get('created_object_id')
                if not new_pid:
                    _record_error(np['name'], 'Keine product_id in Grocy-Antwort')
                    continue
                # Barcode zum Produkt hinzufuegen (falls ausgewaehlt)
                barcode = (np.get('barcode') or '').strip()
                if barcode:
                    try:
                        client.add_product_barcode(new_pid, barcode)
                    except Exception as bc_err:
                        logger.warning(f"Barcode {barcode} fuer {np['name']}: {bc_err}")
                # Naehrwerte als Userfields speichern (falls vorhanden)
                nutrition = np.get('nutrition')
                if nutrition and isinstance(nutrition, dict):
                    userfields = {}
                    field_map = {
                        'energy_kcal': 'nutrition_energy_kcal',
                        'fat': 'nutrition_fat',
                        'saturated_fat': 'nutrition_saturated_fat',
                        'carbs': 'nutrition_carbohydrates',
                        'sugars': 'nutrition_sugars',
                        'protein': 'nutrition_protein',
                        'salt': 'nutrition_salt',
                        'fiber': 'nutrition_fiber',
                    }
                    for src_key, uf_key in field_map.items():
                        val = nutrition.get(src_key)
                        if val is not None:
                            userfields[uf_key] = str(val)
                    if userfields:
                        try:
                            client.set_product_userfields(new_pid, userfields)
                        except Exception as uf_err:
                            logger.warning(f"Userfields fuer {np['name']}: {uf_err}")
                client.add_stock(
                    new_pid,
                    item.get('quantity', 1),
                    price=item.get('unit_price'),
                )
                save_product_mapping(
                    item['raw_name'].upper().strip(),
                    new_pid,
                    np['name'],
                )
                created += 1
                added += 1
            except Exception as e:
                _record_error(np['name'], e)
            continue

        if not item.get('matched_product_id'):
            skipped += 1
            continue
        try:
            client.add_stock(
                item['matched_product_id'],
                item.get('quantity', 1),
                price=item.get('unit_price'),
            )
            added += 1
            save_product_mapping(
                item['raw_name'].upper().strip(),
                item['matched_product_id'],
                item['matched_product_name'] or '',
            )
        except Exception as e:
            _record_error(item.get('raw_name') or f"Position #{item['id']}", e)

    # Status nur dann auf 'confirmed' setzen, wenn ALLES sauber durchlief.
    # Bei (Teil-)Fehlern bleibt der Bon im Review-Status, damit der User
    # ihn nochmal anfassen kann. Detail-Status fuers UI:
    #   - confirmed: alles gebucht, keine Errors
    #   - partial:   einiges gebucht, einiges fehlgeschlagen
    #   - error:     keine Buchung, alle Items fehlgeschlagen
    if errors:
        new_status = 'partial' if added > 0 else 'error'
        schluessel = ('log.receipt_summary_skipped' if skipped
                      else 'log.receipt_summary')
        werte = {'receipt': receipt_label, 'added': added,
                 'failed': len(errors), 'skipped': skipped}
        summary = sprache.t(schluessel, **werte)
        update_receipt_status(receipt_id, new_status, error_message=summary)
        try:
            add_log_entry(
                None, 'receipt_summary', 'Kassenbon', summary, success=False,
                key=schluessel, args=werte,
            )
        except Exception:
            pass
    else:
        update_receipt_status(receipt_id, 'confirmed')

    result = {
        'ok': not errors or added > 0,  # ok=False nur wenn nichts gebucht wurde
        'added': added,
        'created': created,
        'skipped': skipped,
        'status': 'confirmed' if not errors else ('partial' if added > 0 else 'error'),
    }
    if errors:
        result['errors'] = errors
    return jsonify(result)


@app.route('/api/receipts/<int:receipt_id>/reject', methods=['POST'])
def api_reject_receipt(receipt_id):
    update_receipt_status(receipt_id, 'rejected')
    return jsonify({'ok': True})


@app.route('/api/receipts/mappings', methods=['GET'])
def api_get_mappings():
    return jsonify(get_product_mappings())


@app.route('/api/receipts/mappings/<int:mapping_id>', methods=['DELETE'])
def api_delete_mapping(mapping_id):
    delete_product_mapping(mapping_id)
    return jsonify({'ok': True})


@app.route('/api/receipts/reprocess/<int:receipt_id>', methods=['POST'])
def api_reprocess_receipt(receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return jsonify({'error': sprache.t('msg.receipt_missing')}), 404

    try:
        settings = get_all_settings()
        threshold = int(settings.get('receipt_match_threshold', 70))
        client = GrocyClient()
        grocy_products = client.get_all_products()
        mappings = get_product_mappings_dict()
        result = process_receipt(receipt['filepath'], grocy_products, mappings, threshold=threshold)

        update_receipt_status(receipt_id, result['status'], result.get('error_message'))
        if result['items']:
            save_receipt_items(receipt_id, result['items'])

        return jsonify({'ok': True, 'items_count': len(result['items'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_receipt_watch():
    """Wird vom Scheduler aufgerufen um den Kassenbon-Ordner zu scannen."""
    try:
        settings = get_all_settings()
        folder = settings.get('receipt_watch_folder', '/app/receipts')
        threshold = int(settings.get('receipt_match_threshold', 70))
        client = GrocyClient()
        grocy_products = client.get_all_products()
        mappings = get_product_mappings_dict()
        results = scan_receipt_folder(folder, grocy_products, mappings, threshold=threshold)
        if results:
            logger.info(f"Kassenbon-Scan: {len(results)} neue Bons verarbeitet")
    except Exception as e:
        logger.error(f"Kassenbon-Scan Fehler: {e}")


def schedule_receipt_watch():
    settings = get_all_settings()
    if bg_scheduler.get_job('receipt_watch'):
        bg_scheduler.remove_job('receipt_watch', jobstore='default')
    if settings.get('receipt_watch_enabled', '0') == '1':
        minutes = int(settings.get('receipt_watch_interval_minutes', 5))
        if minutes > 0:
            bg_scheduler.add_job(run_receipt_watch, 'interval', minutes=minutes,
                                 id='receipt_watch', replace_existing=True)
            logger.info(f"Kassenbon-Watch geplant: alle {minutes} Minuten")


schedule_check()
schedule_caldav_sync()
schedule_bring_sync()
schedule_receipt_watch()


@app.route('/api/keys', methods=['GET'])
def api_get_keys():
    """Alle App-Zugaenge -- ohne Hash, versteht sich."""
    from database import get_api_keys
    return jsonify(get_api_keys())


@app.route('/api/keys', methods=['POST'])
def api_create_key():
    """Legt einen Zugang an und liefert den Schluessel **einmalig** zurueck.

    Danach steht in der Datenbank nur sein SHA-256. Wer ihn verliert, legt
    einen neuen an und widerruft den alten -- das ist sicherer, als ihn
    nachlesbar zu halten.
    """
    from database import create_api_key
    daten = request.get_json() or {}
    name = (daten.get('name') or 'Geraet').strip()[:60]
    schluessel = create_api_key(name)
    logger.info('App-Zugang angelegt: %s', name)
    return jsonify({'name': name, 'key': schluessel}), 201


@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
def api_revoke_key(key_id):
    """Setzt einen Zugang still -- etwa bei einem verlorenen Handy."""
    from database import revoke_api_key
    name = revoke_api_key(key_id)
    logger.info('App-Zugang widerrufen: %s', name)
    return jsonify({'revoked': key_id, 'name': name})


# ---------------------------------------------------------------------------
# JSON-Schnittstelle fuer die App (siehe api_v1.py)
#
# Erst hier angemeldet, nachdem alle View-Funktionen oben stehen: Der
# Blueprint reicht Anfragen an genau diese Funktionen weiter, damit App und
# Weboberflaeche durch denselben Code laufen.
# ---------------------------------------------------------------------------
from api_v1 import api_v1 as _api_v1_blueprint

app.config['APP_VERSION'] = APP_VERSION
app.register_blueprint(_api_v1_blueprint)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
