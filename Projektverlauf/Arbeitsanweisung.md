# Arbeitsanweisung – grocylink

## Erstelldatum - 2026-03-09

### Beschreibung

- Beim Klick auf "Vorschlagen" wird gesucht und es werden Ergebnisse gefunden, aber in der Spalte "Produktvorschläge" erscheint kein Dropdown-Menü zur Auswahl der gefundenen Produkte. Nur beim Barcode (EAN) funktioniert das Dropdown. Das Produktvorschlags-Dropdown muss in der Spalte "Produktvorschläge" korrekt angezeigt werden, mit Bild, Score und Nährwerten.

## Erstelldatum - 2026-03-10

### Beschreibung

- **EAN/Barcode-Suche in Kassenbon pruefen**: Pro Bon-Position ein Barcode-Eingabefeld mit Suchbutton. Bei Eingabe eines EAN wird zuerst in Grocy nach passenden Produkten gesucht. Falls kein Treffer, wird OpenFoodFacts als Fallback abgefragt. Grocy-Treffer werden automatisch im Produkt-Dropdown ausgewaehlt. OFF-Treffer belegen die Felder fuer neues Produkt vor (Name, Marke, Barcode).

### Umsetzung

- Backend: `/api/barcode/lookup` Endpoint in `app.py` (Grocy-first, OFF-Fallback)
- Client: `search_product_by_barcode()` in `grocy_client.py`
- Frontend: `lookupBarcode()` Funktion in `app.js`, Barcode-Input pro Tabellenzeile
- i18n: 7 neue Keys in `i18n.js` (DE + EN)
- CSS: Styles fuer `.barcode-lookup-row`, Farbindikatoren (gruen=gefunden, rot=nicht gefunden)

---
