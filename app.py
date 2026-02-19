import json
import logging
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from database import (
    init_db, get_all_settings, save_settings,
    get_channels, get_channels_decrypted, save_channel, delete_channel,
    get_product_overrides, save_product_override, delete_product_override,
    get_log, clear_log, get_sync_map, clear_sync_map, add_log_entry
)
from grocy_client import GrocyClient
from notifiers import get_notifier
from scheduler import run_check
from caldav_sync import CalDAVSync, run_caldav_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

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
    return render_template('index.html')


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(get_all_settings())


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.get_json()
    save_settings(data)
    schedule_check()
    schedule_caldav_sync()
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
    settings = get_all_settings()
    overrides = {o['product_id']: o for o in get_product_overrides()}
    products = []
    if settings.get('grocy_url') and settings.get('grocy_api_key'):
        try:
            client = GrocyClient()
            stock = client.get_all_stock()
            for item in stock:
                pid = item.get('product_id') or item.get('product', {}).get('id')
                name = item.get('product', {}).get('name', f'Produkt #{pid}')
                override = overrides.get(pid)
                products.append({
                    'product_id': pid,
                    'name': name,
                    'amount': item.get('amount', 0),
                    'best_before_date': item.get('best_before_date', ''),
                    'custom_days': override['custom_days_before_expiry'] if override else None,
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
        save_product_override(data['product_id'], data['product_name'], data['days'])
    return jsonify({'ok': True})


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


schedule_check()
schedule_caldav_sync()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
