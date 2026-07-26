"""
ASGI — Channels ProtocolTypeRouter for WebSocket live feed (Week 3).
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

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter([
                    path("ws/tenant/<int:tenant_id>/stream", TenantStreamConsumer.as_asgi()),
                ])
            )
        ),
    }
)
