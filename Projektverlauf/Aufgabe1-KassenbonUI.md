# Kassenbon-Review UI Verbesserungen

## Inhaltsverzeichnis

1. [Dropdown-Breiten angleichen](#change_1)
2. [Labels fuer Dropdown-Menues](#change_2)
3. [Automatische Vorauswahl via OpenFoodFacts](#change_3)

---

### 1. >>Dropdown-Breiten angleichen<< <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-06

#### Beschreibung der Aenderung

CSS-Klasse `.receipt-match-select` um `width: 100%` ergaenzt, damit alle Dropdowns (Produktzuordnung, Kategorie, Lagerort, Mengeneinheit) die gleiche Breite haben. Die `.new-product-fields` Selects erben ebenfalls `width: 100%`.

Geaenderte Dateien:
- `Code/static/style.css`: `.receipt-match-select` und `.new-product-fields` Styles ueberarbeitet

---

### 2. >>Labels fuer Dropdown-Menues<< <a name="change_2"></a>
#### Datum der Erstellung - 2026-03-06

#### Beschreibung der Aenderung

Jedes Dropdown-Feld in den "Neues Produkt"-Feldern hat jetzt ein Label-Element (`<span class="np-label">`) mit Beschriftung: Produktname, Kategorie, Lagerort, Mengeneinheit. Labels sind in Grossbuchstaben, hellgrau und klein gehalten.

Geaenderte Dateien:
- `Code/static/app.js`: HTML-Generierung in `openReceiptReview()` — jedes Feld in `.np-field-group` mit `.np-label` gewrappt
- `Code/static/style.css`: Neue Klassen `.np-field-group`, `.np-label`

---

### 3. >>Automatische Vorauswahl via OpenFoodFacts<< <a name="change_3"></a>
#### Datum der Erstellung - 2026-03-06

#### Beschreibung der Aenderung

Beim Oeffnen des Review-Modals wird fuer alle ungematchten Items automatisch `autoSuggestAll()` aufgerufen. Diese Funktion iteriert ueber alle Items mit `__NEW__` und ruft `suggestCategory()` auf. OpenFoodFacts liefert Kategorie-Vorschlag, Produktbild, Barcode und Produktname. Die Kategorie wird automatisch im Dropdown vorausgewaehlt.

Geaenderte Dateien:
- `Code/static/app.js`: Neue Funktion `autoSuggestAll()`, Aufruf in `openReceiptReview()`
- `Code/app.py`: OpenFoodFacts-Endpoint erweitert um `image_url`, `barcode`, `off_product_name`

---