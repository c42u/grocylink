# Grocylink

Grocylink erweitert [Grocy](https://grocy.info/) um automatische Ablaufwarnungen, Multi-Channel-Benachrichtigungen, bidirektionale CalDAV-Synchronisation und einen Kassenbon-Scanner.

Self-hosted, offline-faehig und vollstaendig unter deiner Kontrolle.

---

## Funktionen

- **Dashboard** mit Echtzeit-Uebersicht ueber ablaufende, abgelaufene und fehlende Produkte
- **6 Benachrichtigungskanaele**: E-Mail (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- **Individuelle Warntage** pro Produkt (z.B. Milch 2 Tage, Konserven 30 Tage)
- **CalDAV-Synchronisation**: Grocy-Aufgaben und Haushaltsarbeiten bidirektional mit CalDAV-Clients synchronisieren (2Do, Apple Reminders, Tasks.org u.a.)
- **Neue Aufgaben** aus dem CalDAV-Client werden automatisch in Grocy angelegt
- **Kassenbon-Scanner**: PDF-Kassenbons hochladen oder per Ordnerueberwachung einlesen, Produkte per OCR extrahieren und als Bestand in Grocy buchen
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
mkdir -p /pfad/zu/grocylink/data /pfad/zu/grocylink/receipts
chown 1000:1000 /pfad/zu/grocylink/data /pfad/zu/grocylink/receipts
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
      - /pfad/zu/grocylink/receipts:/app/receipts
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
4. **Kassenbons** (optional): Ordnerueberwachung aktivieren und Schwellwerte anpassen

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

- [GitHub](https://github.com/c42u)
- [Unterstuetzung](https://donate.stripe.com/cNi6oH4OX6KO8i1dpa1Nu00)
