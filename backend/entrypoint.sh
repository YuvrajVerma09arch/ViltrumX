#!/bin/sh
# Container entrypoint: prepare static files, optionally migrate, then serve.
# Exits non-zero on any uncaught failure so the orchestrator can restart us.
set -e

# WhiteNoise serves from STATIC_ROOT; failure here (e.g. a missing manifest in a
# dev image) must not block boot, so it is best-effort.
python manage.py collectstatic --noinput || true

# Migrations are opt-in: docker-compose.dev sets RUN_MIGRATIONS=1, while scaled
# workers (celery, etc.) share the same image and must not race to migrate.
if [ "$RUN_MIGRATIONS" = "1" ]; then
    python manage.py migrate --noinput
fi

exec daphne -b 0.0.0.0 -p "${PORT:-8000}" viltrumx.asgi:application
