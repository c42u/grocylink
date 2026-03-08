# Netto-Kassenbon: Mengenzeile ueber dem Produktnamen

## Inhaltsverzeichnis

1. [Mengenzeile-Erkennung](#change_1)

---

### 1. >>Mengenzeile-Erkennung<< <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-07

#### Beschreibung der Aenderung

Bei Netto-Kassenbons steht die Anzahl eines Produkts in der Zeile UEBER
dem Produktnamen (z.B. "2" auf einer Zeile, gefolgt von "PRODUKT NAME  3,98 A").
Der Parser erkennt jetzt alleinstehende Zahlen als Mengenangabe fuer das
naechste Produkt und berechnet den Stueckpreis korrekt (Gesamtpreis / Menge).

Neues Pattern `PATTERN_PRELINE_QTY` erkennt Zeilen die nur eine Zahl enthalten.
Die Variable `pending_qty` merkt sich die Menge und wendet sie auf das
naechste erkannte Produkt an, sofern dessen Menge noch 1 ist.

Geaenderte Dateien:
- `Code/receipt_scanner.py`: Neues Pattern + Logik in `parse_receipt_text()`

---
