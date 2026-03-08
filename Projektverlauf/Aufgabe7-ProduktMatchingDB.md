# Aufgabe 7 - Produkt-Matching-Datenbank – grocylink

## Inhaltsverzeichnis

1. [Beschreibung](#change_1)

---

### 1. Produkt-Matching-Datenbank <a name="change_1"></a>
#### Datum der Erstellung - 2026-03-08

#### Beschreibung der Änderung

Erweiterung des Kassenbon-Produkt-Matchings: Verschiedene Bon-Namen, die zum
selben Grocy-Produkt gehoeren, werden als Erkennungssignaturen gespeichert.

**Aenderungen:**
- `database.py`: Neue Funktion `get_mappings_by_product()` – liefert alle gelernten
  Bon-Namen gruppiert nach Grocy-Produkt-ID
- `receipt_scanner.py`: Matching-Algorithmus um Schritt 2 erweitert (Fuzzy-Match
  gegen gelernte Bon-Namen als Signaturen). Neue `match_source`: `learned_fuzzy`
- Signatur-Matches werden bei gleicher oder besserer Konfidenz bevorzugt, da sie
  bereits vom Nutzer bestaetigt wurden

#### Status: Erledigt

---
