"""
WebSocket consumer — streams agent activity to the Command Deck.

Event types (ARCHITECTURE §9):
  feed.line        → activity feed row
  agent_status     → agent state update
  incident_update  → incident status change
  action_update    → action status change
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from core.models import Membership

# WebSocket close codes used for authorization failures.
WS_CLOSE_UNAUTHENTICATED = 4401  # no/invalid session — anonymous connection
WS_CLOSE_BAD_REQUEST = 4400  # missing or malformed tenant id
WS_CLOSE_FORBIDDEN = 4403  # authenticated, but not a member of the tenant


class TenantStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Either AuthMiddlewareStack (session cookie) or JWTAuthMiddleware
        # (?token=<jwt>) populates scope["user"] — see viltrumx/asgi.py.
        # Never let an anonymous client subscribe to a tenant stream.
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=WS_CLOSE_UNAUTHENTICATED)
            return

        # Parse the tenant id from the route; if the route omits a valid id,
        # fall back to the user's own membership so a JWT client still connects.
        tenant_id = self._tenant_id_from_scope()
        if tenant_id is None:
            tenant_id = await self._default_tenant_for(user)
        if tenant_id is None:
            await self.close(code=WS_CLOSE_BAD_REQUEST)
            return

        # Sync ORM call — hand it to the sync-to-async executor so we don't
        # block the event loop (and don't trip Django's async-DB guard).
        if not await self._is_member(user, tenant_id):
            await self.close(code=WS_CLOSE_FORBIDDEN)
            return

        self.tenant_id = tenant_id
        self.group = f"tenant_{self.tenant_id}_stream"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    def _tenant_id_from_scope(self):
        """Return a positive int tenant id from the URL kwargs, or None."""
        raw = self.scope.get("url_route", {}).get("kwargs", {}).get("tenant_id")
        try:
            tenant_id = int(raw)
        except (TypeError, ValueError):
            return None
        return tenant_id if tenant_id > 0 else None

    @database_sync_to_async
    def _default_tenant_for(self, user):
        """The user's first tenant — used when the socket URL has no tenant id."""
        membership = Membership.objects.filter(user=user).order_by("id").first()
        return membership.tenant_id if membership else None

    @database_sync_to_async
    def _is_member(self, user, tenant_id):
        """Membership is the single source of truth for tenant access."""
        return Membership.objects.filter(user=user, tenant_id=tenant_id).exists()

    async def disconnect(self, code):
        # A rejected connection may never have set self.group.
        group = getattr(self, "group", None)
        if group is not None:
            await self.channel_layer.group_discard(group, self.channel_name)

    # ── group message handlers (type maps to method name with . → _) ─────────

    async def feed_line(self, event):
        await self.send(text_data=json.dumps({"type": "feed.line", **event}))

    async def agent_status(self, event):
        await self.send(text_data=json.dumps({"type": "agent_status", **event}))

    async def incident_update(self, event):
        await self.send(text_data=json.dumps({"type": "incident_update", **event}))

    async def action_update(self, event):
        await self.send(text_data=json.dumps({"type": "action_update", **event}))
