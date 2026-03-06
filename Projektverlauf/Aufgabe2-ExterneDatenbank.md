# Externe Datenbank fuer automatisierte Vorauswahl

## Inhaltsverzeichnis

1. [OpenFoodFacts Integration](#change_1)

---

### 1. >>OpenFoodFacts Integration<< <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-06

#### Beschreibung der Aenderung

Ja, es wird bereits auf die externe Datenbank OpenFoodFacts (https://de.openfoodfacts.org) zugegriffen. Die Integration funktioniert wie folgt:

1. Backend-Endpoint `POST /api/openfoodfacts/suggest` sendet den Produktnamen an die OpenFoodFacts Suchschnittstelle
2. Aus den Treffern werden Kategorien extrahiert (`categories_tags_de`)
3. Per Fuzzy-Match (rapidfuzz) werden diese gegen die Grocy-Produktgruppen abgeglichen
4. Der beste Treffer wird automatisch als Kategorie vorausgewaehlt
5. Zusaetzlich werden Produktbild, Barcode (EAN) und Produktname zurueckgegeben

Die Vorauswahl wird automatisch beim Oeffnen des Review-Modals fuer alle ungematchten Items ausgefuehrt.

User-Agent: `Grocylink/1.2.0 (grocylink@c42u.de)` (Pflicht bei OpenFoodFacts API)

Geaenderte Dateien:
- `Code/app.py`: OpenFoodFacts Endpoint mit Bild/Barcode/Name
- `Code/static/app.js`: `autoSuggestAll()` beim Oeffnen des Modals

---