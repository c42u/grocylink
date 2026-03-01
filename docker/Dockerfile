FROM python:3.12-slim

# OCI-Standard-Labels – werden vom GitHub Actions Workflow (metadata-action)
# automatisch mit Version, Build-Datum und Git-Revision befüllt
ARG BUILD_DATE
ARG VERSION
ARG REVISION

LABEL org.opencontainers.image.title="Grocylink" \
      org.opencontainers.image.description="Grocy Monitoring, Notifications & CalDAV Sync" \
      org.opencontainers.image.authors="c42u" \
      org.opencontainers.image.licenses="GPL-3.0" \
      org.opencontainers.image.source="https://github.com/c42u/grocylink-test" \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates iputils-ping \
        gcc libffi-dev python3-dev \
        libssl-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Code/requirements.txt .
# --prefer-binary: vorgefertigte Wheels bevorzugen (verhindert Rust/C-Kompilierung auf arm/v7)
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Nur Applikations-Code kopieren (kein docker/, Dokumentation/ etc.)
COPY Code/ .

COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

RUN mkdir -p /app/data && \
    chmod -R o+rX /app

VOLUME ["/app/data"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fs http://localhost:5000/api/settings || exit 1

ENTRYPOINT ["/entrypoint.sh"]
