"""
ASGI — Channels ProtocolTypeRouter for WebSocket live feed.

Auth stack: the SPA keeps a JWT in localStorage, not a session cookie, and a
browser WebSocket cannot send an ``Authorization`` header — so the stock
``AuthMiddlewareStack`` alone leaves every real client anonymous. We wrap it
with ``JWTAuthMiddleware`` (reads ``?token=<jwt>``) so EITHER a session cookie
OR a query-string JWT authenticates the stream. ``AllowedHostsOriginValidator``
stays outermost to reject cross-origin upgrades.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viltrumx.settings.dev")

django_asgi_app = get_asgi_application()

from core.consumers import TenantStreamConsumer  # noqa: E402 — after django setup
from core.ws_auth import JWTAuthMiddleware  # noqa: E402

websocket_router = URLRouter([
    path("ws/tenant/<int:tenant_id>/stream", TenantStreamConsumer.as_asgi()),
])

# JWT first: it only fills scope["user"] when it has a valid ?token=, and
# leaves an already-authenticated session untouched (see ws_auth.py).
websocket_stack = JWTAuthMiddleware(AuthMiddlewareStack(websocket_router))

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(websocket_stack),
    }
)
