from .base import *  # noqa: F403

DEBUG = True
# "backend" = the Docker Compose service name the orchestrator uses as its
# Host header (DJANGO_BASE_URL=http://backend:8000); without it, Django
# rejects the orchestrator's calls with 400 DisallowedHost.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "backend", "0.0.0.0"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # vite dev server
    "http://localhost:4173",  # vite preview
]

# Run Celery tasks inline so `runserver` alone is a full dev environment;
# start a real worker (`celery -A viltrumx worker`) to test async behavior.
CELERY_TASK_ALWAYS_EAGER = True
