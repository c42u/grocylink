import json
import logging
import os
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from database import (
    init_db, get_all_settings, save_settings,
    get_channels, get_channels_decrypted, save_channel, delete_channel,
    get_product_overrides, save_product_override, delete_product_override,
    get_log, clear_log, get_sync_map, clear_sync_map, add_log_entry,
    save_receipt, get_receipts, get_receipt, update_receipt_status,
    delete_receipt as db_delete_receipt, save_receipt_items, update_receipt_item,
    get_receipt_item, get_product_mappings_dict, get_product_mappings,
    save_product_mapping, delete_product_mapping, receipt_filepath_exists,
)
from grocy_client import GrocyClient
from notifiers import get_notifier
from scheduler import run_check
from caldav_sync import CalDAVSync, run_caldav_sync
from receipt_scanner import process_receipt, scan_receipt_folder

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

APP_VERSION = '1.1.0'

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
    return render_template('index.html', version=APP_VERSION)


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(get_all_settings())


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.get_json()
    save_settings(data)
    schedule_check()
    schedule_caldav_sync()
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
        return jsonify({'error': 'Grocy nicht konfiguriert'}), 400
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
        return jsonify({'ok': False, 'message': 'Kanal nicht gefunden'}), 404
    try:
        config = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
        notifier = get_notifier(ch['type'], config)
        notifier.test()
        add_log_entry(None, 'test', ch['name'], 'Testnachricht erfolgreich gesendet', success=True)
        return jsonify({'ok': True, 'message': 'Testnachricht gesendet!'})
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
        return jsonify({'error': 'product_id and amount required'}), 400
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
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'category': None, 'product_group_id': None, 'raw_categories': []})
    try:
        import requests as req
        from rapidfuzz import fuzz
        resp = req.get(
            'https://de.openfoodfacts.org/cgi/search.pl',
            params={'search_terms': name, 'search_simple': 1, 'action': 'process', 'json': 1, 'page_size': 3},
            headers={'User-Agent': 'Grocylink/1.2.0 (grocylink@c42u.de)'},
            timeout=10,
        )
        resp.raise_for_status()
        products = resp.json().get('products', [])
        raw_categories = []
        for p in products:
            cats = p.get('categories_tags_de') or p.get('categories_tags') or []
            if isinstance(cats, str):
                cats = [c.strip() for c in cats.split(',')]
            raw_categories.extend(cats)
        raw_categories = list(dict.fromkeys(raw_categories))
        if not raw_categories:
            return jsonify({'category': None, 'product_group_id': None, 'raw_categories': []})
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
            return jsonify({'category': None, 'product_group_id': None, 'raw_categories': raw_categories})
        return jsonify({'category': best_match, 'product_group_id': best_group_id, 'raw_categories': raw_categories})
    except Exception as e:
        logger.error(f"OpenFoodFacts Fehler: {e}")
        return jsonify({'category': None, 'product_group_id': None, 'error': str(e)})


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
        return jsonify({'ok': True, 'message': 'Check durchgeführt!'})
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
        return jsonify({'ok': True, 'message': 'Synchronisation abgeschlossen!', 'stats': stats})
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


# ── Kassenbon-Endpunkte ──────────────────────────────────────────────

@app.route('/api/receipts', methods=['GET'])
def api_get_receipts():
    return jsonify(get_receipts())


@app.route('/api/receipts/<int:receipt_id>', methods=['GET'])
def api_get_receipt(receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return jsonify({'error': 'Kassenbon nicht gefunden'}), 404
    return jsonify(receipt)


@app.route('/api/receipts/upload', methods=['POST'])
def api_upload_receipt():
    if 'file' not in request.files:
        return jsonify({'error': 'Keine Datei hochgeladen'}), 400
    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Nur PDF-Dateien erlaubt'}), 400

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
        return jsonify({'error': 'Kassenbon nicht gefunden'}), 404

    body = request.get_json(silent=True) or {}
    new_products = body.get('new_products', {})

    errors = []
    added = 0
    created = 0
    client = GrocyClient()

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
                    errors.append(f"{np['name']}: Keine product_id in Antwort")
                    continue
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
                errors.append(f"{np['name']}: {e}")
            continue

        if not item.get('matched_product_id'):
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
            errors.append(f"{item['raw_name']}: {e}")

    update_receipt_status(receipt_id, 'confirmed')

    result = {'ok': True, 'added': added, 'created': created}
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
        return jsonify({'error': 'Kassenbon nicht gefunden'}), 404

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
schedule_receipt_watch()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
