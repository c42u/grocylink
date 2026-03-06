import requests
from database import get_setting


class GrocyClient:
    def __init__(self, url=None, api_key=None):
        self.url = (url or get_setting('grocy_url') or '').rstrip('/')
        self.api_key = api_key or get_setting('grocy_api_key') or ''

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
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()

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
