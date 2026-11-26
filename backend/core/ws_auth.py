"""
JWT authentication middleware for Django Channels (P1).

The browser WebSocket handshake cannot set an ``Authorization`` header, and the
SPA keeps its JWT in ``localStorage`` (not a Django session cookie), so the
stock ``AuthMiddlewareStack`` always resolves an anonymous user and the Command
Deck feed closes with 4401 for every real client.

This middleware reads the token from the query string (``?token=<jwt>``),
validates it with SimpleJWT, and populates ``scope["user"]``. It never raises:
a missing/invalid/expired token leaves an ``AnonymousUser`` in scope so the
consumer's own authorization check takes over and closes cleanly.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


@database_sync_to_async
def _user_from_token(raw_token: str):
    """Resolve a Django user from a validated JWT access token.

    Imported lazily so this module can be imported before Django apps are
    fully loaded (asgi.py imports it at startup).
    """
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        token = AccessToken(raw_token)
    except TokenError as exc:
        logger.debug("WS JWT rejected: %s", exc)
        return AnonymousUser()

    user_id = token.get("user_id")
    if not user_id:
        return AnonymousUser()

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return AnonymousUser()
    if not user.is_active:
        return AnonymousUser()
    return user


class JWTAuthMiddleware:
    """ASGI middleware: authenticate a WebSocket via ``?token=<jwt>``."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        # A prior (session) middleware may already have set a real user; don't
        # clobber an authenticated session with an anonymous JWT result.
        existing = scope.get("user")
        has_user = existing is not None and getattr(existing, "is_authenticated", False)

        if not has_user and scope.get("type") in ("websocket", "http"):
            token = self._token_from_scope(scope)
            if token:
                scope["user"] = await _user_from_token(token)

        return await self.inner(scope, receive, send)

    @staticmethod
    def _token_from_scope(scope) -> str:
        query = scope.get("query_string", b"")
        try:
            params = parse_qs(query.decode())
        except (UnicodeDecodeError, AttributeError):
            return ""
        values = params.get("token") or []
        return values[0] if values else ""
