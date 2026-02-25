FROM python:3.12-slim

LABEL maintainer="Grocylink"
LABEL description="Grocylink - Grocy Monitoring, Notifications & CalDAV Sync"

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg ca-certificates debian-keyring debian-archive-keyring apt-transport-https iputils-ping net-tools iproute2 tree nano && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends caddy && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN rm -rf docker doku data/__pycache__

COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /app/data /data/caddy /config/caddy

VOLUME ["/app/data", "/data/caddy"]

EXPOSE 443 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fs http://localhost:5000/api/settings || exit 1

ENTRYPOINT ["/entrypoint.sh"]
