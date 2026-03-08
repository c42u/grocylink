# Barcode-Suche: Multi-API Lookup mit Vorschlag-Dropdown

## Inhaltsverzeichnis

1. [Backend: Barcode-Such-Endpoint](#change_1)
2. [Backend: Barcode in Grocy speichern](#change_2)
3. [Frontend: Barcode-Dropdown](#change_3)

---

### 1. >>Backend: Barcode-Such-Endpoint<< <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-07

#### Beschreibung der Aenderung

Neuer Endpoint `POST /api/barcode/search` sucht Barcodes fuer einen
Produktnamen ueber OpenFoodFacts. Gibt eine Liste von Vorschlaegen zurueck,
jeweils mit EAN, Produktname, Bild-URL und Quelle. Bis zu 8 Produkte
werden abgefragt, Duplikate gefiltert und nur Ergebnisse mit Produktname
zurueckgegeben.

Hinweis: opengtindb.org unterstuetzt nur EAN→Produkt (nicht umgekehrt) und
benoetigt einen API-Key, daher wird aktuell nur OpenFoodFacts verwendet.
Weitere Quellen koennen spaeter ergaenzt werden.

Geaenderte Dateien:
- `Code/app.py`: Neuer Endpoint `/api/barcode/search`

---

### 2. >>Backend: Barcode in Grocy speichern<< <a name="change_2"></a>
#### Datum der Erstellung - 2026-03-07

#### Beschreibung der Aenderung

GrocyClient um zwei Methoden erweitert:
- `add_product_barcode(product_id, barcode)`: Speichert EAN via `/objects/product_barcodes`
- `get_product_barcodes(product_id)`: Liefert alle Barcodes eines Produkts

Im Confirm-Flow (`api_confirm_receipt`) wird nach dem Erstellen eines neuen
Produkts automatisch der ausgewaehlte Barcode gespeichert, sofern einer
ausgewaehlt wurde.

Geaenderte Dateien:
- `Code/grocy_client.py`: Neue Methoden `add_product_barcode()`, `get_product_barcodes()`
- `Code/app.py`: Barcode-Speicherung in `api_confirm_receipt()`

---

### 3. >>Frontend: Barcode-Dropdown<< <a name="change_3"></a>
#### Datum der Erstellung - 2026-03-07

#### Beschreibung der Aenderung

In den "Neues Produkt"-Feldern im Review-Modal gibt es jetzt ein
Barcode-Dropdown (`.np-barcode-select`). Beim automatischen Suggest
(`autoSuggestAll`) oder manuellen Klick auf "Vorschlagen" wird parallel
eine Barcode-Suche ausgefuehrt. Das Dropdown zeigt alle gefundenen
EAN-Codes mit Produktname und Quelle. Der erste Treffer wird automatisch
vorausgewaehlt. Beim Bestaetigen wird der ausgewaehlte Barcode an das
Backend uebergeben.

Neue Funktion `searchBarcodes(itemId, productName)` fuellt das Dropdown
asynchron und wird von `suggestCategory()` aufgerufen.

Geaenderte Dateien:
- `Code/static/app.js`: Neue Funktion `searchBarcodes()`, Barcode-Dropdown in Review-HTML,
  Barcode im `confirmCurrentReceipt()` mitgeschickt
- `Code/static/style.css`: `.np-barcode-select` Styling
- `Code/static/i18n.js`: Neue i18n-Keys fuer Barcode-UI (DE + EN)

---
