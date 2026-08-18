# Changelog

All notable changes to Grocylink will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **A note on version numbers.** Development runs on its own line; the public
> releases on Docker Hub and GitHub follow the `1.2.x` series. Where the two
> differ, the entry says so. Entries up to 1.6.0 are in German.

---

## [1.7.1] - 2026-08-18

*Published as **1.2.2** on Docker Hub — see the note below.*

Follow-up to 1.7.0: under *Settings → App access* the translation keys were
shown verbatim (`keys.title`, `keys.device`, `keys.create` …) instead of the
texts.

### Fixed

* **Five keys were never defined.** `index.html` refers to `keys.title`,
  `keys.hint`, `keys.new`, `keys.once` and `keys.create` — they had never been
  added to `i18n.js`. The translation helper returns the key itself when it
  does not know it, which is why the key ended up on the page.
* **The German set landed in the English block.** The remaining `keys.*`
  entries were inserted twice into the English section of `i18n.js`. German was
  missing them entirely, while English carried German texts.
* **The placeholder in the key-name field** ("z. B. iPhone von c42u") was
  hard-coded German and now carries `data-i18n`.

### Added

* `tests/test_i18n_vollstaendig.py`: checks that **every** key used in
  `index.html` or `app.js` exists in **both** languages, that both languages
  carry the same set, and that no key appears twice — a second entry silently
  overrides the first. Exactly these three checks would have prevented the bug.
  68 tests pass.
* The README documents the `/api/v1` interface in both languages, including the
  note that an iOS app is being built on it.

---

## [1.7.0] - 2026-08-18

*Published as **1.2.1** on Docker Hub.*

