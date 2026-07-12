from .base import *  # noqa: F403

# CI provides DATABASE_URL for its Postgres service; locally, fall back to
# the docker-compose Postgres. SQLite is NOT used — tests should run against
# the same engine as production.
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # noqa: S105 — fast test hashing
