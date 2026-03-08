# Aufgabe 8 - Produktauswahl-Dropdown mit Naehrwerten – grocylink

## Inhaltsverzeichnis

1. [Beschreibung](#change_1)

---

### 1. Produktauswahl bei Kassenbon-Pruefung <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-08

#### Beschreibung der Änderung

Erweiterung der "Kassenbon pruefen"-Funktion: Statt nur dem besten Treffer
werden jetzt mehrere Produktvorschlaege mit Bild, Score und Naehrwerten angezeigt.

**Aenderungen:**
- `app.py`: OpenFoodFacts-API liefert jetzt `suggestions[]` mit mehreren Produkten,
  jeweils mit Bild, Barcode, Name-Score, Marke, Menge und Naehrwert-Daten
- `app.py`: Neue Endpunkte `/api/grocy/userfields` (GET) und
  `/api/grocy/products/<id>/userfields` (PUT) fuer Naehrwert-Userfields
- `app.py`: Confirm-Endpunkt speichert Naehrwerte als Grocy-Userfields
- `grocy_client.py`: Neue Methoden `get_userfields()` und `set_product_userfields()`
- `app.js`: Neues Vorschlags-Dropdown mit `renderSuggestionDetail()`,
  `onSuggestionSelect()` – zeigt Bild, Produktname, Marke, Score und Naehrwerttabelle
- `app.js`: Confirm uebertraegt Naehrwerte des gewaehlten Vorschlags
- `i18n.js`: Neue Keys fuer Naehrwert-Labels (DE+EN)
- `style.css`: Styling fuer `.np-suggestions`, `.np-suggestion-detail`, `.np-nutrition-table`

**Grocy-Userfields fuer Naehrwerte:**
Die folgenden Felder muessen in Grocy unter Einstellungen → Benutzerfelder → Entity "Produkte"
angelegt werden:
- `nutrition_energy_kcal` (Energie in kcal)
- `nutrition_fat` (Fett in g)
- `nutrition_saturated_fat` (gesaettigte Fettsaeuren in g)
- `nutrition_carbohydrates` (Kohlenhydrate in g)
- `nutrition_sugars` (Zucker in g)
- `nutrition_protein` (Eiweiss in g)
- `nutrition_salt` (Salz in g)
- `nutrition_fiber` (Ballaststoffe in g)

#### Status: Erledigt

---
