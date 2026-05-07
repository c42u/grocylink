# Table of contents / Inhaltsverzeichnis
1. [Grocylink - english](#english)
2. [Grocylink - deutsch](#deutsch)
3. [Impressum](IMPRESSUM.md)
---

# Grocylink <a name="english"></a>

Grocylink extends [Grocy](https://grocy.info/) with automatic expiry alerts, multi-channel notifications and bidirectional CalDAV synchronization.

Self-hosted, offline-capable and fully under your control.

---

## Features

- **Dashboard** with real-time overview of expiring, expired and missing products
- **6 notification channels**: Email (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- **Individual warning days per product** — e.g. milk 2 days, canned goods 30 days; set to `0` to disable notifications for a specific product entirely
- **Best-before vs. use-by date**: Grocylink reads the `due_type` field from Grocy and labels notifications accordingly — useful if you want to treat use-by dates (e.g. fresh meat) differently from best-before dates (e.g. pasta)
- **Category and location filter**: Limit notifications to specific Grocy product categories and/or storage locations — ideal if you only care about certain areas (e.g. fridge) or product groups
- **Add stock directly from dashboard**: Restock below-minimum products without leaving Grocylink
- **Notification repeat limit**: Choose how often Grocylink notifies per product and alert state — Always (default), Once, 2×, 3×, or 5×. The counter resets automatically when a product is restocked or leaves the alert state
- **CalDAV synchronization**: Sync Grocy tasks and chores bidirectionally with CalDAV clients (2Do, Apple Reminders, Tasks.org and more)
- **New tasks** created in CalDAV clients are automatically added to Grocy
- **Configurable check interval** with automatic scheduler
- **Test function** for each notification channel
- **Full notification log** with filtering and sorting
- **Encrypted storage** of all passwords and API keys (Fernet/AES)
- **Dark/Light mode** (automatic + manual toggle)
- **Multilingual**: German and English
- **Non-root container** with minimal privileges

---

## How notifications work

Grocylink checks your Grocy stock on a configurable interval (default: every 6 hours). When a product meets an alert condition, a notification is sent to all enabled channels.

**When is a notification triggered?**

| Condition | Trigger |
|---|---|
| Expiring | Product's best-before or use-by date is within the configured warning days |
| Expired | Product's best-before or use-by date has passed |
| Below minimum stock | Current stock is below the minimum defined in Grocy |

**Example — fresh minced meat with a 1-day use-by date:**
With the default warning of 5 days, minced meat bought today with a use-by date of tomorrow will trigger an expiry notification immediately on the next check — because 1 day is within the 5-day warning window. If you want to avoid this, set the warning days for that product to `1` or `0` (disabled).

**Notification frequency:**
By default, Grocylink sends a notification on every check cycle for as long as the alert condition is active. Use the **Notification repeat** setting to limit this to once, 2×, 3×, or 5× per product and alert state.

**Per-product warning days:**
Individual warning thresholds can be set for each product directly from the Grocylink dashboard — but only while the product has stock in Grocy. Parent products without own stock entries are shown on the dashboard but cannot be configured there; set the default warning days in Settings instead.

**Disabling notifications for specific products:**
Set the warning days to `0` for any product you don't want notifications for (e.g. dried pasta, canned goods). The product will still appear in the dashboard but will never trigger a notification.

---

## Installation

### 1. Prepare data directory

```bash
mkdir -p /path/to/grocylink/data
chown 1000:1000 /path/to/grocylink/data
# Optional: hot-folder for automatic receipt import (see note below)
# mkdir -p /path/to/grocylink/receipts && chown 1000:1000 /path/to/grocylink/receipts
```

### 2. Docker Compose

`compose.yaml`:

```yaml
services:
  grocylink:
    image: c42u/grocylink:latest
    container_name: grocylink
    restart: unless-stopped
    user: ${UID}:${GID}
    cpus: "1.0"
    pids_limit: 200
    mem_limit: 2G
    memswap_limit: 3G
    oom_kill_disable: false
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    environment:
      GUNICORN_WORKERS: ${GUNICORN_WORKERS}
      TZ: ${TIMEZONE}
    volumes:
      - ${PATH_TO}/grocylink/data:/app/data
      # Optional: hot-folder for automatic PDF receipt import
      # - ${PATH_TO}/grocylink/receipts:/app/receipts
    ports:
      - "5000:5000"
```

`.env` (next to `compose.yaml`):

```
PATH_TO=/path/to
UID=1000
GID=1000
GUNICORN_WORKERS=2
TIMEZONE=Europe/Berlin
```

**Note on the `receipts` volume**: The `/app/receipts` mount is the hot-folder for the *automatic* PDF receipt scanner — useful if you want a scanner, mail server, or sync tool to drop PDFs into a directory that Grocylink picks up on its own. The path can be changed in Settings → Receipt watch folder.
PDFs uploaded through the web UI do **not** use this volume; they are stored inside the `data` volume (`/app/data/receipts/`) and are kept across container restarts without the extra mount. If you only use the web UI uploader, you can leave the `receipts` volume commented out.

### 3. Start

```bash
docker compose up -d
```

Grocylink is then accessible at `http://localhost:5000`.

### 4. Configure

1. **Grocy connection**: Enter the Grocy URL and API key under Settings
2. **Notifications**: Set up one or more notification channels under Channels
3. **CalDAV** (optional): Configure CalDAV server, credentials and calendar

---

## Reverse Proxy (HTTPS)

Grocylink serves HTTP on port 5000. For HTTPS, use an external reverse proxy.

**Caddy example:**

```caddyfile
grocylink.example.com {
    reverse_proxy http://localhost:5000
}
```

**Nginx example:**

```nginx
server {
    listen 443 ssl;
    server_name grocylink.example.com;
    ssl_certificate /certs/fullchain.pem;
    ssl_certificate_key /certs/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GUNICORN_WORKERS` | `2` | Number of Gunicorn worker processes |
| `TZ` | `Europe/Berlin` | Timezone for scheduler and logs |

---

## Persistent Data

All data is stored in `/app/data` inside the container:

| File | Description |
|---|---|
| `grocy_notify.db` | SQLite database (settings, channels, logs) |
| `.encryption_key` | Encryption key for passwords and API keys |

**Important:** The volume `/app/data` must be mounted so data survives restarts. Make sure to back up the `.encryption_key` - without it, stored credentials cannot be decrypted.

---

## Compatible CalDAV Servers

| Server | Path |
|---|---|
| Nextcloud | `/remote.php/dav` |
| Radicale | `/radicale/` |
| Baikal | `/baikal/html/dav.php` |
| iCloud | - |
| RFC 6764 | `/.well-known/caldav` |

---

## Security

- Runs as non-root user
- All Linux capabilities dropped (`cap_drop: ALL`)
- No privilege escalation (`no-new-privileges`)
- All sensitive data AES-encrypted in the database
- Resource limits for CPU, RAM and processes

---

## AI Disclosure

Grocylink is developed with the assistance of [Claude Code](https://claude.ai/code) (Claude by Anthropic), an AI coding assistant used directly in the terminal.

**How AI is used in this project:**
- **Code generation**: Modules, API routes, frontend logic, and Docker configuration are written collaboratively with the AI based on requirements defined by the developer
- **Bug analysis & fixes**: The AI assists in identifying root causes and suggesting fixes, which the developer reviews and applies
- **Documentation**: README, changelogs, and code comments are drafted with AI assistance and reviewed by the developer
- **Architecture decisions**: All design decisions — feature scope, data model, security approach — are made by the developer; the AI implements them

**What the AI does not do:**
- Make autonomous commits or deploy code
- Define requirements or product direction
- Replace code review — all generated code is read and understood by the developer before use

The software is provided "as is" without warranty. Use at your own risk.

## Links

- [GitHub](https://github.com/c42u/grocylink)
- [Docker Hub](https://hub.docker.com/r/c42u/grocylink)
- [Impressum / Legal Notice](IMPRESSUM.md)
- [Support](https://buymeacoffee.com/c42u)

---

# Grocylink <a name="deutsch"></a>

Grocylink erweitert [Grocy](https://grocy.info/) um automatische Ablaufwarnungen, Multi-Channel-Benachrichtigungen und bidirektionale CalDAV-Synchronisation.

Self-hosted, offline-fähig und vollständig unter deiner Kontrolle.

---

## Funktionen

- **Dashboard** mit Echtzeit-Übersicht über ablaufende, abgelaufene und fehlende Produkte
- **6 Benachrichtigungskanäle**: E-Mail (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- **Individuelle Warntage pro Produkt** — z.B. Milch 2 Tage, Konserven 30 Tage; auf `0` setzen deaktiviert Benachrichtigungen für dieses Produkt vollständig
- **MHD vs. Verbrauchsdatum**: Grocylink liest das `due_type`-Feld aus Grocy und kennzeichnet Benachrichtigungen entsprechend — nützlich wenn man Verbrauchsdaten (z.B. Hackfleisch) anders behandeln möchte als MHD-Angaben (z.B. Nudeln)
- **Kategorie- und Lagerort-Filter**: Benachrichtigungen auf bestimmte Grocy-Produktkategorien und/oder Lagerorte einschränken — ideal wenn nur bestimmte Bereiche (z.B. Kühlschrank) relevant sind
- **Bestand direkt aus dem Dashboard buchen**: Produkte unter Mindestbestand nachbuchen ohne Grocylink zu verlassen
- **Benachrichtigungs-Wiederholung**: Konfigurierbar wie oft Grocylink pro Produkt und Alarmzustand benachrichtigt — immer (Standard), einmalig, 2x, 3x oder 5x. Der Zähler setzt sich automatisch zurück wenn ein Produkt nachgebucht wird oder den Alarmzustand verlaesst
- **CalDAV-Synchronisation**: Grocy-Aufgaben und Haushaltsarbeiten bidirektional mit CalDAV-Clients synchronisieren (2Do, Apple Reminders, Tasks.org u.a.)
- **Neue Aufgaben** aus dem CalDAV-Client werden automatisch in Grocy angelegt
- **Konfigurierbares Prüfintervall** mit automatischem Scheduler
- **Test-Funktion** für jeden Benachrichtigungskanal
- **Vollständiges Benachrichtigungsprotokoll** mit Filter und Sortierung
- **Verschlüsselte Speicherung** aller Passwörter und API-Keys (Fernet/AES)
- **Dark/Light Mode** (automatisch + manueller Toggle)
- **Mehrsprachig**: Deutsch und Englisch
- **Non-Root Container** mit minimalen Berechtigungen

---

## Wie Benachrichtigungen funktionieren

Grocylink prüft den Grocy-Bestand in einem konfigurierbaren Intervall (Standard: alle 6 Stunden). Erfullt ein Produkt eine Alarmbedingung, wird eine Benachrichtigung an alle aktivierten Kanäle gesendet.

**Wann wird eine Benachrichtigung ausgelöst?**

| Bedingung | Ausloser |
|---|---|
| Ablaufend | MHD oder Verbrauchsdatum liegt innerhalb der konfigurierten Warntage |
| Abgelaufen | MHD oder Verbrauchsdatum ist überschritten |
| Unter Mindestbestand | Aktueller Bestand liegt unter dem in Grocy definierten Minimum |

**Beispiel — frisches Hackfleisch mit 1 Tag Verbrauchsdatum:**
Mit dem Standard-Warnwert von 5 Tagen wird Hackfleisch, das heute mit einem Verbrauchsdatum von morgen gekauft wird, beim nächsten Check sofort eine Benachrichtigung auslösen — weil 1 Tag innerhalb des 5-Tage-Fensters liegt. Um das zu vermeiden, Warntage für dieses Produkt auf `1` oder `0` (deaktiviert) setzen.

**Benachrichtigungshäufigkeit:**
Standardmäßig sendet Grocylink bei jedem Check eine Benachrichtigung solange die Alarmbedingung aktiv ist. Mit der Einstellung **Benachrichtigungs-Wiederholung** lässt sich das auf einmalig, 2x, 3x oder 5x pro Produkt und Alarmzustand begrenzen.

**Warntage pro Produkt:**
Individuelle Schwellenwerte können für jedes Produkt direkt im Grocylink-Dashboard gesetzt werden — aber nur solange das Produkt Bestand in Grocy hat. Produkte ohne eigenen Bestand werden im Dashboard angezeigt, können dort aber nicht konfiguriert werden; in diesem Fall den globalen Standard unter Einstellungen verwenden.

**Benachrichtigungen für bestimmte Produkte deaktivieren:**
Warntage auf `0` setzen für Produkte, für die keine Benachrichtigungen gewünscht sind (z.B. Nudeln, Konserven). Das Produkt erscheint weiterhin im Dashboard, löst aber keine Benachrichtigungen aus.

---

## Installation

### 1. Datenverzeichnis vorbereiten

```bash
mkdir -p /pfad/zu/grocylink/data
chown 1000:1000 /pfad/zu/grocylink/data
# Optional: Hot-Folder für automatischen Kassenbon-Import (siehe Hinweis unten)
# mkdir -p /pfad/zu/grocylink/receipts && chown 1000:1000 /pfad/zu/grocylink/receipts
```

### 2. Docker Compose

`compose.yaml`:

```yaml
services:
  grocylink:
    image: c42u/grocylink:latest
    container_name: grocylink
    restart: unless-stopped
    user: ${UID}:${GID}
    cpus: "1.0"
    pids_limit: 200
    mem_limit: 2G
    memswap_limit: 3G
    oom_kill_disable: false
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    environment:
      GUNICORN_WORKERS: ${GUNICORN_WORKERS}
      TZ: ${TIMEZONE}
    volumes:
      - ${PATH_TO}/grocylink/data:/app/data
      # Optional: Hot-Folder für automatischen Kassenbon-PDF-Import
      # - ${PATH_TO}/grocylink/receipts:/app/receipts
    ports:
      - "5000:5000"
```

`.env` (neben `compose.yaml`):

```
PATH_TO=/pfad/zu
UID=1000
GID=1000
GUNICORN_WORKERS=2
TIMEZONE=Europe/Berlin
```

**Hinweis zum `receipts`-Volume**: Das Mount `/app/receipts` ist der Hot-Folder für den *automatischen* Kassenbon-Scanner — nützlich, wenn ein Scanner, Mailserver oder Sync-Tool PDFs in ein Verzeichnis ablegen soll, das Grocylink eigenständig einliest. Der Pfad ist in Einstellungen → Kassenbon-Watch-Folder anpassbar.
Über die Web-UI hochgeladene PDFs nutzen dieses Volume **nicht**; sie werden im `data`-Volume gespeichert (`/app/data/receipts/`) und bleiben auch ohne zusätzliches Mount über Container-Neustarts erhalten. Wer ausschliesslich die Web-UI nutzt, kann das `receipts`-Volume auskommentiert lassen.

### 3. Starten

```bash
docker compose up -d
```

Grocylink ist dann erreichbar unter `http://localhost:5000`.

### 4. Einrichten

1. **Grocy-Verbindung**: Unter Einstellungen die Grocy-URL und den API-Key eintragen
2. **Benachrichtigungen**: Unter Kanäle einen oder mehrere Benachrichtigungskanäle einrichten
3. **CalDAV** (optional): CalDAV-Server, Zugangsdaten und Kalender konfigurieren

---

## Reverse Proxy (HTTPS)

Grocylink stellt HTTP auf Port 5000 bereit. Für HTTPS einen externen Reverse Proxy vorschalten.

**Caddy-Beispiel:**

```caddyfile
grocylink.example.com {
    reverse_proxy http://localhost:5000
}
```

**Nginx-Beispiel:**

```nginx
server {
    listen 443 ssl;
    server_name grocylink.example.com;
    ssl_certificate /certs/fullchain.pem;
    ssl_certificate_key /certs/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `GUNICORN_WORKERS` | `2` | Anzahl Gunicorn Worker-Prozesse |
| `TZ` | `Europe/Berlin` | Zeitzone für Scheduler und Logs |

---

## Persistente Daten

Alle Daten werden in `/app/data` im Container gespeichert:

| Datei | Beschreibung |
|---|---|
| `grocy_notify.db` | SQLite-Datenbank (Einstellungen, Kanäle, Logs) |
| `.encryption_key` | Verschlüsselungsschlüssel für Passwörter und API-Keys |

**Wichtig:** Das Volume `/app/data` muss gemountet sein, damit Daten einen Neustart überleben. Den `.encryption_key` unbedingt sichern - ohne ihn können gespeicherte Zugangsdaten nicht mehr entschlüsselt werden.

---

## Kompatible CalDAV-Server

| Server | Pfad |
|---|---|
| Nextcloud | `/remote.php/dav` |
| Radicale | `/radicale/` |
| Baikal | `/baikal/html/dav.php` |
| iCloud | - |
| RFC 6764 | `/.well-known/caldav` |

---

## Sicherheit

- Läuft als Non-Root User
- Alle Linux Capabilities entfernt (`cap_drop: ALL`)
- Keine Privilege Escalation (`no-new-privileges`)
- Alle sensiblen Daten AES-verschlüsselt in der Datenbank
- Ressourcenlimits für CPU, RAM und Prozesse

---

## KI-Transparenz

Grocylink wird unter Einsatz von [Claude Code](https://claude.ai/code) (Claude von Anthropic), einem KI-Coding-Assistenten direkt im Terminal, entwickelt.

**Wie KI in diesem Projekt eingesetzt wird:**
- **Code-Generierung**: Module, API-Routen, Frontend-Logik und Docker-Konfiguration werden kollaborativ mit der KI auf Basis vom Entwickler definierter Anforderungen erstellt
- **Fehleranalyse & Behebung**: Die KI hilft bei der Ursachenanalyse und schlägt Lösungen vor, die der Entwickler prüft und umsetzt
- **Dokumentation**: README, Changelogs und Code-Kommentare werden mit KI-Unterstützung verfasst und vom Entwickler geprüft
- **Architekturentscheidungen**: Alle Designentscheidungen — Feature-Umfang, Datenmodell, Sicherheitsansatz — trifft der Entwickler; die KI setzt sie um

**Was die KI nicht tut:**
- Eigenständig committen oder Code deployen
- Anforderungen oder Produktrichtung bestimmen
- Code-Review ersetzen — jeder generierte Code wird vom Entwickler gelesen und verstanden, bevor er eingesetzt wird

Die Software wird "wie besehen" ohne jegliche Gewährleistung bereitgestellt. Nutzung auf eigene Gefahr.

## Links

- [GitHub](https://github.com/c42u/grocylink)
- [Docker Hub](https://hub.docker.com/r/c42u/grocylink)
- [Impressum](IMPRESSUM.md)
- [Unterstützung](https://buymeacoffee.com/c42u)
