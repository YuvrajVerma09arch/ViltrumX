"""
WebSocket consumer — streams agent activity to the Command Deck.

Event types (ARCHITECTURE §9):
  feed.line        → activity feed row
  agent_status     → agent state update
  incident_update  → incident status change
  action_update    → action status change
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class TenantStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope["url_route"]["kwargs"]["tenant_id"]
        self.group = f"tenant_{self.tenant_id}_stream"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    # ── group message handlers (type maps to method name with . → _) ─────────

    async def feed_line(self, event):
        await self.send(text_data=json.dumps({"type": "feed.line", **event}))

    async def agent_status(self, event):
        await self.send(text_data=json.dumps({"type": "agent_status", **event}))

    async def incident_update(self, event):
        await self.send(text_data=json.dumps({"type": "incident_update", **event}))

    async def action_update(self, event):
        await self.send(text_data=json.dumps({"type": "action_update", **event}))
