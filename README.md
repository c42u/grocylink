# Table of contents / Inhaltsverzeichnis
1. [Grocylink - english](#english)
2. [Grocylink - deutsch](#deutsch)

---

# Grocylink <a name="english"></a>

Grocylink extends [Grocy](https://grocy.info/) with automatic expiry alerts, multi-channel notifications and bidirectional CalDAV synchronization.

Self-hosted, offline-capable and fully under your control.

---

## Features

- **Dashboard** with real-time overview of expiring, expired and missing products
- **6 notification channels**: Email (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- **Individual warning days** per product (e.g. milk 2 days, canned goods 30 days)
- **CalDAV synchronization**: Sync Grocy tasks and chores bidirectionally with CalDAV clients (2Do, Apple Reminders, Tasks.org and more)
- **New tasks** created in CalDAV clients are automatically added to Grocy
- **Automatic scheduler** with configurable interval
- **Test function** for each notification channel
- **Full notification log** with filtering and sorting
- **Encrypted storage** of all passwords and API keys (Fernet/AES)
- **Dark/Light mode** (automatic + manual toggle)
- **Multilingual**: German and English
- **Non-root container** with minimal privileges

---

## Installation

### 1. Prepare data directory

```bash
mkdir -p /path/to/grocylink/data
chown 1000:1000 /path/to/grocylink/data
```

### 2. Docker Compose

```yaml
services:
  grocylink:
    image: c42u/grocylink:latest
    container_name: grocylink
    restart: unless-stopped
    user: "1000:1000"
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
      GUNICORN_WORKERS: 2
      TZ: Europe/Berlin
    volumes:
      - /path/to/grocylink/data:/app/data
    ports:
      - "5000:5000"
```

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

## Links

- [GitHub](https://github.com/c42u/grocylink)
- [Docker Hub](https://hub.docker.com/r/c42u/grocylink)
- [Support](https://donate.stripe.com/cNi6oH4OX6KO8i1dpa1Nu00)

---

# Grocylink <a name="deutsch"></a>

Grocylink erweitert [Grocy](https://grocy.info/) um automatische Ablaufwarnungen, Multi-Channel-Benachrichtigungen und bidirektionale CalDAV-Synchronisation.

Self-hosted, offline-faehig und vollstaendig unter deiner Kontrolle.

---

## Funktionen

- **Dashboard** mit Echtzeit-Uebersicht ueber ablaufende, abgelaufene und fehlende Produkte
- **6 Benachrichtigungskanaele**: E-Mail (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- **Individuelle Warntage** pro Produkt (z.B. Milch 2 Tage, Konserven 30 Tage)
- **CalDAV-Synchronisation**: Grocy-Aufgaben und Haushaltsarbeiten bidirektional mit CalDAV-Clients synchronisieren (2Do, Apple Reminders, Tasks.org u.a.)
- **Neue Aufgaben** aus dem CalDAV-Client werden automatisch in Grocy angelegt
- **Automatischer Scheduler** mit konfigurierbarem Intervall
- **Test-Funktion** fuer jeden Benachrichtigungskanal
- **Vollstaendiges Benachrichtigungsprotokoll** mit Filter und Sortierung
- **Verschluesselte Speicherung** aller Passwoerter und API-Keys (Fernet/AES)
- **Dark/Light Mode** (automatisch + manueller Toggle)
- **Mehrsprachig**: Deutsch und Englisch
- **Non-Root Container** mit minimalen Berechtigungen

---

## Installation

### 1. Datenverzeichnis vorbereiten

```bash
mkdir -p /pfad/zu/grocylink/data
chown 1000:1000 /pfad/zu/grocylink/data
```

### 2. Docker Compose

```yaml
services:
  grocylink:
    image: c42u/grocylink:latest
    container_name: grocylink
    restart: unless-stopped
    user: "1000:1000"
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
      GUNICORN_WORKERS: 2
      TZ: Europe/Berlin
    volumes:
      - /pfad/zu/grocylink/data:/app/data
    ports:
      - "5000:5000"
```

### 3. Starten

```bash
docker compose up -d
```

Grocylink ist dann erreichbar unter `http://localhost:5000`.

### 4. Einrichten

1. **Grocy-Verbindung**: Unter Einstellungen die Grocy-URL und den API-Key eintragen
2. **Benachrichtigungen**: Unter Kanaele einen oder mehrere Benachrichtigungskanaele einrichten
3. **CalDAV** (optional): CalDAV-Server, Zugangsdaten und Kalender konfigurieren

---

## Reverse Proxy (HTTPS)

Grocylink stellt HTTP auf Port 5000 bereit. Fuer HTTPS einen externen Reverse Proxy vorschalten.

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
| `TZ` | `Europe/Berlin` | Zeitzone fuer Scheduler und Logs |

---

## Persistente Daten

Alle Daten werden in `/app/data` im Container gespeichert:

| Datei | Beschreibung |
|---|---|
| `grocy_notify.db` | SQLite-Datenbank (Einstellungen, Kanaele, Logs) |
| `.encryption_key` | Verschluesselungsschluessel fuer Passwoerter und API-Keys |

**Wichtig:** Das Volume `/app/data` muss gemountet sein, damit Daten einen Neustart ueberleben. Den `.encryption_key` unbedingt sichern - ohne ihn koennen gespeicherte Zugangsdaten nicht mehr entschluesselt werden.

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

- Laeuft als Non-Root User
- Alle Linux Capabilities entfernt (`cap_drop: ALL`)
- Keine Privilege Escalation (`no-new-privileges`)
- Alle sensiblen Daten AES-verschluesselt in der Datenbank
- Ressourcenlimits fuer CPU, RAM und Prozesse

---

## Links

- [GitHub](https://github.com/c42u/grocylink)
- [Docker Hub](https://hub.docker.com/r/c42u/grocylink)
- [Unterstuetzung](https://donate.stripe.com/cNi6oH4OX6KO8i1dpa1Nu00)
