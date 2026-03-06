# Vorauswahl mit Produktbildern und Barcodes

## Inhaltsverzeichnis

1. [Produktbild und Barcode Anzeige](#change_1)

---

### 1. >>Produktbild und Barcode Anzeige<< <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-06

#### Beschreibung der Aenderung

Wenn kein automatischer Abgleich mit bestehenden Grocy-Produkten moeglich ist, wird ueber OpenFoodFacts eine visuelle Vorauswahl angeboten:

1. Beim automatischen Suggest (oder manuellem Klick auf "Vorschlagen") wird das OpenFoodFacts-Ergebnis angezeigt
2. Das Produktbild (`image_front_small_url`) wird als 40x40px Vorschaubild dargestellt
3. Der OpenFoodFacts-Produktname wird angezeigt, damit der User pruefen kann ob der Treffer passt
4. Der Barcode (EAN) wird in Monospace-Schrift angezeigt

Diese Informationen helfen dem User zu verifizieren, ob der OpenFoodFacts-Vorschlag zum Kassenbon-Artikel passt.

Ein vollstaendiges Dropdown mit mehreren Produktvorschlaegen (inkl. Bilder) als Auswahl waere technisch moeglich, ist aber aktuell nicht implementiert, da OpenFoodFacts haeufig nur 1-2 relevante Treffer liefert.

Geaenderte Dateien:
- `Code/app.py`: Response um `image_url`, `barcode`, `off_product_name` erweitert
- `Code/static/app.js`: `suggestCategory()` zeigt Bild/Name/Barcode in `.np-preview-row`
- `Code/static/style.css`: Neue Klassen `.np-preview-img`, `.np-preview-row`, `.np-barcode`

---