import logging
import os
from datetime import timedelta

from .staging import *  # noqa: F403

logger = logging.getLogger(__name__)

# prod = staging hardening plus strict transport + short-lived tokens
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if not ALLOWED_HOSTS:
    # Fail open to localhost rather than crash boot — but make the misconfig
    # loud so it shows up in container logs before a deploy reaches traffic.
    logger.warning("ALLOWED_HOSTS is empty; falling back to ['localhost']")
    ALLOWED_HOSTS = ["localhost"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}