Fixes [#1](https://github.com/c42u/grocylink/issues/1): the language setting
only ever applied to the browser. Everything the **server** writes stayed
German — and in a fresh window the whole UI was back in German.

### Fixed

* **The language is now a server setting.** `static/i18n.js` read it from
  `localStorage`; it was stored on the server as well, but never read back from
  there. `GET /` now ships the page with the configured language already
  applied (`<html lang="…">` and `window.SERVER_LANG`) — without the brief
  German flash a later fetch would cause. The browser store remains as a
  fallback.
* **Server-side texts follow that setting**: the "check completed" response,
  the **test notification sent to a channel** (the reported Discord case), the
  sync message and thirteen further API responses.
* **Log entries in the UI switch language too** — including ones already
  written. The database now holds **key and values** instead of a finished
  sentence (new columns `message_key`, `message_args`); the text is built when
  it is displayed. Entries without a key — exception messages and anything
  written before 1.7.0 — are kept as they are: a German error message beats no
  message at all.
* **App access keys translated** (from 1.6.0): table header, "never",
  "revoke" and the confirmation prompt were hard-coded in the script.

### Not changed

The **application log** (`logger.…`) stays German. It is operational
diagnostics, and a fixed language is easier to grep than one that moves with a
setting. The log **in the UI** is user-facing text and is translated.

### Technical

* New: `Code/sprache.py` — one table for all server-side texts (de/en, 33
  keys), `t(key, lang=None, **values)` and `sprache_lesen()` (language from
  `settings.language`, default `de`).
* `scheduler.TRANSLATIONS` moved there; the 11 keys of the alert dispatch now
  sit next to those of the API.
* `add_log_entry(..., key=…, args=…)` and `get_log(limit, lang=…)`.
* `setLanguage(lang, save)` — applying an already stored language no longer
  writes it back.
* New test module `tests/test_sprache.py` (12 checks); 65 tests pass.

---

## [1.6.0] - 2026-08-17

Eine abgesicherte JSON-Schnittstelle fuer eine eigene iOS-App. Bis auf
Kassenbons und Barcode-Suche laesst sich damit alles steuern, was die
Weboberflaeche kann.

### Added

* **`/api/v1/` mit Geraeteschluesseln.** Je Geraet ein Schluessel (`gl_…`),
  unter *Einstellungen -> App-Zugaenge* erzeugt, mit "angelegt" und "zuletzt
  benutzt", einzeln widerrufbar. In der Datenbank steht nur der **SHA-256** --
  ein Schluessel, der sich zurueckholen laesst, ist keiner. Mitgegeben wird er
  als `X-API-Key` oder `Authorization: Bearer`.
* **Abgedeckt:** Ueberblick und Vorrat (`status`, `products`,
  `products/override`, `stock/add`, Stammdaten), Einstellungen, Kanaele
  (lesen, anlegen, entfernen, testen), Protokoll, `check-now`, CalDAV
  (Status, Test, Kalender, `sync-now`, Zuordnung) und Bring! (Status, Test,
  Listen, `sync-now`, Positionen lesen/aendern, manuelle Position,
  Uebersteuerungen, Zuordnung).
* **`GET /api/v1/info`** zum Pruefen beim Einrichten: Fassung, Zugangsname und
  was konfiguriert ist.
* Schnittstellenbeschreibung: `Dokumentation/grocylink-API.md` (+PDF).

### Warum eine eigene Fassung neben `/api/…`

Die Weboberflaeche ruft ihre 47 Endpunkte aus dem Browser **ohne** Schluessel
auf; eine Schluesselpflicht dort haette sie lahmgelegt, und ein Sonderweg fuer
"Anfragen aus dem eigenen Browser" waere geraten. `/api/v1/` ist deshalb eine
abgesicherte Schicht darueber, die **dieselben View-Funktionen** aufruft --
keine zweite Umsetzung, die mit der Zeit auseinanderlaeuft.

### Nicht enthalten

**Kassenbons und Barcode-Suche** -- mit dem Nutzer so festgelegt. Beides lebt
von Kamera und Dateiupload und braucht, wenn ueberhaupt, einen eigenen
Zuschnitt.

---

## [1.5.0] - 2026-08-09

Haertung des Bring!-Layers. Kein sichtbares neues Feature, aber deutlich
weniger Last gegenueber der Bring-API - Grundlage fuer die geplante
Rueckrichtung Bring -> Grocy.

### Added

- **Neues Modul `bring_runtime.py`**: ein dauerhafter asyncio-Eventloop in
  einem Daemon-Thread haelt aiohttp-Session und eingeloggten Bring-Client
  zwischen den Aufrufen am Leben.
  - Client wird ueber einen Fingerprint der Zugangsdaten zwischengespeichert;
    aendern sich Mail oder Passwort, wird automatisch neu eingeloggt
  - Access-Token erneuert `bring-api` selbst per Refresh-Token, solange der
    Client lebt
  - Einmaliger Relogin bei abgelaufenem Token (`BringAuthException`)
  - Zeitlimit pro Aufruf (180s), damit ein haengender Request keinen
    Gunicorn-Worker blockiert
- **Testsuite fuer den Bring!-Layer** unter `Code/tests/` (48 Tests,
  91% Abdeckung von `bring_sync.py` und `bring_runtime.py`). Laeuft ohne
  Netzwerk und ohne Datenbank gegen eine Client-Attrappe.
  - `Code/requirements-dev.txt` und `Code/pytest.ini` neu
  - Aufruf: `python3 -m pytest` im Ordner `Code/`

### Changed

- **Ein Login statt einem pro Request.** Bisher oeffnete jeder Aufruf
  (Status, Listen, Listeninhalt, Sync) einen eigenen Eventloop, eine eigene
  Session und einen eigenen Login. Ein Wechsel auf den Bring!-Tab kostete
  damit mehrere Anmeldungen hintereinander.
- **Sync braucht statt rund 2N nur noch zwei Requests.** Anlegen, Aendern
  und Entfernen sind in der Library allesamt `batch_update_list` mit
  unterschiedlicher Operation - der Sync sammelt die Differenz jetzt und
  schickt sie gebuendelt (in Bloecken zu 50). Faellt ein Sammelrequest um,
  werden die Aenderungen des Blocks einzeln nachgereicht, damit ein
  einzelnes stoerendes Produkt nicht den ganzen Block kostet.
- **Kein Vollabruf der Liste mehr nach jedem neuen Eintrag.** Die Item-UUID
  darf beim Anlegen selbst vergeben werden (`uuid4`), das frueher noetige
  `get_list()` zum Nachschlagen entfaellt - beim Sync ebenso wie beim
  manuellen Hinzufuegen und beim Umbenennen.
- **Die `bring_sync_map` wird erst nach erfolgreicher Uebertragung
  geschrieben.** Vorher konnte sie Eintraege fuehren, die auf der
  Bring-Liste nie ankamen.
- Geaenderte Bring-Zugangsdaten verwerfen den gecachten Client sofort
  (`POST /api/settings` und `POST /api/bring/test`).

### Misc

- `APP_VERSION` 1.4.13 -> 1.5.0, User-Agent-Strings aktualisiert
- `bring-api` bleibt auf 1.1.2 - das ist der aktuelle Stand auf PyPI
  (04.05.2026), es gibt nichts zu heben
- `.dockerignore` schliesst `Code/tests/` und Bytecode aus dem Image aus

---

## [1.4.13] - 2026-05-08

### Added

- **Aktive Seite ueberlebt einen Reload**: Beim Reload landet man jetzt
  auf der zuletzt geoeffneten Seite statt immer im Dashboard
  (`localStorage`-basiertes Routing). Wechsel ueber die Sidebar
  speichert die aktuelle Page automatisch.

### Changed

- **"Aktuelle Einkaufsliste" laedt deutlich schneller.** Backend war
  vorher pro Bring-Item zwei sequentielle Grocy-Calls
  (`get_product_userfields` + `get_product_details`); bei 30 Items
  ergab das ~60 Roundtrips. Jetzt:
  - Userfield `grocylink_unit_price` wird direkt aus `/api/objects/products`
    gelesen (`show_as_column_in_tables=1` exposed das Feld als Spalte) -
    spart einen Call pro Item komplett.
  - `last_price` wird parallel via `ThreadPoolExecutor` (8 Worker)
    gefetcht statt sequentiell.
  - Effekt: ~5x schneller bei typischen Listen, deduplizierte Calls
    (gleiche product_id wird nur einmal gefragt).
- **"Item" -> "Produkt"** im Bring!-Tab konsequent: Stat-Card
  "Items synchronisiert" -> "Produkte synchronisiert", Auto-Remove-
  Beschriftung, Sync-Mapping-Hinweis "Noch keine Produkte..." (DE+EN).

### Misc

- `APP_VERSION` 1.4.12 -> 1.4.13, User-Agent-Strings aktualisiert

---

## [1.4.12] - 2026-05-08

### Fixed

- **Kassenbon-Buchung war intransparent bei Fehlern:** Beim Klick auf
  "Bestaetigen & Buchen" lief der Endpoint durch, setzte den Status pauschal
  auf `confirmed` und gab N rote Toasts zurueck - aber **nichts landete im
  notification_log**, der Bon-Status verbarg den Teil-Erfolg, und Items waren
  in Grocy nicht angelegt. Jetzt:
  - Jeder Item-Fehler wird mit `add_log_entry` als `receipt_error` ins Log
    geschrieben (mit Bon-ID + Markt + Datum als Kontext).
  - Logger schreibt zusaetzlich den vollen Stacktrace pro Fehler ins
    Container-Log.
  - Bon-Status haengt jetzt vom Ergebnis ab:
    - `confirmed`: alle Positionen erfolgreich gebucht
    - `partial`: einiges gebucht, einiges fehlgeschlagen
    - `error`: keine Buchung, alle Items fehlten
  - Zusammenfassungs-Eintrag pro Bon im Log (`receipt_summary`).
  - Frontend zeigt **einen Sammel-Toast** ("X gebucht, Y fehlgeschlagen –
    Details siehe Log") statt N einzelne. Details werden in einem Modal
    aufgelistet, das Review-Modal bleibt offen, damit der User die nicht
    gebuchten Positionen nachbearbeiten kann.

### Added

- Neuer Status **"Teilweise gebucht"** (`partial`) in der Kassenbon-Tabelle
  mit gelbem Badge.
- Neue Log-Typen `receipt_error`, `receipt_summary`, `bring_sync`,
  `bring_manual` mit eigenen Farb-Badges und i18n-Labels (waren bislang
  nicht typisiert dargestellt).

### Misc

- `APP_VERSION` 1.4.11 -> 1.4.12, User-Agent-Strings aktualisiert
- `ok` im JSON-Response von `/api/receipts/<id>/confirm` jetzt nur
  noch true wenn mind. ein Item gebucht wurde.

---

## [1.4.11] - 2026-05-08

### Fixed

- **Gesamtpreis-Summierung war falsch:** zwei Ursachen behoben.
  1. `parseFloat("2,49")` liefert in JS `2`, nicht `2.49`. Im Frontend
     wurden Live-Werte mit Komma als Dezimaltrennzeichen verstuemmelt.
     Neuer Helper `parseLocaleNumber` akzeptiert sowohl `2,49` als auch
     `2.49` und wird ueberall in der Bring-Tabelle benutzt.
  2. Items ohne explizit gespeicherten Stueckpreis, aber mit `last_price`
     aus Grocy, wurden in der Live-Berechnung als "kein Preis" gewertet
     - dadurch summierte das Frontend zu wenig. Neu:
     `bringEffectivePrice(row, idx)` faellt auf `last_price` aus dem
     Origin-Snapshot zurueck (gleiche Logik wie das Backend).
- **Anzahl in Spec wurde nicht zuverlaessig erkannt:** Regex erforderte
  bisher ein Leerzeichen zwischen `x` und Info. Jetzt matcht auch
  `2xVollmilch` (ohne Space). Mengenangaben wie `200ml`, `500g`,
  `2,5L Wasser` werden weiterhin korrekt als Info behandelt
  (kein `x` direkt nach der Zahl).

### Misc

- `APP_VERSION` 1.4.10 -> 1.4.11, User-Agent-Strings aktualisiert
- Origin-Snapshot enthaelt jetzt `last_price` fuer korrekte Live-Summen

---

## [1.4.10] - 2026-05-08

### Fixed

- **Stueckpreis konnte nicht eingetragen werden**, weil das Eingabefeld
  bei Bring-Items ohne Grocy-Match disabled war. Feld ist jetzt **immer
  editierbar**; Items ohne Grocy-Verknuepfung haben einen dezent gelben
  gestrichelten Rand (`bring-edit-price-unmatched`). Beim Speichern ohne
  Match liefert das Backend einen klaren 400 mit erklaerendem Toast.
- **Gesamtpreis-Kumulierung** lief ins Leere, weil viele Bring-Items
  keinen Grocy-Match bekamen (Bring normalisiert Item-Namen, exact-Match
  scheiterte). Jetzt **Fuzzy-Match als Fallback** mit `rapidfuzz`
  (`token_set_ratio`, Cutoff 75%) - dadurch werden mehr Items zugeordnet,
  Preise und Totals werden ueberhaupt erst berechenbar.

### Added

- **Listen werden automatisch geladen**, sobald der Bring!-Tab geoeffnet
  wird und Bring-Konto+Passwort gesetzt sind. Kein manueller "Laden"-
  Klick mehr noetig.

### Misc

- `APP_VERSION` 1.4.9 -> 1.4.10, User-Agent-Strings aktualisiert

---

## [1.4.9] - 2026-05-07

### Fixed

- **Cache-Busting fuer Static-Assets:** `style.css`, `app.js` und `i18n.js`
  haben jetzt einen Versions-Querystring (`?v=1.4.9` etc.). Das war der
  eigentliche Grund warum der Frontend-Fix aus 1.4.8 fuer den Stueckpreis
  beim User nicht ankam – der Browser hat die alte JS-Version aus dem
  Cache bedient.

### Added

- **Gesamtpreis-Anzeige** rechts oben in der Karten-Ueberschrift
  "Aktuelle Einkaufsliste". Live-Berechnung als Summe aller Zeilen-
  Totale, aktualisiert sich beim Tippen.
- **Waehrung wird jetzt aus Grocy uebernommen** (CURRENCY-Setting via
  `/api/system/config`). Stueckpreis, Gesamt-Spalte und Gesamtpreis
  zeigen das passende Waehrungssymbol (z.B. €, $, CHF, ...). Fallback
  ist EUR, falls Grocy nicht erreichbar ist.

### Changed

- `GrocyClient.get_system_config()` und `get_currency()` neu
- `GET /api/bring/list-items` liefert zusaetzlich `currency`
- Frontend: `formatPriceNumber` separat von `bringFormatPrice` (mit Symbol),
  Symbol via `Intl.NumberFormat.formatToParts`

### Misc

- `APP_VERSION` 1.4.8 -> 1.4.9, User-Agent-Strings aktualisiert
- 1 neuer i18n-Key (`bring.view_grand_total`, DE+EN, Diff = 0)

---

## [1.4.8] - 2026-05-07

### Fixed

- **Stueckpreis konnte nicht gespeichert werden:** Der PUT-Endpoint hat
  beim Speichern immer ein Bring-Update mitgeschickt, auch wenn nur der
  Preis geaendert wurde. Wenn Bring update_item bei "kein Diff" nicht sauber
  durchlief, wurde das Grocy-Userfield-Update nicht mehr ausgefuehrt.
  Frontend schickt jetzt nur die wirklich geaenderten Felder, Backend
  faehrt Bring- und Grocy-Update unabhaengig voneinander.

### Added

- **Detail-Spalte aufgeteilt** in zwei Spalten: **Anzahl** (Number) und
  **Weitere Info** (Text). Beim Push nach Bring werden sie als
  `<n>x <Info>` zusammengefuegt (z.B. `3x Vollmilch`). Beim Lesen wird die
  Spec entsprechend wieder zerlegt.
- **Spalte "Gesamt"** zwischen Stueckpreis und Aktion: Anzahl x Stueckpreis,
  live im UI berechnet beim Tippen.
- **Globaler Button "Alle Änderungen speichern"** unter der Tabelle:
  sammelt Diffs aller Zeilen und speichert sie sequenziell. Toast meldet
  Erfolg + ggf. Anzahl Fehler.
- Geaenderte Zeilen werden visuell hervorgehoben (`row-dirty`, leichtes Gelb).

### Changed

- **Footer mittig:** Der Block (Copyright, KI-Disclaimer, Bugs-Link) wird
  jetzt zentriert dargestellt. Logo links via `position: absolute`, sodass
  der Text echt mittig steht und nicht durch den Logo-Platz verschoben wird.
- API `GET /api/bring/list-items` liefert zusaetzlich `quantity`, `info`
  und `total_price` (= quantity x effective_price); vorhandenes `spec`-Feld
  bleibt zur Rueckwaertskompatibilitaet erhalten.
- API `PUT /api/bring/list-items` akzeptiert jetzt `quantity`+`info` statt
  `spec`. Felder sind alle optional - was fehlt, wird nicht angefasst.
  Ein reiner `unit_price`-Update loest kein Bring-Update mehr aus.
- 8 neue i18n-Keys (DE+EN, Diff = 0)

### Misc

- `APP_VERSION` 1.4.7 -> 1.4.8, User-Agent-Strings aktualisiert

---

## [1.4.7] - 2026-05-07

### Changed

- Sidebar-Reihenfolge: CalDAV bekommt einen eigenen Block zwischen
  Kassenbons und Einstellungen, mit Trennern oben und unten:
  Bring!, Kassenbons | CalDAV | Einstellungen, Hilfe, Log
- `APP_VERSION` 1.4.6 -> 1.4.7, User-Agent-Strings aktualisiert

---

## [1.4.6] - 2026-05-07

### Changed

- **Sidebar neu gruppiert** mit Trennern fuer bessere Lesbarkeit:
  1. Dashboard
  2. Kanaele, Produkte
  3. CalDAV, Bring!, Kassenbons
  4. Einstellungen, Hilfe, Log
  5. Kaffee, Fehlermeldung
  Bring! sitzt jetzt zwischen CalDAV und Kassenbons (Sync-Block).
  Einstellungen ueber Hilfe, Log unter Hilfe.
- "Kaffee?" -> "Kaffee" (Fragezeichen entfernt; EN: "Coffee?" -> "Coffee")
- Neue CSS-Klasse `.nav-divider` als zarter horizontaler Trenner
  (1px, rgba(255,255,255,.1)) analog zum Border ueber `sidebar-section`
- **Stripe-Spendenlink aus Fusszeile entfernt** (Block `footer-right`
  inkl. SVG-Logo), zugehoeriges CSS `.footer-right` raus

### Misc

- `APP_VERSION` 1.4.5 -> 1.4.6, User-Agent-Strings aktualisiert

---

## [1.4.5] - 2026-05-07

### Added

- **Stueckpreis pro Produkt in Grocy als Userfield** `grocylink_unit_price`
  (Type: number-decimal). Wird in der Karte "Aktuelle Einkaufsliste" pro
  Produktzeile als editierbares Eingabefeld angezeigt.
  - Userfield-Definition wird automatisch in Grocy angelegt, sobald sie zum
    ersten Mal gesetzt wird (`GrocyClient.ensure_userfield`).
  - Anzeige-Reihenfolge: Userfield-Wert > `last_price`/`avg_price` aus dem
    Stock-Log (Userfield hat Vorrang).
  - Wird der Eingabewert geleert, wird der Userfield-Wert in Grocy geloescht.
- **Bring-Items inline editierbar:** Pro Zeile koennen Name, Detail/Spec
  und Stueckpreis direkt geaendert werden. Save-Button pro Zeile.
  - Name-Aenderung: Eintrag wird mit neuem Namen neu angelegt und der alte
    via UUID entfernt (Bring zeigt umbenannte Items via update_item nicht
    zuverlaessig in der App an, save+remove ist konsistenter).
  - Spec-Aenderung: `update_item` mit UUID.
  - Preis-Aenderung: Userfield-Set in Grocy (nur wenn Produkt zugeordnet).
- Neue API-Endpoints/Methoden:
  - `PUT /api/bring/list-items` – kombiniertes Update (Bring + Grocy)
  - `BringSync.update_list_item(list_uuid, item_uuid, name, spec, old_name)`
  - `GrocyClient.ensure_userfield`, `get_userfield_definitions`,
    `create_userfield_definition`, `get_product_userfields`

### Changed

- Spaltenkopf "Letzter Preis" -> "Stueckpreis" in der Bring-View-Tabelle
- `last_price` aus Grocy wird jetzt als Placeholder im Preis-Input angezeigt,
  wenn noch kein Userfield-Wert gesetzt ist
- Bei Bring-Items ohne Grocy-Match ist das Preis-Input deaktiviert (kein
  Speicherort)
- 14 neue i18n-Keys (DE+EN, Diff = 0)
- `APP_VERSION` 1.4.4 -> 1.4.5, User-Agent-Strings aktualisiert

---

## [1.4.4] - 2026-05-07

### Changed

- **Sidebar:** "Unterstuetzung"-Link durch direkten Buy-Me-A-Coffee-Link
  (https://buymeacoffee.com/c42u) ersetzt – mit Lucide-Coffee-Icon und
  dezent gelb-orangem Hover-Style (analog DALI ServUI). Oeffnet in neuem Tab.
- Komplette Seite `page-support` entfernt (146 HTML-Zeilen) inklusive aller
  zugehoerigen Logik:
  - JS-Bezuege auf `supportDe`/`supportEn` und `page === 'support'` raus
  - i18n-Keys `nav.support` raus, neu: `nav.coffee` und `nav.coffee_title`
  - CSS `.support-*`-Block (~120 Zeilen) raus

### Added

- CSS `.nav-link-coffee` mit Hover-Highlight

### Misc

- `APP_VERSION` 1.4.3 -> 1.4.4, User-Agent-Strings aktualisiert

---

## [1.4.3] - 2026-05-07

### Added

- **Karte "Aktuelle Einkaufsliste"** im Bring!-Tab: Liste auswaehlen ->
  Produkte aus Bring werden tabellarisch dargestellt (Produkt, Detail,
  Letzter Preis). Wird zu einem Bring-Produkt ein passender Grocy-Eintrag
  gefunden (per `bring_sync_map`-UUID oder ueber Namens-Match), wird zusaetzlich
  der letzte Einkaufspreis aus Grocy (`last_price`/`avg_price`) angezeigt.
- Neuer Endpoint: `GET /api/bring/list-items?list_uuid=<uuid>`
- Neue Methode `BringSync.get_list_items()`

### Changed

- **UI-Texte:** "Item manuell hinzufuegen" -> "Produkt manuell hinzufuegen",
  "Item-Name" -> "Produkt-Name" (DE+EN konsistent)
- **Manual-Add:** Option "Globale Liste verwenden" entfernt. Stattdessen wird
  beim Listen-Laden die globale Liste automatisch im Ziel-Listen-Dropdown
  vorausgewaehlt. Der User MUSS jetzt eine konkrete Liste waehlen.
- Beim Hinzufuegen eines Produkts ueber das Manual-Dropdown wird die
  "Aktuelle Einkaufsliste"-Karte automatisch aktualisiert, falls dieselbe
  Liste angezeigt wird.
- Listen-Dropdown beim Laden spiegelt jetzt in alle drei Sub-Dropdowns
  (Hauptauswahl, Manual-Add, View)
- `APP_VERSION` 1.4.2 -> 1.4.3, User-Agent-Strings aktualisiert

---

## [1.4.2] - 2026-05-06

### Added

- **Manuelles Hinzufuegen einzelner Items** auf eine Bring!-Liste, ohne dafuer
  ein Grocy-Produkt zu brauchen. Neue Karte "Item manuell hinzufuegen" im
  Bring!-Tab mit Eingabefeldern fuer Name, Detail/Menge und Ziel-Liste.
  - Default ist die global konfigurierte Bring!-Liste
  - Optional eine andere Liste aus dem Dropdown waehlen (produktspezifisch)
  - Neuer Endpoint: `POST /api/bring/items/manual` (Body: `name`, `spec`, `list_uuid`)
  - Neue Methode `BringSync.add_item_manual()`
  - Items werden im `notification_log` als Typ `bring_manual` protokolliert
- **UI-Hinweis** unter dem Listen-Dropdown: "Einkaufslisten koennen nur ueber
  die Bring!-App angelegt werden" (entspricht der Plattform-Limitierung)

### Changed

- `APP_VERSION` 1.4.1 -> 1.4.2, User-Agent-Strings aktualisiert
- Listen-Dropdown beim Laden spiegelt automatisch in das manuelle "Ziel-Liste"-Dropdown

---

## [1.4.1] - 2026-05-06

### Fixed

- **Bring!-Verbindungstest schlug mit `'BringListResponse' object is not subscriptable`
  fehl**: Die Library `bring-api` 1.1.2 liefert Dataclasses statt Dicts
  (`BringListResponse`, `BringItemsResponse`, `BringPurchase`, `Items`, `BringList`).
  Drei Stellen in `bring_sync.py` umgestellt auf Attribut-Zugriff
  (`.lists`, `.listUuid`, `.items.purchase`, `.itemId`, `.specification`, `.uuid`).

### Changed

- `APP_VERSION` 1.4.0 -> 1.4.1, User-Agent-Strings (OFF + Bring) aktualisiert

---

## [1.4.0] - 2026-05-06

### Added

- **Bring!-Synchronisation** (eigener Sync-Layer neben CalDAV): Grocy-Eintraege
  werden in eine Bring!-Einkaufsliste geschoben.
  - Neuer Tab **Bring!** in der Sidebar mit Status-Karten, Konto-Setup,
    Listen-Auswahl, Sync-Einstellungen und Mapping-Tabelle
  - Quellen-Modi (Setting `bring_source`):
    - `shopping_list` (Default): Grocy-Einkaufsliste wird komplett uebernommen
    - `missing`: nur Produkte mit unterschrittenem Mindestbestand
  - Item-Spec wird aus Menge + Mengeneinheit (Plural-Form falls vorhanden) gebaut
  - Dedup ueber UUID-Mapping in neuer Tabelle `bring_sync_map`
  - Per-Produkt-Overrides in neuer Tabelle `bring_item_overrides`:
    `hide_from_bring`, `custom_name`, `custom_spec`
  - Auto-Remove (Setting `bring_auto_remove`, Default aus): Items, die nicht mehr
    benoetigt werden, werden aus Bring! entfernt
  - Sanitizer ersetzt das in der Bring-API problematische `%` durch `Prozent`
  - Sync-Intervall ueber APScheduler (`schedule_bring_sync()`)
  - v1 unidirektional (Grocy -> Bring!), bidirektionaler Modus fuer spaeter geplant
- Neue Bibliothek: `bring-api==1.1.2` (miaucl, async aiohttp)
- Neue Backend-Endpoints:
  `/api/bring/status`, `/api/bring/test`, `/api/bring/lists`,
  `/api/bring/sync-now`, `/api/bring/map`, `/api/bring/overrides`
- Neue Grocy-Client-Methoden: `get_shopping_list()`, `get_shopping_lists()`
- 47 neue i18n-Keys (DE + EN) fuer den Bring!-Bereich

### Changed

- Setting `bring_password` in `SENSITIVE_SETTINGS` aufgenommen (Fernet-Verschluesselung)
- `User-Agent` der OpenFoodFacts-Abfragen auf `Grocylink/1.4.0` aktualisiert
- `APP_VERSION` 1.3.2 -> 1.4.0

### Notes

- Bring! Labs bietet keine offizielle API. Die Integration nutzt eine
  reverse-engineered Library und kann brechen, wenn Bring! die App-API umbaut.
- Im UI wird ein entsprechender Disclaimer angezeigt.

---

## [1.3.2] - 2026-04-20

### Changed

- **Versionssprung** von 1.2.1 auf 1.3.2: Angleichung an die in der internen
  Registry bereits vorhandenen Tags (1.3.0, 1.3.1).
  Die Versionen 1.2.2 und 1.3.0/1.3.1 entfallen in diesem Changelog, der Sprung
  stellt die Konsistenz zwischen Git, App, Registry und Deploy wieder her.

### Added

- **CI/CD**: develop-Branch + Promote-Stage eingefuehrt
  - develop-Flow mit `push-test`, `deploy-test` und `promote-to-latest` ergaenzt
  - Neuer `promote-to-latest` Job: manuelles Retagging develop→latest per docker (kein Neubau)
  - `deploy-prod-promoted` fuer Wirkdeploy nach Promote
  - Hadolint Dockerfile-Lint hinzugefuegt

---

## [1.2.1] - 2026-03-10

### Fixed

- **JavaScript SyntaxError**: Doppelte `const row` Deklaration in `suggestCategory()`
  verhinderte das Laden von app.js — Menueauswahl war komplett defekt.

### Added

- **EAN/Barcode-Suche im Kassenbon-Review**: Pro Bon-Position ein Barcode-Eingabefeld
  mit Live-Suche. Workflow:
  1. EAN eingeben und suchen
  2. Grocy-Treffer: Produkt wird automatisch im Dropdown ausgewaehlt
  3. Kein Grocy-Treffer: OpenFoodFacts wird als Fallback abgefragt
  4. OFF-Treffer: Name und Barcode werden in die Felder fuer neues Produkt uebernommen
  5. Kein Treffer: Rote Markierung, manuelle Zuordnung noetig
- Neuer Backend-Endpoint `/api/barcode/lookup` (Grocy-first, OFF-Fallback)
- Neue Methode `search_product_by_barcode()` in `grocy_client.py`
- 7 neue i18n-Keys fuer die Barcode-Suche (DE + EN)
- CSS-Styles fuer Barcode-Lookup (Eingabefeld, Farbindikatoren)

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
