# Aldi-Kassenbon: Duplikate zusammenfuehren

## Inhaltsverzeichnis

1. [Duplikat-Zusammenfuehrung](#change_1)

---

### 1. >>Duplikat-Zusammenfuehrung<< <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-07

#### Beschreibung der Aenderung

Bei Aldi-Kassenbons wird jedes Produkt einzeln aufgefuehrt, auch wenn es
mehrfach gekauft wurde. Die Funktion `merge_duplicates()` gruppiert Items
mit identischem `raw_name` (case-insensitive), addiert die Mengen und
summiert die Gesamtpreise. Der Stueckpreis bleibt erhalten.

Die Zusammenfuehrung erfolgt automatisch am Ende von `parse_receipt_text()`
fuer alle Kassenbons, nicht nur Aldi – das ist ein generisch sinnvolles
Verhalten.

Geaenderte Dateien:
- `Code/receipt_scanner.py`: Neue Funktion `merge_duplicates()`, Aufruf in `parse_receipt_text()`

---
