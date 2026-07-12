from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # vite dev server
    "http://localhost:4173",  # vite preview
]

# Run Celery tasks inline so `runserver` alone is a full dev environment;
# start a real worker (`celery -A viltrumx worker`) to test async behavior.
CELERY_TASK_ALWAYS_EAGER = True
