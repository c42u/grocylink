# Changelog

All notable changes to Grocylink will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-03-05

### Added

- **Kassenbon-Scanner**: Neue Seite "Kassenbons" in der Navigation zum Verarbeiten von
  PDF-Kassenbons als Grocy-Bestandsbuchungen.
  - **PDF-Upload** per Drag & Drop oder Dateiauswahl direkt in der Web-UI
  - **Automatische Ordnerueberwachung**: Konfigurierbarer Ordner (`/app/receipts`) wird
    periodisch auf neue PDFs gescannt (Intervall einstellbar)
  - **Duale Textextraktion**: Digitale PDFs werden direkt mit pdfplumber gelesen,
    gescannte PDFs per Tesseract OCR (deutsch) verarbeitet
  - **Intelligentes Bon-Parsing**: Regex-basierte Erkennung gaengiger deutscher
    Kassenbon-Formate (Marktname, Datum, Produkte mit Menge/Preis, Gesamtsumme)
  - **Fuzzy Product Matching**: Automatische Zuordnung von Bon-Produkten zu Grocy-Produkten
    per rapidfuzz (token_sort_ratio) mit konfigurierbarem Schwellwert
  - **Gelernte Zuordnungen**: Bestaetigte Zuordnungen werden gespeichert und bei
    zukuenftigen Bons automatisch angewendet (exakter Match vor Fuzzy-Match)
  - **Review-Workflow**: Items pruefen, Zuordnungen manuell korrigieren per Dropdown,
    dann bestaetigen — Bestand wird per `add_stock()` in Grocy gebucht
  - **Zuordnungsverwaltung**: Gelernte Zuordnungen einsehen und loeschen
  - **Neue Einstellungen**: Ueberwachungsordner, Scan-Intervall, Match-Schwellwert,
    Auto-Confirm-Schwellwert
  - **10 neue API-Endpunkte**: CRUD fuer Kassenbons, Items, Mappings, Upload, Confirm,
    Reject, Reprocess
  - **Neue Docker-Abhaengigkeiten**: tesseract-ocr, tesseract-ocr-deu, poppler-utils,
    pdfplumber, pdf2image, pytesseract, rapidfuzz
  - **Neues Volume**: `/app/receipts` fuer Ordnerueberwachung

---

## [1.1.0] - 2026-03-01

### Added

- **"Keine Warnung" per Produkt**: Warntage auf `0` setzen deaktiviert Benachrichtigungen
  für dieses Produkt vollständig (gilt für alle Alert-Typen: ablaufend, abgelaufen, Mindestbestand).
- **Verbrauchsdatum vs. MHD**: Benachrichtigungen unterscheiden jetzt zwischen
  Mindesthaltbarkeitsdatum (MHD) und Verbrauchsdatum (`due_type` aus Grocy).
- **Bestand direkt aus dem Dashboard hinzufügen**: In der "Unter Mindestbestand"-Liste
  gibt es pro Produkt einen "Hinzufügen"-Button. Ein Modal erlaubt das direkte Nachbuchen
  (Menge, optionales MHD/Verbrauchsdatum, optionaler Preis). Die Dashboard-Ansicht
  aktualisiert sich nach dem Buchen automatisch.
- **Kategorie- und Lagerort-Filter** (Einstellungen → Benachrichtigungen):
  Benachrichtigungen können auf bestimmte Grocy-Produktkategorien und/oder Lagerorte
  eingeschränkt werden. Ohne Auswahl werden alle berücksichtigt. Checkboxen werden im
  3-Spalten-Raster alphabetisch sortiert angezeigt.
- **Flexibles Wiederholungslimit**: Freies Zahlenfeld statt Dropdown. Jeder Wert ≥ 1 ist
  gültig; `0` bedeutet "immer benachrichtigen". Standard bleibt `1` (einmalig pro Produkt
  und Alarmzustand). Im Eingabefeld wird `0` als lesbares `immer` (DE) bzw. `always` (EN)
  angezeigt; Eingabe von `immer`/`always` wird als `0` interpretiert.
