FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5

# Build tools first: hdbscan (and a few ML deps) have no aarch64/slim wheels, so
# they compile from source and need a C toolchain. requirements.txt already lists
# every runtime + ML dependency, so a single install covers it all; the toolchain
# is then purged to keep the image lean.
COPY requirements.txt .
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential python3-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y --auto-remove build-essential python3-dev \
 && rm -rf /var/lib/apt/lists/*

COPY . .
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
EXPOSE 8000
# Daphne, not runserver: the Command Deck's live feed is a WebSocket, and the
# WSGI dev server can't serve the /ws/ upgrade. Daphne handles HTTP + WS on one
# port, so the whole API and the stream share this container. entrypoint.sh
# collects static and (optionally) migrates before handing off to daphne.
ARG DJANGO_SETTINGS_MODULE=viltrumx.settings.dev
ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}
CMD ["/app/entrypoint.sh"]
