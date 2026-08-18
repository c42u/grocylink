# grocylink – JSON-Schnittstelle (v1)

**Für die iOS-App.** Alle Endpunkte liegen unter `/api/v1/` und antworten in
JSON. Sie rufen **dieselben Funktionen** auf wie die Weboberfläche – was der
Browser zeigt, zeigt auch das iPhone.

---

## 1. Zugang {#1-zugang}

Je Gerät ein Schlüssel, erzeugt unter **Einstellungen → App-Zugänge**. Der
Schlüssel (`gl_…`) erscheint **einmal**; gespeichert wird nur sein SHA-256.

```http
GET /api/v1/info
X-API-Key: gl_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Alternativ `Authorization: Bearer gl_…`. Ohne gültigen Schlüssel antwortet
**jeder** Endpunkt mit `401` und `{"error": "…"}`; ein widerrufener Zugang gilt
wie ein unbekannter.

**Erreichbarkeit:** im Heimnetz bzw. über VPN, am selben Port wie die
Oberfläche (5000).

### Warum eine eigene Fassung neben `/api/…`

Die Weboberfläche ruft ihre 47 Endpunkte aus dem Browser **ohne** Schlüssel
auf. Eine Schlüsselpflicht dort hätte sie lahmgelegt. `/api/v1/` ist deshalb
eine abgesicherte Schicht darüber, die intern dieselben Funktionen aufruft –
keine zweite Umsetzung, die mit der Zeit auseinanderläuft.

## 2. Überblick und Vorrat {#2-vorrat}

| Endpunkt | Zweck |
|---|---|
| `GET /info` | Fassung, Zugangsname, was konfiguriert ist |
| `GET /status` | Dashboard: ablaufend, überfällig, abgelaufen, fehlend |
| `GET /products` | Produkte mit Ablaufdaten und Übersteuerungen |
| `POST /products/override` | Warntage je Produkt festlegen |
| `POST /stock/add` | Bestand nachtragen |
| `GET /product-groups` · `/locations` · `/quantity-units` | Stammdaten aus Grocy |

`GET /info` eignet sich zum Prüfen beim Einrichten:

```json
{"version": "1.6.0", "api": "v1", "grocy_konfiguriert": true,
 "bring_konfiguriert": true, "caldav_konfiguriert": false,
 "zugang": "iPhone von c42u"}
```

## 3. Einstellungen, Kanäle, Protokoll {#3-einstellungen}

| Endpunkt | Zweck |
|---|---|
| `GET /settings` · `POST /settings` | alle Einstellungen lesen und schreiben |

**Die Einstellung `language` (`de` / `en`) gilt seit 1.7.0 serverseitig.** Sie bestimmt nicht nur die Oberflaeche, sondern auch die Texte, die der Server formuliert: Testnachrichten an Kanaele, Warnmeldungen und die Eintraege im Log. Eine App, die sie ueber `POST /settings` aendert, aendert damit auch die Sprache der Benachrichtigungen.

| `POST /test-connection` | Grocy-Zugang prüfen |
| `GET /channels` · `POST /channels` | Benachrichtigungskanäle lesen und anlegen |
| `DELETE /channels/<id>` · `POST /channels/<id>/test` | entfernen, testen |
| `GET /log` · `DELETE /log` | Protokoll lesen und leeren |
| `POST /check-now` | Prüfung sofort ausführen |

Sechs Kanäle stehen zur Wahl: E-Mail, Pushover, Telegram, Slack, Discord,
Gotify.

## 4. CalDAV {#4-caldav}

| Endpunkt | Zweck |
|---|---|
| `GET /caldav/status` | Zustand des Abgleichs |
| `POST /caldav/test` | Zugang prüfen |
| `GET /caldav/calendars` | verfügbare Kalender |
| `POST /caldav/sync-now` | Abgleich sofort ausführen |
| `GET /caldav/map` · `DELETE /caldav/map` | Zuordnungstabelle lesen, leeren |

## 5. Bring! {#5-bring}

| Endpunkt | Zweck |
|---|---|
| `GET /bring/status` | Zustand des Abgleichs |
| `POST /bring/test` | Zugang prüfen |
| `GET /bring/lists` | Listen des Kontos |
| `POST /bring/sync-now` | Abgleich sofort ausführen |
| `GET /bring/list-items` · `PUT /bring/list-items` | Positionen lesen und ändern |
| `POST /bring/items/manual` | Position von Hand hinzufügen |
| `GET /bring/overrides` · `POST /bring/overrides` | Übersteuerungen je Produkt |
| `GET /bring/map` · `DELETE /bring/map` | Zuordnungstabelle |

## 6. Was die Schnittstelle nicht kann {#6-grenzen}

**Kassenbons und Barcode-Suche** – mit dem Nutzer so festgelegt. Beides lebt
von Kamera und Dateiupload; wenn es in die App soll, wird es eine eigene
Anforderung mit eigenem Zuschnitt.

## 7. Fehler {#7-fehler}

| Code | Bedeutung |
|---|---|
| 400 | Anfrage unbrauchbar oder Grocy nicht konfiguriert |
| 401 | kein gültiger Zugang |
| 500 | unerwarteter Fehler |

Die vorhandenen Endpunkte antworten mit `{"error": "…"}` – die Meldungen
stammen aus der Weboberfläche und sind für Menschen geschrieben. **Zeig sie
an**, statt sie durch eigene zu ersetzen.

Autor: c42u · Co-Autor: ClaudeCode · Lizenz: GPLv3
