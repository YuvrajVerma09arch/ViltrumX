FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Detection ML plane — the trained .joblib models (Isolation Forest, XGBoost,
# Random Forest, HDBSCAN) in detection/models_store/ are loaded with joblib at
# runtime. Without these packages the scorer silently falls back to a no-ML
# rule-based path and INC-042 scores 0.94 instead of the trained 0.98-0.99, so
# the demo must ship them. hdbscan has no manylinux wheel for slim, so build it
# from source (needs a C compiler), then drop the toolchain to stay small.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential python3-dev \
 && pip install --no-cache-dir scikit-learn xgboost joblib pandas hdbscan \
 && apt-get purge -y --auto-remove build-essential python3-dev \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir requests

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
