"""
Shared Django API client + service-token authentication (ARCH §6).

This is the *only* module the orchestrator uses to touch the governed backend.
Every agent calls Django over HTTP with the service token — never imports
the Django ORM — so the orchestrator container can run, scale, and be
upgraded independently of the backend release cycle.

The matching `ServiceTokenAuthentication` class on the Django side accepts
the same bearer token and grants the `system:orchestrator` actor.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Configured by environment (docker-compose mounts it from .env).
# Trailing-slash tolerant: we always join paths with /api/v1/.
DJANGO_BASE = os.environ.get("DJANGO_BASE_URL", "http://localhost:8000").rstrip("/")
SERVICE_TOKEN = os.environ.get("ORCHESTRATOR_SERVICE_TOKEN", "")
TIMEOUT = float(os.environ.get("ORCHESTRATOR_HTTP_TIMEOUT", "10"))

# A shared connection pool keeps latency low across the orchestrator's
# many small calls per event.
_client: httpx.Client | None = None


def _headers(json: bool = True) -> dict:
    h = {}
    # httpx rejects a header value of "Bearer " (trailing space, empty token)
    # with an opaque "Illegal header value" error — omit the header entirely
    # when no token is configured so the failure reads as a clean 401 instead.
    if SERVICE_TOKEN:
        h["Authorization"] = f"Bearer {SERVICE_TOKEN}"
    if json:
        h["Content-Type"] = "application/json"
    return h


def get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            base_url=f"{DJANGO_BASE}/api/v1",
            headers=_headers(),
            timeout=httpx.Timeout(TIMEOUT, connect=5.0),
        )
    return _client


def call(method: str, path: str, *, json=None, params=None, expect_json: bool = True):
    """Make an authenticated call to the Django backend. Returns dict or None.

    All errors are logged + swallowed — agents must degrade gracefully so a
    single failed enrichment never drops a real attack from the pipeline.
    """
    try:
        client = get_client()
        r = client.request(method, path, json=json, params=params)
        r.raise_for_status()
        return r.json() if expect_json else {"status": r.status_code}
    except httpx.HTTPStatusError as exc:
        logger.warning("API %s %s -> %s: %s",
                       method, path, exc.response.status_code, exc.response.text[:200])
    except (httpx.RequestError, ValueError) as exc:  # noqa: BLE001
        logger.warning("API %s %s failed: %s", method, path, exc)
    return None


def get(path, **kw):
    return call("GET", path, **kw)


def post(path, **kw):
    return call("POST", path, **kw)


def put(path, **kw):
    return call("PUT", path, **kw)


def close():
    """Used by the process entrypoint on shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None
