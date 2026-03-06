#!/bin/bash
set -e

echo "=== Grocylink Startup ==="
echo "User: $(id)"

# Persistente Daten prüfen
if [ -f /app/data/.encryption_key ]; then
    echo "[OK] Encryption Key vorhanden"
else
    echo "[INFO] Kein Encryption Key gefunden - wird beim ersten Start generiert"
fi

if [ -f /app/data/grocy_notify.db ]; then
    echo "[OK] Datenbank vorhanden ($(du -h /app/data/grocy_notify.db | cut -f1))"
else
    echo "[INFO] Keine Datenbank gefunden - wird beim ersten Start angelegt"
fi

# Volume-Mount prüfen
if mountpoint -q /app/data 2>/dev/null; then
    echo "[OK] /app/data ist ein gemountetes Volume"
else
    echo "[WARNUNG] /app/data ist KEIN gemountetes Volume! Daten gehen beim Redeploy verloren!"
fi

# Gunicorn starten (Flask-App)
echo "Starte Grocylink..."
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    "app:app" \
    --preload
