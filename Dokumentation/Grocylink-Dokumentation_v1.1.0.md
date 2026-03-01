# Grocylink - Dokumentation

Grocylink ist eine Webapplikation, die den Lagerbestand einer [Grocy](https://grocy.info/)-Instanz ueberwacht und automatisch Benachrichtigungen versendet, wenn Produkte bald ablaufen, bereits abgelaufen sind oder der Mindestbestand unterschritten wird. Zusaetzlich synchronisiert Grocylink Tasks und Chores bidirektional mit einem CalDAV-Server.

## Inhaltsverzeichnis

- [Features](#features)
- [Architektur](#architektur)
- [Installation](#installation)
  - [Docker-Netzwerk einrichten](#docker-netzwerk-einrichten)
  - [Docker (empfohlen)](#docker-empfohlen)
  - [Komodo](#komodo)
  - [Manuell](#manuell)
- [Konfiguration](#konfiguration)
  - [Grocy-Verbindung](#grocy-verbindung)
  - [Benachrichtigungskanaele](#benachrichtigungskanaele)
  - [Individuelle Warntage](#individuelle-warntage)
  - [CalDAV-Synchronisation](#caldav-synchronisation)
- [Reverse Proxy / HTTPS](#reverse-proxy--https)
- [Sicherheit](#sicherheit)
- [API-Referenz](#api-referenz)
- [Fehlerbehebung](#fehlerbehebung)

---

## Features

- **Dashboard** mit Echtzeit-Uebersicht ueber ablaufende, abgelaufene und fehlende Produkte
- **6 Benachrichtigungskanaele**: Email (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- **Individuelle Warntage** pro Produkt konfigurierbar (z.B. Milch 2 Tage, Konserven 30 Tage)
- **Automatischer Scheduler** mit konfigurierbarem Intervall (Standard: 6 Stunden)
- **Manueller Check** per Button-Klick
- **Test-Funktion** fuer jeden Notification-Kanal
- **Benachrichtigungsprotokoll** mit vollstaendiger Historie
- **Dark/Light Mode** (automatisch via System-Einstellung + manueller Toggle)
- **Responsives Design** fuer Desktop und Mobilgeraete
- **Verschluesselte Speicherung** aller Passwoerter und API-Keys
- **CalDAV-Synchronisation**: Bidirektionale Sync von Grocy Tasks und Chores als VTODO-Eintraege
- **Mehrsprachig**: Deutsch und Englisch
- **Non-Root Container**: Laeuft ohne Root-Rechte mit minimalen Berechtigungen

---

## Architektur

```
                                                    ┌───────────┐
┌─────────────┐     HTTPS      ┌──────────────┐    │  Flask +  │
│   Browser   │ ◄────────────► │   Reverse    │ ◄─►│  Gunicorn │
│             │                │   Proxy      │    │  :5000    │
└─────────────┘                └──────────────┘    └─────┬─────┘
                               (extern, z.B.             │
                                Caddy, Traefik,          │
                                Nginx)          ┌────────┼────────┐
                                                │        │        │        │
                                           ┌────▼───┐┌───▼───┐┌──▼─────┐┌─▼───────┐
                                           │ SQLite ││ Grocy ││Notifier││ CalDAV  │
                                           │  (DB)  ││  API  ││ Email, ││ Server  │
                                           └────────┘└───────┘│Pushover││(VTODO)  │
                                                              │Telegram│└─────────┘
                                                              │ Slack, │
                                                              │Discord,│
                                                              │ Gotify │
                                                              └────────┘
```

### Projektstruktur

```
grocy/
├── compose.yaml        # Docker Compose
├── app.py              # Flask-Server, API-Routen, Scheduler-Init
├── database.py         # SQLite-Zugriff mit Verschluesselung
├── grocy_client.py     # Grocy REST-API Client
├── notifiers.py        # Notification-Provider (6 Stueck)
├── scheduler.py        # Automatische Check-Logik
├── caldav_sync.py      # CalDAV-Synchronisation (VTODO bidirektional)
├── crypto.py           # Fernet-Verschluesselung fuer sensible Daten
├── requirements.txt    # Python-Dependencies
├── .dockerignore
├── templates/
│   └── index.html      # Single-Page Frontend
├── static/
│   ├── style.css       # Design mit Dark/Light Mode
│   ├── i18n.js         # Internationalisierung (DE/EN)
│   └── app.js          # Frontend-Logik
├── docker/
│   ├── Dockerfile
│   ├── .env            # Umgebungsvariablen (IP, Pfade, Timezone)
│   └── entrypoint.sh   # Gunicorn Start
├── data/               # SQLite DB + Encryption Key (automatisch erstellt)
└── doku/
    └── README.md       # Diese Dokumentation
```

---

## Installation

### Docker-Netzwerk einrichten

Grocylink verwendet ein externes Docker-Netzwerk mit festen IP-Adressen. Das Netzwerk muss **einmalig** vor dem ersten Start erstellt werden.

#### Macvlan-Netzwerk (empfohlen fuer dedizierte IPs)

Ein **Macvlan-Netzwerk** gibt jedem Container eine eigene IP-Adresse im physischen Netzwerk. Die Container sind damit direkt ueber das LAN erreichbar - wie ein eigenstaendiger Server.

```bash
docker network create -d macvlan \
  --subnet=192.168.0.0/16 \
  --gateway=192.168.255.254 \
  -o parent=ens19 \
  DockerNetwork
```

| Parameter | Beschreibung |
|---|---|
| `-d macvlan` | Treiber: Macvlan - Container erhalten eigene MAC-Adressen im physischen Netzwerk |
| `--subnet=192.168.0.0/16` | Subnetz des physischen Netzwerks. Muss zum bestehenden LAN passen. `/16` erlaubt Adressen von `192.168.0.1` bis `192.168.255.254` |
| `--gateway=192.168.255.254` | Standard-Gateway (Router) des Netzwerks. In den meisten Heimnetzwerken die Router-IP |
| `-o parent=ens19` | Physisches Netzwerk-Interface des Hosts. Mit `ip link show` pruefen (haeufig: `eth0`, `ens18`, `ens19`, `enp0s3`) |
| `DockerNetwork` | Name des Netzwerks - muss mit dem Namen in `compose.yaml` uebereinstimmen |

> **Wichtig:** Das Subnetz und Gateway muessen zum bestehenden Netzwerk passen. Beispiele:
> - Heimnetzwerk mit Fritz!Box: `--subnet=192.168.178.0/24 --gateway=192.168.178.1`
> - Proxmox/Server-Umgebung: Subnetz und Gateway je nach VLAN-Konfiguration anpassen
> - Das physische Interface (`-o parent=...`) mit `ip link show` oder `ip addr` ermitteln

> **Macvlan-Einschraenkung:** Der Docker-Host selbst kann Container im Macvlan-Netzwerk **nicht direkt** erreichen (und umgekehrt). Falls der Host auf den Container zugreifen muss, eine Macvlan-Subinterface-Bridge einrichten oder einen separaten Proxy verwenden.

#### Bridge-Netzwerk (Alternative)

Falls kein Macvlan gewuenscht ist, kann auch ein normales Bridge-Netzwerk mit festem Subnetz verwendet werden:

```bash
docker network create \
  --subnet=172.30.45.0/24 \
  --gateway=172.30.45.1 \
  DockerNetwork
```

Bei einem Bridge-Netzwerk sind Container nur ueber Port-Mappings (`ports:`) von aussen erreichbar.

#### Netzwerk pruefen

```bash
# Netzwerk anzeigen
docker network inspect DockerNetwork

# Alle Netzwerke auflisten
docker network ls
```

### Docker (empfohlen)

#### Voraussetzungen

- Docker und Docker Compose installiert
- Docker-Netzwerk `DockerNetwork` erstellt (siehe oben)
- Quellcode auf dem Server vorhanden
- **Externer Reverse Proxy** fuer HTTPS (z.B. Caddy, Traefik, Nginx)

#### Image bauen und starten

```bash
cd /pfad/zu/grocylink

# Image bauen
docker build --no-cache --network host -t grocylink:latest -f docker/Dockerfile .

# Container starten
docker compose up -d

# Logs anzeigen
docker compose logs -f
```

Die Anwendung ist dann erreichbar unter `http://<GROCYLINK_IP>:5000`. Fuer HTTPS einen Reverse Proxy vorschalten (siehe [Reverse Proxy / HTTPS](#reverse-proxy--https)).

#### Umgebungsvariablen (.env)

Die Datei `docker/.env` enthaelt alle konfigurierbaren Umgebungsvariablen:

```env
GUNICORN_WORKERS=2
TIMEZONE=Europe/Berlin
GROCYLINK_IP=172.30.45.26
PATH_TO=/var/container/ds06
UID=1000
GID=1000
```

| Variable | Standard | Beschreibung |
|---|---|---|
| `GUNICORN_WORKERS` | `2` | Anzahl der Gunicorn Worker-Prozesse |
| `TIMEZONE` | `Europe/Berlin` | Zeitzone fuer Scheduler und Logs |
| `GROCYLINK_IP` | `172.30.45.26` | Feste IP-Adresse im Docker-Netzwerk |
| `PATH_TO` | `/var/container/ds06` | Basispfad fuer persistente Daten (Bind Mounts) |
| `UID` | `1000` | User-ID unter der der Container laeuft |
| `GID` | `1000` | Group-ID unter der der Container laeuft |

Die Datenverzeichnisse werden automatisch unter `${PATH_TO}/grocylink/` angelegt:
- `${PATH_TO}/grocylink/data/` - Datenbank und Encryption Key

#### Container-Sicherheit

Der Container laeuft mit minimalen Berechtigungen:

```yaml
user: ${UID}:${GID}           # Non-Root User
cap_drop:
  - ALL                        # Alle Linux Capabilities entfernt
security_opt:
  - no-new-privileges:true     # Keine Privilege Escalation
cpus: "1.0"                    # Max 1 CPU-Kern
mem_limit: 2G                  # Max 2 GB RAM
pids_limit: 200                # Max 200 Prozesse
```

> **Wichtig:** Das Datenverzeichnis `${PATH_TO}/grocylink/data/` muss fuer den konfigurierten User (UID/GID) schreibbar sein:
> ```bash
> mkdir -p /var/container/ds06/grocylink/data
> chown 1000:1000 /var/container/ds06/grocylink/data
> ```

### Komodo

[Komodo](https://komo.do/) ist eine Self-Hosted Plattform zur Verwaltung von Docker-Containern und Deployments. Grocylink kann als **Stack** in Komodo eingebunden werden - ohne Git, rein ueber Dateien auf dem Host.

**Voraussetzungen:**
- Komodo Core laeuft und ist erreichbar
- Komodo Periphery ist auf dem Zielserver installiert und verbunden
- Der Zielserver hat Docker und Docker Compose installiert

> **Wichtiger Hinweis:** Komodo kann standardmaessig keine lokalen Docker-Images bauen. Daher wird das Image **vorab manuell** auf dem Server gebaut und in der `compose.yaml` als fertiges Image referenziert (`image:` statt `build:`). Komodo startet dann nur den Container.

#### Schritt 1: Dateien auf den Server kopieren

Zuerst muss der komplette Grocylink-Quellcode auf den Zielserver uebertragen werden. Das Zielverzeichnis kann frei gewaehlt werden, z.B. `/opt/grocylink`.

**Per SCP (von lokalem Rechner):**

```bash
scp -r /pfad/zu/grocy/ benutzer@server:/opt/grocylink
```

**Per rsync (effizienter bei Updates):**

```bash
rsync -avz --exclude='data/' /pfad/zu/grocy/ benutzer@server:/opt/grocylink/
```

**Oder manuell per SFTP/Dateimanager** - z.B. mit FileZilla, WinSCP oder dem Dateimanager des Server-Panels.

Nach dem Kopieren sollte die Verzeichnisstruktur auf dem Server so aussehen:

```
/opt/grocylink/
├── compose.yaml          # Compose fuer lokales docker compose
├── app.py
├── database.py
├── grocy_client.py
├── caldav_sync.py
├── notifiers.py
├── scheduler.py
├── crypto.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── i18n.js           # Internationalisierung (DE/EN)
│   ├── app.js
│   └── style.css
└── docker/
    ├── Dockerfile
    ├── .env              # Umgebungsvariablen
    └── entrypoint.sh
```

#### Schritt 2: Docker-Image manuell bauen

Das Image muss auf dem Zielserver manuell gebaut werden, **bevor** Komodo den Stack deployed:

```bash
cd /opt/grocylink
docker build --no-cache --network host -t grocylink:latest -f docker/Dockerfile .
```

| Flag | Erklaerung |
|---|---|
| `--no-cache` | Erzwingt einen vollstaendigen Rebuild ohne gecachte Layer. Wichtig nach Code-Aenderungen. |
| `--network host` | Verwendet das Host-Netzwerk waehrend des Builds. Behebt DNS-Probleme, die in manchen Docker-Umgebungen auftreten (z.B. `deb.debian.org` nicht aufloesbar). |
| `-t grocylink:latest` | Taggt das Image als `grocylink:latest` - dieser Name muss mit der `compose.yaml` uebereinstimmen. |
| `-f docker/Dockerfile .` | Verwendet das Dockerfile aus dem `docker/`-Unterordner mit dem aktuellen Verzeichnis als Build-Context. |

> **Haeufiges Problem:** Falls der Build mit DNS-Fehlern wie `Temporary failure resolving 'deb.debian.org'` fehlschlaegt, ist `--network host` die Loesung. Docker verwendet sonst ein eigenes Netzwerk fuer den Build, das je nach Server-Konfiguration keine DNS-Aufloesung hat.

#### Schritt 3: Stack in Komodo anlegen

1. In Komodo auf **Stacks** > **+ New Stack** klicken
2. **Name**: `grocylink`
3. **Server** auswaehlen (z.B. `vSrv-Docker01`)

#### Schritt 4: Compose File in Komodo eintragen

Unter **Compose File** in Komodo den folgenden Inhalt eintragen:

```yaml
services:
  grocylink:
    image: grocylink:latest
    pull_policy: never
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
    ports:
      - "5000:5000"
    networks:
      DockerNetwork:
        ipv4_address: ${GROCYLINK_IP}

networks:
  DockerNetwork:
    external: true
```

| Feld | Erklaerung |
|---|---|
| `image: grocylink:latest` | Referenziert das lokal gebaute Image (aus Schritt 2). |
| `pull_policy: never` | **Wichtig!** Verhindert, dass Docker/Komodo versucht, das Image von Docker Hub zu pullen. Ohne dieses Flag schlaegt der Deploy mit `pull access denied` fehl. |
| `user: ${UID}:${GID}` | Container laeuft als Non-Root User. |
| `cap_drop: ALL` | Alle Linux Capabilities werden entfernt. |
| `security_opt: no-new-privileges` | Verhindert Privilege Escalation. |
| `volumes: ${PATH_TO}/...:/app/data` | Bind Mount fuer Datenbank und Encryption Key. |
| `ports: "5000:5000"` | Gunicorn Port. Fuer HTTPS einen Reverse Proxy vorschalten. |
| `networks: DockerNetwork` | Externes Docker-Netzwerk mit fester IP (muss vorher erstellt werden, siehe [Docker-Netzwerk einrichten](#docker-netzwerk-einrichten)). |

#### Schritt 5: Environment konfigurieren

Unter **Environment** in Komodo die Umgebungsvariablen setzen:

```env
GUNICORN_WORKERS=2
TIMEZONE=Europe/Berlin
GROCYLINK_IP=172.30.45.26
PATH_TO=/var/container/ds06
UID=1000
GID=1000
```

| Variable | Standard | Beschreibung |
|---|---|---|
| `GUNICORN_WORKERS` | `2` | Anzahl Gunicorn Worker-Prozesse |
| `TIMEZONE` | `Europe/Berlin` | Zeitzone fuer Scheduler und Logs |
| `GROCYLINK_IP` | `172.30.45.26` | Feste IP-Adresse im Docker-Netzwerk. Muss eine freie Adresse im konfigurierten Subnetz sein. |
| `PATH_TO` | `/var/container/ds06` | Basispfad fuer persistente Daten auf dem Host. |
| `UID` | `1000` | User-ID unter der der Container laeuft |
| `GID` | `1000` | Group-ID unter der der Container laeuft |

> **Wichtig:** Die IP-Adresse (`GROCYLINK_IP`) muss im Subnetz des Docker-Netzwerks liegen und darf nicht von einem anderen Container oder Geraet belegt sein.

> **Wichtig:** Das Datenverzeichnis muss fuer den konfigurierten User schreibbar sein:
> ```bash
> mkdir -p ${PATH_TO}/grocylink/data
> chown ${UID}:${GID} ${PATH_TO}/grocylink/data
> ```

#### Schritt 6: Deploy

1. In Komodo auf **Deploy** klicken
2. Komodo fuehrt `docker compose -f compose.yaml up -d` im Run Directory aus
3. Der Container startet mit dem lokal gebauten Image `grocylink:latest`

#### Nach dem Deployment

- Grocylink ist erreichbar unter `http://<GROCYLINK_IP>:5000` bzw. ueber den vorgeschalteten Reverse Proxy
- In Komodo unter **Stacks** > **grocylink** sind Logs, Container-Status und Ressourcenverbrauch sichtbar
- **Daten** liegen persistent unter `${PATH_TO}/grocylink/data/` auf dem Host

#### Betrieb hinter einem Reverse Proxy

Grocylink stellt nur HTTP auf Port 5000 bereit. Fuer HTTPS wird ein externer Reverse Proxy empfohlen. Beispiel fuer eine Caddy-Konfiguration:

```caddyfile
grocylink.example.com {
    tls /certs/fullchain.pem /certs/key.pem
    reverse_proxy http://172.30.45.26:5000
}
```

> **Wichtig:** Beim TLS-Zertifikat immer die **fullchain.pem** (Leaf + Intermediate) verwenden, nicht nur die cert.pem. Details dazu im Abschnitt [Reverse Proxy / HTTPS](#reverse-proxy--https).

#### Updates durchfuehren

Bei Code-Aenderungen muessen Image und Container aktualisiert werden:

```bash
# 1. Neue Dateien auf den Server kopieren
rsync -avz --exclude='data/' /pfad/zu/grocy/ benutzer@server:/opt/grocylink/

# 2. Image neu bauen (auf dem Server)
cd /opt/grocylink
docker build --no-cache --network host -t grocylink:latest -f docker/Dockerfile .

# 3. In Komodo: Stacks > grocylink > Redeploy
```

> **Tipp:** Das `data/`-Verzeichnis beim Kopieren ausschliessen (`--exclude='data/'`), damit die Datenbank und der Encryption Key nicht ueberschrieben werden. Diese liegen im Docker-Volume und sind vom Quellcode getrennt.

#### Monitoring in Komodo

Nach dem Deployment zeigt Komodo:
- **Container-Status**: Running/Stopped mit Uptime
- **Logs**: Echtzeit-Logs von Gunicorn
- **Ressourcen**: CPU- und RAM-Verbrauch des Containers
- **Actions**: Start, Stop, Restart, Redeploy direkt aus der UI

### Manuell

**Voraussetzungen:** Python 3.10+

```bash
cd /opt/claude/grocy

# Dependencies installieren
pip install -r requirements.txt

# App starten (Entwicklungsmodus)
python3 app.py
```

Die App laeuft dann auf `http://localhost:5000`.

Fuer HTTPS im manuellen Betrieb einen Reverse Proxy (z.B. Caddy, Traefik) vorschalten.

---

## Konfiguration

### Grocy-Verbindung

1. Oeffne die Webapplikation im Browser
2. Navigiere zu **Einstellungen**
3. Trage die **Grocy URL** ein (z.B. `https://grocy.example.com`)
4. Trage den **API-Key** ein (in Grocy unter Einstellungen > API-Keys zu finden)
5. Klicke auf **Verbindung testen**
6. Speichere die Einstellungen

### Benachrichtigungskanaele

Navigiere zu **Kanaele** und klicke auf **+ Kanal hinzufuegen**.

#### Email (SMTP)

| Feld | Beispiel | Beschreibung |
|---|---|---|
| SMTP Host | `smtp.gmail.com` | SMTP-Server |
| SMTP Port | `587` | Port (587 fuer STARTTLS) |
| Benutzername | `user@gmail.com` | Login |
| Passwort | `app-passwort` | Passwort/App-Passwort |
| Absender-Email | `user@gmail.com` | Von-Adresse |
| Empfaenger-Email | `notify@example.com` | Ziel-Adresse |
| TLS verwenden | `ja` | STARTTLS aktivieren |

**Hinweis Gmail:** Es muss ein [App-Passwort](https://myaccount.google.com/apppasswords) verwendet werden.

#### Pushover

| Feld | Beschreibung |
|---|---|
| API Token | App-Token von pushover.net |
| User Key | User/Group Key |
| Prioritaet | -2 (leise) bis 2 (Notfall) |

#### Telegram

| Feld | Beschreibung |
|---|---|
| Bot Token | Token vom BotFather |
| Chat ID | Ziel-Chat (User-ID oder Gruppen-ID) |

**Schritt-fuer-Schritt Einrichtung:**

1. **Bot erstellen**: In Telegram den [BotFather](https://t.me/BotFather) oeffnen und `/newbot` senden
2. Einen **Namen** und einen **Benutzernamen** fuer den Bot vergeben (Benutzername muss auf `bot` enden, z.B. `MeinGrocyBot`)
3. Der BotFather gibt einen **HTTP API Token** zurueck im Format:
   ```
   1234567890:AABBccDDeeFFggHHiiJJkkLLmmNNooPPqq
   ```
   Diesen Token in Grocylink unter **Bot Token** eintragen.

4. **Chat ID ermitteln:**
   - Den eigenen Bot in Telegram oeffnen (nach dem Benutzernamen suchen)
   - Auf **Start** klicken oder eine beliebige Nachricht senden (z.B. "Hallo")
   - Folgende URL im Browser aufrufen (Token einsetzen):
     ```
     https://api.telegram.org/bot<DEIN_KOMPLETTER_TOKEN>/getUpdates
     ```
     Der Token ist der **gesamte String** inklusive der Zahl, dem Doppelpunkt und dem Buchstabenteil.
   - In der JSON-Antwort die Chat ID ablesen:
     ```json
     {
       "ok": true,
       "result": [{
         "message": {
           "chat": {
             "id": 1234567890,
             "first_name": "Max",
             "type": "private"
           }
         }
       }]
     }
     ```
   - Die Zahl hinter `"id"` (z.B. `1234567890`) ist die **Chat ID** - diese in Grocylink eintragen.

5. In Grocylink auf **Test** klicken - es sollte eine Testnachricht im Telegram-Chat erscheinen.

> **Leere Antwort (`"result": []`):** Falls `getUpdates` ein leeres Ergebnis liefert, wurde noch keine Nachricht an den Bot gesendet. Erst im Telegram-Chat eine Nachricht an den Bot schicken, dann die URL erneut aufrufen.

> **Gruppen-Benachrichtigungen:** Um Nachrichten in eine Telegram-Gruppe zu senden, den Bot zur Gruppe hinzufuegen, dort eine Nachricht senden, und dann `getUpdates` aufrufen. Gruppen-Chat-IDs sind negativ (z.B. `-100123456789`).

> **Sicherheitshinweis:** Den Bot-Token niemals oeffentlich teilen. Falls der Token kompromittiert wurde, beim BotFather mit `/revoke` einen neuen Token generieren.

#### Slack

| Feld | Beschreibung |
|---|---|
| Webhook URL | Incoming Webhook URL |

Webhook erstellen unter: Slack App > Incoming Webhooks

#### Discord

| Feld | Beschreibung |
|---|---|
| Webhook URL | Discord Channel Webhook URL |

Webhook erstellen: Kanal-Einstellungen > Integrationen > Webhooks

#### Gotify

| Feld | Beschreibung |
|---|---|
| Server URL | Gotify-Serveradresse |
| App Token | App-Token aus Gotify |
| Prioritaet | Numerisch (Standard: 5) |

### Individuelle Warntage

Unter **Produkte** kann fuer jedes Produkt ein individueller Warnzeitraum gesetzt werden:

- **Standard** (aus Einstellungen, z.B. 5 Tage)
- **Individuell** pro Produkt (z.B. Milch = 2 Tage, Konserven = 30 Tage)

Einfach im Feld "Warntage" den gewuenschten Wert eingeben. "Reset" setzt auf den Standardwert zurueck.

### CalDAV-Synchronisation

Grocylink kann Tasks und Chores aus Grocy bidirektional mit einem CalDAV-Server synchronisieren. Jeder Task und jede Chore wird als **VTODO-Eintrag** im CalDAV-Kalender angelegt.

#### Einrichtung

1. Navigiere zu **CalDAV** in der Seitenleiste
2. Trage die **CalDAV Server URL** ein (z.B. `https://nextcloud.example.com`)
3. Waehle den **Servertyp** aus oder trage manuell den **DAV-Pfad** ein (z.B. `/remote.php/dav`)
4. Gib **Benutzername** und **Passwort** ein
5. Klicke auf **Verbindung testen** - bei Erfolg werden die verfuegbaren Kalender angezeigt
6. Klicke auf **Laden** neben der Kalender-Auswahl und waehle den gewuenschten Kalender
7. Setze das **Sync-Intervall** (Standard: 30 Minuten)
8. Aktiviere die **Automatische Synchronisation**
9. Klicke auf **CalDAV-Einstellungen speichern**

#### Kompatible CalDAV-Server

| Server | URL-Format | Pfad |
|---|---|---|
| Nextcloud | `https://server.example.com` | `/remote.php/dav` |
| Radicale | `https://server.example.com` | `/radicale/` |
| Baikal | `https://server.example.com` | `/baikal/html/dav.php` |
| iCloud | `https://caldav.icloud.com` | - |
| RFC 6764 | `https://server.example.com` | `/.well-known/caldav` |

#### Sync-Verhalten

**Grocy -> CalDAV:**
- Jeder Grocy-Task und jede Chore wird als VTODO angelegt
- UID-Schema: `grocy-task-{id}@grocylink` / `grocy-chore-{id}@grocylink`
- Felder: SUMMARY (Name), DESCRIPTION (Beschreibung), DUE (Faelligkeitsdatum), STATUS
- Erledigte Tasks werden mit STATUS=COMPLETED synchronisiert

**CalDAV -> Grocy:**
- Wird ein VTODO im CalDAV-Client als erledigt markiert, wird der entsprechende Task/Chore beim naechsten Sync auch in Grocy als erledigt markiert
- Wird ein VTODO wieder auf "offen" gesetzt, wird der Task in Grocy ebenfalls wieder geoeffnet (undo)
- Aenderungen an Name, Beschreibung und Faelligkeitsdatum werden zurueck nach Grocy synchronisiert
- Neue Aufgaben, die im CalDAV-Client erstellt werden, werden automatisch als neue Tasks in Grocy angelegt
- **Duplikat-Erkennung**: Beim Import neuer Aufgaben aus CalDAV wird sowohl die Original-UID als auch die Grocylink-UID in der Sync-Map gespeichert, um doppelte Imports zu verhindern. Zusaetzlich wird geprueft, ob in Grocy bereits ein Task mit identischem Namen existiert

#### Sync-Mapping

Die Tabelle "Sync-Mapping" auf der CalDAV-Seite zeigt alle synchronisierten Eintraege mit Typ, Grocy-ID, CalDAV-UID, aktuellem Status, Sync-Richtung und Zeitpunkt der letzten Synchronisation.

---

## Reverse Proxy / HTTPS

Grocylink stellt nur **HTTP auf Port 5000** bereit. Fuer HTTPS wird ein externer Reverse Proxy empfohlen.

### Beispiel: Caddy

```caddyfile
grocylink.example.com {
    tls /certs/fullchain.pem /certs/key.pem
    reverse_proxy http://172.30.45.26:5000
}
```

### Beispiel: Nginx

```nginx
server {
    listen 443 ssl;
    server_name grocylink.example.com;

    ssl_certificate /certs/fullchain.pem;
    ssl_certificate_key /certs/key.pem;

    location / {
        proxy_pass http://172.30.45.26:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Beispiel: Traefik (Docker Labels)

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.grocylink.rule=Host(`grocylink.example.com`)"
  - "traefik.http.routers.grocylink.tls=true"
  - "traefik.http.services.grocylink.loadbalancer.server.port=5000"
```

### Vollstaendige Zertifikatskette

> **Wichtig:** Beim TLS-Zertifikat immer die **fullchain.pem** (Leaf + Intermediate) verwenden, nicht nur die cert.pem. Andernfalls koennen Clients (z.B. Python `requests`) die Verbindung nicht verifizieren, da das Intermediate-Zertifikat fehlt.
>
> ```bash
> # Fullchain erstellen (Leaf + Intermediate)
> cat cert.pem > fullchain.pem
> curl -s https://letsencrypt.org/certs/2024/e7.pem >> fullchain.pem
> ```
>
> Pruefen ob die Datei korrekt ist (muss `2` zurueckgeben):
>
> ```bash
> grep -c "BEGIN CERTIFICATE" fullchain.pem
> ```
>
> Pruefen ob der Server die vollstaendige Chain liefert:
>
> ```bash
> openssl s_client -connect domain.example.com:443 -servername domain.example.com 2>&1 | grep "depth="
> # Erwartet: depth=0 (Leaf) und depth=1 (Intermediate)
> ```

### SSL-Verifizierung der Grocy-Verbindung

Grocylink verifiziert standardmaessig das SSL-Zertifikat der Grocy-Instanz. Falls die Grocy-Instanz ein Zertifikat ohne vollstaendige Chain liefert oder ein selbstsigniertes Zertifikat verwendet, kann die Verifizierung unter **Einstellungen** mit der Checkbox **"SSL-Zertifikat verifizieren"** deaktiviert werden.

> **Empfehlung:** Die SSL-Verifizierung sollte nur voruebergehend deaktiviert werden. Besser ist es, das SSL-Problem auf dem Grocy-Server zu beheben (vollstaendige Zertifikatskette konfigurieren).

---

## Sicherheit

### Container-Haertung

Grocylink laeuft standardmaessig mit minimalen Berechtigungen:

- **Non-Root**: Container laeuft als unprivilegierter User (konfigurierbar via `UID`/`GID`)
- **cap_drop: ALL**: Alle Linux Capabilities entfernt
- **no-new-privileges**: Keine Privilege Escalation moeglich
- **Ressourcenlimits**: CPU, RAM und Prozessanzahl begrenzt

### Verschluesselung sensibler Daten

Alle Passwoerter und API-Keys werden mit **Fernet (AES-128-CBC + HMAC-SHA256)** verschluesselt in der SQLite-Datenbank gespeichert.

**Verschluesselte Felder:**
- Grocy API-Key (Settings)
- CalDAV-Passwort (Settings)
- Email-Passwoerter (Channel-Config)
- API-Tokens: Pushover, Telegram Bot-Token, Gotify App-Token
- Webhook-URLs: Slack, Discord

**Encryption Key:**
- Wird automatisch beim ersten Start generiert
- Gespeichert in `data/.encryption_key` (Datei-Berechtigung: 600)
- **Wichtig:** Diese Datei sichern! Ohne sie koennen verschluesselte Daten nicht entschluesselt werden

### Datenpersistenz und Volumes

Grocylink speichert alle Daten in `/app/data/` innerhalb des Containers. Dieses Verzeichnis **muss** als Docker-Volume gemountet sein, damit Daten einen Container-Neustart oder Redeploy ueberleben.

**Kritische Dateien in `/app/data/`:**

| Datei | Beschreibung |
|---|---|
| `grocy_notify.db` | SQLite-Datenbank mit allen Einstellungen, Kanaelen, Overrides und Logs |
| `.encryption_key` | Fernet-Schluessel zur Ent-/Verschluesselung aller Passwoerter und API-Keys |

> **WICHTIG:** Geht der `.encryption_key` verloren (z.B. durch Loeschen des Volumes), koennen alle verschluesselten Werte in der Datenbank **nicht mehr entschluesselt** werden. Alle Zugangsdaten (API-Keys, Passwoerter, Webhook-URLs, Kanalkonfigurationen) muessen dann neu eingegeben werden.

**Volume-Konfiguration (Bind Mount):**

```yaml
volumes:
  - ${PATH_TO}/grocylink/data:/app/data       # Datenbank + Encryption Key
```

Bei der Standard-Konfiguration mit `PATH_TO=/var/container/ds06` liegen die Daten unter:
- `/var/container/ds06/grocylink/data/` - Datenbank und Encryption Key

**Beim Redeploy beachten:**
- Bind Mounts bleiben bei `docker compose down` **immer** erhalten (anders als Named Volumes)
- Auch ein Redeploy in Komodo behaelt alle Daten, da sie direkt auf dem Host liegen
- Die Daten bleiben selbst bei `docker compose down -v` erhalten, da `-v` nur Named Volumes loescht
- Beim Start prueft Grocylink automatisch ob das Volume korrekt gemountet ist und gibt eine Warnung aus, falls nicht

**Integritaetspruefung:**
Grocylink prueft beim Start ob der Encryption Key zur Datenbank passt. Falls nicht (z.B. nach Key-Verlust), erscheint eine Warnung im Log:

```
WARNUNG: Encryption Key passt nicht zur Datenbank!
Verschluesselte Werte koennen nicht entschluesselt werden.
Bitte alle Zugangsdaten neu eingeben.
```

### Empfehlungen

- Datenverzeichnis (`data`) regelmaessig sichern
- **Backup des Encryption Keys**: `docker cp grocylink:/app/data/.encryption_key ./encryption_key.backup`
- **Backup der Datenbank**: `docker cp grocylink:/app/data/grocy_notify.db ./grocy_notify.db.backup`
- Zugriff auf die Webapplikation via Firewall oder VPN einschraenken
- `data/.encryption_key` separat und sicher aufbewahren
- Externen Reverse Proxy fuer HTTPS verwenden

---

## API-Referenz

Alle API-Endpunkte unter `/api/`:

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/settings` | Einstellungen abrufen |
| `POST` | `/api/settings` | Einstellungen speichern |
| `POST` | `/api/test-connection` | Grocy-Verbindung testen |
| `GET` | `/api/status` | Aktueller Stock-Status (volatile) |
| `GET` | `/api/channels` | Alle Notification-Kanaele |
| `POST` | `/api/channels` | Kanal erstellen/bearbeiten |
| `DELETE` | `/api/channels/<id>` | Kanal loeschen |
| `POST` | `/api/channels/<id>/test` | Test-Nachricht senden |
| `GET` | `/api/products` | Produkte mit Override-Einstellungen |
| `POST` | `/api/products/override` | Produkt-Warntage setzen |
| `GET` | `/api/log` | Benachrichtigungs-Historie |
| `DELETE` | `/api/log` | Log leeren |
| `POST` | `/api/check-now` | Manuellen Check ausloesen |
| `GET` | `/api/caldav/status` | CalDAV-Sync-Status und Statistiken |
| `POST` | `/api/caldav/test` | CalDAV-Verbindung testen |
| `GET` | `/api/caldav/calendars` | Verfuegbare Kalender abrufen |
| `POST` | `/api/caldav/sync-now` | Manuelle Synchronisation ausloesen |
| `GET` | `/api/caldav/map` | Sync-Mapping-Tabelle abrufen |

---

## Fehlerbehebung

### "Grocy nicht konfiguriert"
Unter Einstellungen muessen Grocy-URL und API-Key eingetragen werden.

### Verbindungstest schlaegt fehl
- Ist die Grocy-URL korrekt (inkl. Protokoll `http://` oder `https://`)?
- Ist der API-Key gueltig? (In Grocy pruefen)
- Ist Grocy vom Container/Server aus erreichbar?
- Bei HTTPS: Liefert der Grocy-Server die vollstaendige Zertifikatskette? (siehe [Vollstaendige Zertifikatskette](#vollstaendige-zertifikatskette))
- Temporaerer Workaround: "SSL-Zertifikat verifizieren" in den Einstellungen deaktivieren

### Benachrichtigungen kommen nicht an
1. Kanal-Test-Funktion nutzen (Button "Test")
2. Log pruefen (Seite "Log")
3. Bei Email: App-Passwort statt normalem Passwort verwenden (Gmail, etc.)
4. Bei Telegram: Chat-ID pruefen (muss numerisch sein)

### SSL-Zertifikat Probleme

**Grocy-Verbindung schlaegt mit SSL-Fehler fehl (`CERTIFICATE_VERIFY_FAILED`):**

Dieses Problem tritt auf, wenn der Grocy-Server nur das Leaf-Zertifikat liefert, aber nicht die vollstaendige Zertifikatskette (Intermediate fehlt). Python `requests` kann die Kette dann nicht verifizieren.

**Diagnose:**
```bash
# Pruefen ob der Server die vollstaendige Chain liefert
openssl s_client -connect grocy.example.com:443 -servername grocy.example.com 2>&1 | grep "depth="
# Nur "depth=0" = Intermediate fehlt!
# "depth=0" + "depth=1" = Chain vollstaendig
```

**Loesung (auf dem Grocy-Server):**
1. `fullchain.pem` erstellen (Leaf + Intermediate):
   ```bash
   cat cert.pem > fullchain.pem
   curl -s https://letsencrypt.org/certs/2024/e7.pem >> fullchain.pem
   ```
2. Reverse Proxy konfigurieren, `fullchain.pem` statt `cert.pem` zu verwenden
3. Berechtigungen pruefen - der Webserver-User muss die Datei lesen koennen
4. Webserver neu starten

**Workaround (in Grocylink):**
Unter Einstellungen die Checkbox "SSL-Zertifikat verifizieren" deaktivieren. Dies sollte nur als temporaere Loesung verwendet werden.

### CalDAV-Sync funktioniert nicht

1. **Verbindung testen**: Auf der CalDAV-Seite "Verbindung testen" klicken
2. **URL pruefen**: Die CalDAV-URL muss den korrekten Servertyp/Pfad enthalten (z.B. `/remote.php/dav` bei Nextcloud)
3. **Kalender pruefen**: Ein Kalender muss ausgewaehlt und gespeichert sein
4. **Benutzername/Passwort**: Bei Nextcloud ggf. ein App-Passwort verwenden
5. **Firewall**: Der CalDAV-Server muss vom Container aus erreichbar sein
6. **Log pruefen**: Im Container-Log (`docker compose logs -f`) erscheinen detaillierte Sync-Meldungen

### Berechtigungsprobleme (Non-Root Container)

Falls der Container mit Berechtigungsfehlern startet:

```bash
# Datenverzeichnis fuer den Container-User schreibbar machen
chown -R 1000:1000 /var/container/ds06/grocylink/data/

# Oder mit der konfigurierten UID/GID
chown -R ${UID}:${GID} ${PATH_TO}/grocylink/data/
```

### Daten nach Redeploy verloren

**Symptome:** Nach einem Redeploy sind alle Einstellungen, Kanaele und API-Keys weg, oder Kanaele sind vorhanden aber Verbindungstests schlagen fehl.

**Ursache 1: Volume nicht gemountet**
Pruefen ob das Volume korrekt gemountet ist:
```bash
docker inspect grocylink | grep -A5 "Mounts"
```
Die Ausgabe muss `/app/data` als Mount zeigen. Falls nicht: `compose.yaml` pruefen ob die Volumes konfiguriert sind.

**Ursache 2: Encryption Key verloren**
Falls die DB vorhanden ist, aber verschluesselte Daten nicht mehr lesbar sind (API-Keys, Passwoerter funktionieren nicht):
```bash
docker logs grocylink 2>&1 | grep -i "encryption\|warnung"
```
Falls die Warnung "Encryption Key passt nicht" erscheint, muessen alle Zugangsdaten neu eingegeben werden. Ein Backup des Keys kann wiederhergestellt werden:
```bash
docker cp ./encryption_key.backup grocylink:/app/data/.encryption_key
docker compose restart
```

### Datenbank zuruecksetzen
```bash
docker exec grocylink rm /app/data/grocy_notify.db
docker compose restart
```
**Achtung:** Alle Einstellungen und Kanaele gehen verloren.

---

## Bugs melden &amp; Features vorschlagen

Grocylink verwendet [GitHub Issues](https://github.com/c42u/grocylink/issues) als zentralen Bugtracker und Feature-Tracker.

### Bug melden

1. Oeffne [Bug Report](https://github.com/c42u/grocylink/issues/new?labels=bug&template=bug_report.md)
2. Beschreibe den Fehler, die Schritte zur Reproduktion und das erwartete Verhalten
3. Fuege wenn moeglich Logs bei (`docker compose logs grocylink`)

### Feature vorschlagen

1. Oeffne [Feature Request](https://github.com/c42u/grocylink/issues/new?labels=enhancement&template=feature_request.md)
2. Beschreibe das gewuenschte Feature und den Anwendungsfall
3. Optional: Loesungsvorschlaege oder Mockups beifuegen

### Direkt aus der App

Auf der **Hilfe**-Seite und im **Footer** der App befinden sich direkte Links zu GitHub Issues, um Bugs und Feature Requests schnell einzureichen.