- **Wiederholungslimit pro Produkt**: Jedes Produkt hat auf der Produktseite ein eigenes
  "Wiederholung"-Feld. `0` = immer, Zahl = N-mal, leer = globalen Standard verwenden.
- **Per-Produkt-Einstellungen haben Vorrang vor Kategorie/Lagerort-Filter**: Ist für ein
  Produkt ein individuelles Wiederholungslimit gesetzt, wird es unabhängig vom Filter immer
  berücksichtigt.
- **Alle Grocy-Produkte auf der Produktseite**: Die Produktseite zeigt jetzt alle in Grocy
  definierten Produkte – nicht nur solche mit Bestand. Per-Produkt-Einstellungen sind
  jederzeit konfigurierbar.

### Changed

- **Prüfintervall-Beschriftung**: Label verdeutlicht jetzt, dass alle X Stunden geprüft und
  benachrichtigt wird (DE + EN).

---

## [1.0.4] - 2026-02-21

### Added

- **Version number in footer**: The current version is now displayed in the app footer
  (`© 2026 c42u · GPLv3 · Version x.x`).

### Fixed

- **CalDAV bidirectional task sync**:
  - **Completions from CalDAV were ignored**: `_sync_tasks_to_caldav` ran before
    `_sync_caldav_to_grocy` and overwrote CalDAV status changes (COMPLETED → NEEDS-ACTION)
    before they could be applied to Grocy. Sync order is now CalDAV→Grocy first, then
    Grocy→CalDAV — changes from both sides are correctly detected and propagated.
  - **Duplicate tasks (clone effect)** on CalDAV import: Creating a task in CalDAV and
    then completing it in Grocy produced a second open entry in CalDAV. The original
    CalDAV VTODO UID was overwritten in the sync map by a Grocylink UID, causing
    `_sync_tasks_to_caldav` to lose track of the VTODO and create a new one. The original
    UID is now permanently retained in the sync map; `_sync_tasks_to_caldav` reads it
    directly — no UID update in CalDAV, no duplicates.

---

## [1.0.3] - 2026-02-20

### Fixed

- **CalDAV bidirectional chore sync broken on many servers** (e.g. PrivateEmail, Dovecot-based):
  - Replaced `calendar.search(todo=True)` with `calendar.todos(include_completed=True)` in
    `_find_vtodo_by_uid` and `_sync_caldav_to_grocy`. Several CalDAV servers exclude completed
    VTODOs from REPORT query results by default, which caused completed reminders to be invisible
    to the sync engine — marking a reminder done never triggered chore execution in Grocy.
  - `_find_vtodo_by_uid` no longer misses completed VTODOs, preventing duplicate chore entries
    from being created in CalDAV after a chore was marked done in a client like Apple Reminders.
  - Extended the update check in `_sync_chores_to_caldav` to also compare the due date
    (`next_estimated_execution_time`) in addition to the chore name. Previously, only a name
    change triggered a CalDAV update — meaning the due date in CalDAV was never refreshed after
    a chore was executed in Grocy. After execution, the new due date is now correctly propagated
    to CalDAV and the VTODO status is reset to `NEEDS-ACTION` on the next sync cycle.

---

## [1.0.0] - 2026-01-01

### Added

- Initial release of Grocylink
- Dashboard with real-time overview of expiring, expired and missing products
- 6 notification channels: Email (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- Individual warning days per product
- CalDAV synchronization: bidirectional sync of Grocy tasks and chores
- New tasks created in CalDAV clients are automatically added to Grocy
- Automatic scheduler with configurable interval
- Test function for each notification channel
- Full notification log with filtering and sorting
- Encrypted storage of all passwords and API keys (Fernet/AES)
- Dark/Light mode (automatic + manual toggle)
- Multilingual support: German and English
- Non-root Docker container with minimal privileges
