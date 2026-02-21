import requests
from database import get_setting


class GrocyClient:
    def __init__(self, url=None, api_key=None):
        self.url = (url or get_setting('grocy_url') or '').rstrip('/')
        self.api_key = api_key or get_setting('grocy_api_key') or ''
        self.verify_ssl = (get_setting('grocy_verify_ssl') or '1') != '0'

    def _headers(self):
        return {
            'GROCY-API-KEY': self.api_key,
            'Accept': 'application/json',
        }

    def _get(self, endpoint, params=None):
        if not self.url or not self.api_key:
            raise ConnectionError("Grocy URL oder API-Key nicht konfiguriert")
        resp = requests.get(
            f"{self.url}/api{endpoint}",
            headers=self._headers(),
            params=params,
            timeout=15,
            verify=self.verify_ssl
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint, data=None):
        if not self.url or not self.api_key:
            raise ConnectionError("Grocy URL oder API-Key nicht konfiguriert")
        resp = requests.post(
            f"{self.url}/api{endpoint}",
            headers={**self._headers(), 'Content-Type': 'application/json'},
            json=data or {},
            timeout=15,
            verify=self.verify_ssl
        )
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}

    def _put(self, endpoint, data=None):
        if not self.url or not self.api_key:
            raise ConnectionError("Grocy URL oder API-Key nicht konfiguriert")
        resp = requests.put(
            f"{self.url}/api{endpoint}",
            headers={**self._headers(), 'Content-Type': 'application/json'},
            json=data or {},
            timeout=15,
            verify=self.verify_ssl
        )
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}

    def test_connection(self):
        try:
            data = self._get('/system/info')
            return True, f"Verbunden mit Grocy {data.get('grocy_version', {}).get('Version', '?')}"
        except Exception as e:
            return False, str(e)

    def get_volatile_stock(self, due_soon_days=5):
        return self._get('/stock/volatile', params={'due_soon_days': due_soon_days})

    def get_all_stock(self):
        return self._get('/stock')

    def get_product_details(self, product_id):
        return self._get(f'/stock/products/{product_id}')

    def get_tasks(self):
        return self._get('/tasks')

    def get_all_tasks_including_done(self):
        return self._get('/objects/tasks')

    def complete_task(self, task_id):
        return self._post(f'/tasks/{task_id}/complete', {'done_time': ''})

    def undo_task(self, task_id):
        return self._post(f'/tasks/{task_id}/undo')

    def update_task(self, task_id, data):
        return self._put(f'/objects/tasks/{task_id}', data)

    def create_task(self, data):
        return self._post('/objects/tasks', data)

    def get_chores(self):
        return self._get('/chores')

    def get_chore_details(self, chore_id):
        return self._get(f'/chores/{chore_id}')

    def execute_chore(self, chore_id):
        return self._post(f'/chores/{chore_id}/execute', {
            'tracked_time': '',
            'done_by': 0
        })
