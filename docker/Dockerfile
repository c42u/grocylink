FROM python:3.12-slim

LABEL maintainer="Grocylink"
LABEL description="Grocylink - Grocy Monitoring, Notifications & CalDAV Sync"

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates iputils-ping && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN rm -rf docker doku data/__pycache__

COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

RUN mkdir -p /app/data && \
    chmod -R o+rX /app

VOLUME ["/app/data"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fs http://localhost:5000/api/settings || exit 1

ENTRYPOINT ["/entrypoint.sh"]
