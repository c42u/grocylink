import json
import logging
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

from database import (
    init_db, get_all_settings, save_settings,
    get_channels, save_channel, delete_channel,
    get_product_overrides, save_product_override, delete_product_override,
    get_log, clear_log
)
from grocy_client import GrocyClient
from notifiers import get_notifier
from scheduler import run_check

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

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
    return jsonify({'ok': True})


@app.route('/api/test-connection', methods=['POST'])
def api_test_connection():
    data = request.get_json()
    client = GrocyClient(data.get('grocy_url'), data.get('grocy_api_key'))
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
    channels = get_channels()
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
    channels = get_channels()
    ch = next((c for c in channels if c['id'] == channel_id), None)
    if not ch:
        return jsonify({'ok': False, 'message': 'Kanal nicht gefunden'}), 404
    try:
        config = json.loads(ch['config_json']) if isinstance(ch['config_json'], str) else ch['config_json']
        notifier = get_notifier(ch['type'], config)
        notifier.test()
        return jsonify({'ok': True, 'message': 'Testnachricht gesendet!'})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)})


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


if __name__ == '__main__':
    init_db()
    schedule_check()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
