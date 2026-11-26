"""
ViltrumX settings — base. Environment-specific overrides live in
dev.py / staging.py / prod.py (selected via DJANGO_SETTINGS_MODULE).
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(path: Path) -> None:
    """Read the repo-root .env into os.environ for local (non-container) runs.

    Docker Compose injects these via `env_file:`, so this is a no-op there.
    Uses setdefault so real environment variables always win — a production
    secrets manager is never overridden by a stray .env on disk.
    """
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")  # noqa: S105
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # viltrumx apps
    "core",
    "connectors",
    "ontology",
    "detection",
    "actions",
    "reports",
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves collected static files (Django admin) straight from the
    # ASGI app, so prod needs no separate static host behind nginx.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "viltrumx.urls"
WSGI_APPLICATION = "viltrumx.wsgi.application"
ASGI_APPLICATION = "viltrumx.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Honour DATABASE_URL when provided (Docker Compose, CI, prod). The default
# preserves the original local-dev values so `runserver` works with no env var.
_DEFAULT_DATABASE_URL = "postgres://viltrumx:viltrumx_dev@localhost:5432/viltrumx?sslmode=disable"
DATABASES = {
    "default": dj_database_url.config(
        default=_DEFAULT_DATABASE_URL,
        conn_max_age=600,
    )
}
# Bound connection attempts for Postgres only — SQLite rejects connect_timeout.
if DATABASES["default"]["ENGINE"].endswith("postgresql"):
    DATABASES["default"].setdefault("OPTIONS", {}).setdefault("connect_timeout", 3)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        # Content-hashed + gzipped assets, served by WhiteNoise. Shared by all
        # environments; collectstatic (entrypoint.sh) populates STATIC_ROOT.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# nginx terminates TLS and forwards the original scheme; trust it so Django
# knows the request was HTTPS (needed for secure cookies inside the proxy).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Comma-separated allowlist for state-changing requests behind the proxy.
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# ── DRF + JWT ────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    # Order matters: ServiceTokenAuthentication must come FIRST. Both classes
    # claim the "Bearer" scheme, but JWTAuthentication *raises* on a token it
    # cannot decode, which aborts the whole chain — so if it ran first the
    # orchestrator's service token would never be reached (401). The service
    # class returns None on a non-match, letting JWT run for human callers.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.service_auth.ServiceTokenAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": None,  # screen payloads are small, curated lists
    # Per-view throttles via `throttle_scope` on the view. The "auth" scope is
    # wired onto the email-code endpoints so one client can't brute-force send.
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "auth": "30/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),  # dev-friendly; tighten in prod.py
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ── Email / owner verification ───────────────────────────────────────────────
# Safe dev default: the console backend prints mail instead of needing SMTP, so
# signup/login flows work offline. Production supplies EMAIL_BACKEND + SMTP
# credentials via the environment; no real secrets live in this file.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "false").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "ViltrumX <no-reply@viltrumx.local>")

# One-time code lifecycle (6-digit codes, hashed at rest, single use).
VERIFICATION_CODE_TTL_SECONDS = int(os.environ.get("VERIFICATION_CODE_TTL_SECONDS", "600"))
VERIFICATION_MAX_ATTEMPTS = int(os.environ.get("VERIFICATION_MAX_ATTEMPTS", "5"))
VERIFICATION_RESEND_COOLDOWN_SECONDS = int(
    os.environ.get("VERIFICATION_RESEND_COOLDOWN_SECONDS", "60")
)
VERIFICATION_MAX_RESENDS = int(os.environ.get("VERIFICATION_MAX_RESENDS", "3"))

# ── Celery / Redis ───────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False  # dev.py flips this so tasks run inline w/o a worker

# ── Data stores (Week 2+) ────────────────────────────────────────────────────
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "viltrumx_dev")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# ── LLM explanation layer (never used for detection — CLAUDE.md §6) ─────────
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # "groq" | "ollama"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# ── Django Channels (WebSocket live feed) ────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# ── Internal service token (orchestrator → Django API, Week 3) ──────────────
ORCHESTRATOR_SERVICE_TOKEN = os.environ.get("ORCHESTRATOR_SERVICE_TOKEN", "")

# ── Frontend URL (for OAuth redirects) ────────────────────────────────────────
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# ── Connector provider credentials (P2) ──────────────────────────────────────
# Every value here comes from the environment — never commit real secrets.
# A missing key simply leaves that provider unconfigured (poll returns 0).
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_WORKSPACE_ADMIN = os.environ.get("GOOGLE_WORKSPACE_ADMIN", "")
AWS_ROLE_ARN = os.environ.get("AWS_ROLE_ARN", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
# Webhook secret is SEPARATE from the key secret and differs per mode (test/live).
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
# GST invoicing (seller identity). Seller state decides CGST+SGST vs IGST.
GST_SELLER_GSTIN = os.environ.get("GST_SELLER_GSTIN", "")
GST_SELLER_STATE = os.environ.get("GST_SELLER_STATE", "")

# ── Startup verification (P4) ────────────────────────────────────────────────
# Require company-domain email at signup (blocks gmail creating an org).
# Set REQUIRE_BUSINESS_EMAIL=0 for local demos. Domain DNS check is on by
# default; disable in offline test envs with VERIFICATION_DNS_ENABLED=0.
REQUIRE_BUSINESS_EMAIL = os.environ.get("REQUIRE_BUSINESS_EMAIL", "1") == "1"
VERIFICATION_DNS_ENABLED = os.environ.get("VERIFICATION_DNS_ENABLED", "1") == "1"
# Optional GSTIN vendor lookup (Surepass/Karza). Empty => checksum-only.
GSTIN_API_KEY = os.environ.get("GSTIN_API_KEY", "")
GSTIN_API_URL = os.environ.get("GSTIN_API_URL", "")

# ── Orchestrator hand-off ────────────────────────────────────────────────────
# When ORCHESTRATOR_ENABLED is false ingestion skips the Redis publish that
# wakes the LangGraph worker. ORCHESTRATOR_STREAM is the pub/sub channel the
# orchestrator's `worker` mode subscribes to (must match on both sides).
ORCHESTRATOR_ENABLED = os.environ.get("ORCHESTRATOR_ENABLED", "1")
ORCHESTRATOR_STREAM = os.environ.get("ORCHESTRATOR_STREAM", "viltrumx:events")
ORCHESTRATOR_TENANT_SLUG = os.environ.get("ORCHESTRATOR_TENANT_SLUG", "")
# The tenant's home country — events resolving outside it count as foreign for
# impossible-travel / geo-mismatch detection. Default India.
TENANT_HOME_COUNTRY = os.environ.get("TENANT_HOME_COUNTRY", "IN")

# ── Celery beat schedule ─────────────────────────────────────────────────────
# Periodic jobs, all timezone-aware via TIME_ZONE (Asia/Kolkata).
CELERY_BEAT_SCHEDULE = {
    "poll-all-connectors": {
        "task": "connectors.tasks.poll_all_connectors",
        "schedule": crontab(minute="*/5"),
    },
    "sweep-auto-rollbacks": {
        "task": "actions.tasks.sweep_auto_rollbacks",
        "schedule": crontab(minute="*"),
    },
    "nightly-readiness": {
        "task": "reports.tasks.nightly_readiness",
        "schedule": crontab(hour=2, minute=30),
    },
}
