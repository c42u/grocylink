# Feedback-Modul v1 (Test)

Eingebautes Feedback-System fuer Grocylink, das ohne GitHub-Account funktioniert.

## Dateien

| Datei | Beschreibung |
|---|---|
| `feedback_routes.py` | Flask Blueprint mit API-Endpunkten (`/api/feedback`) |
| `feedback_page.html` | HTML-Vorlage fuer die Feedback-Seite (Nav-Link + Page-Content) |
| `feedback_app.js` | JavaScript-Funktionen (Submit, Liste, Status, Delete) |
| `feedback_i18n.js` | i18n-Strings DE/EN |

## Features

- **Feedback-Formular**: Bug Reports und Feature Requests direkt in der App
- **Kein GitHub-Account noetig**: Feedback wird lokal in SQLite gespeichert
- **Optionale Kontakt-Email**: Fuer Rueckfragen
- **Admin-Ansicht**: Tabelle mit allen Feedbacks, Status-Verwaltung (Offen/In Bearbeitung/Geschlossen)
- **Benachrichtigung**: Optional Feedback per erstem konfigurierten Kanal an Admin senden
- **Zweisprachig**: Komplett DE/EN ueber i18n
- **GitHub-Verweis**: Hinweis auf GitHub Issues fuer User die einen Account haben

## Integration

### 1. Backend (app.py)

```python
from feedback_routes import feedback_bp, init_feedback_db

init_feedback_db()
app.register_blueprint(feedback_bp)
```

### 2. Navigation (templates/index.html)

Nav-Link nach "Hilfe" einfuegen (siehe feedback_page.html).

### 3. Page-Content (templates/index.html)

Den `<div class="page" id="page-feedback">` Block aus feedback_page.html
in `<main class="content">` einfuegen.

### 4. JavaScript (static/app.js)

- Code aus `feedback_app.js` in app.js einfuegen
- In `loadPageData()`: `case 'feedback': loadFeedbackList(); break;`

### 5. i18n (static/i18n.js)

Keys aus `feedback_i18n.js` in die I18N.de und I18N.en Objekte einfuegen.

### 6. Einstellungen (optional)

Um Feedback-Benachrichtigungen zu aktivieren, unter Einstellungen
`feedback_notify` auf `1` setzen (muss als Setting-Feld ergaenzt werden).

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/feedback` | Alle Feedbacks abrufen |
| `POST` | `/api/feedback` | Neues Feedback einreichen |
| `PATCH` | `/api/feedback/<id>` | Status/Admin-Notiz aktualisieren |
| `DELETE` | `/api/feedback/<id>` | Feedback loeschen |

## Datenbank-Schema

```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL DEFAULT 'bug',       -- 'bug' oder 'feature'
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    contact TEXT DEFAULT '',                 -- optionale Email
    status TEXT NOT NULL DEFAULT 'open',     -- 'open', 'in_progress', 'closed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    admin_note TEXT DEFAULT ''
);
```
