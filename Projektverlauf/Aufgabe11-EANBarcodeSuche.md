# Aufgabe 11 – EAN/Barcode-Suche in Kassenbon-Pruefung

## Status: Erledigt
## Datum: 2026-03-10

### Beschreibung

Pro Bon-Position im Kassenbon-Review ein Barcode-Eingabefeld mit Suchbutton implementieren. Bei Eingabe eines EAN wird zuerst in Grocy nach passenden Produkten gesucht. Falls kein Treffer, wird OpenFoodFacts als Fallback abgefragt.

### Umsetzung

- **Backend**: `/api/barcode/lookup` Endpoint in `app.py` (Grocy-first, OFF-Fallback)
- **Client**: `search_product_by_barcode()` Methode in `grocy_client.py`
- **Frontend**: `lookupBarcode()` Funktion in `app.js`, Barcode-Input pro Tabellenzeile
- **i18n**: 7 neue Uebersetzungskeys in `i18n.js` (DE + EN)
- **CSS**: Styles fuer `.barcode-lookup-row`, Farbindikatoren (gruen=gefunden, rot=nicht gefunden)

### Workflow

1. EAN eingeben und suchen
2. Grocy-Treffer: Produkt wird automatisch im Dropdown ausgewaehlt
3. Kein Grocy-Treffer: OpenFoodFacts wird als Fallback abgefragt
4. OFF-Treffer: Name und Barcode werden in die Felder fuer neues Produkt uebernommen
5. Kein Treffer: Rote Markierung, manuelle Zuordnung noetig

### Ergebnis

- Barcode-Suche funktioniert in der Kassenbon-Pruefung
- Grocy- und OFF-Integration vollstaendig
