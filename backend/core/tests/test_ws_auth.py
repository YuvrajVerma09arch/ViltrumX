"""
Authorization tests for the tenant WebSocket stream.

connect() must reject anonymous connections (4401) and authenticated users
who are not members of the requested tenant (4403) *before* they are added
to the tenant's channel group.

No pytest-asyncio in this project, so async communicator flows are driven
through asgiref's async_to_sync.
"""

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import override_settings
from django.urls import path

from core.consumers import TenantStreamConsumer
from core.models import Membership, Tenant

WS_CLOSE_UNAUTHENTICATED = 4401
WS_CLOSE_FORBIDDEN = 4403

# The project's default channel layer is Redis; tests use the in-process one.
IN_MEMORY_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}


def _application_for(user):
    """Build an ASGI app mirroring production routing, injecting `user`.

    AuthMiddlewareStack normally supplies scope["user"] from the session;
    tests inject it directly so we can exercise each authorization branch
    without building session cookies.
    """
    router = URLRouter([
        path("ws/tenant/<int:tenant_id>/stream", TenantStreamConsumer.as_asgi()),
    ])

    async def app(scope, receive, send):
        scope = dict(scope)
        scope["user"] = user
        await router(scope, receive, send)

    return app


@async_to_sync
async def _connect_and_close(user, tenant_id):
    """Run the full socket lifecycle in one event loop and return the result.

    The communicator's tasks are bound to the loop that runs connect(), so
    disconnect() must run in that same loop (hence one coroutine here).
    """
    communicator = WebsocketCommunicator(
        _application_for(user), f"/ws/tenant/{tenant_id}/stream"
    )
    connected, close_code = await communicator.connect()
    await communicator.disconnect()
    return connected, close_code


def _make_tenant(slug):
    return Tenant.objects.create(name=slug, slug=slug)


def _make_user(username):
    return User.objects.create_user(username=username, password="unused-in-ws-test")


@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
def test_anonymous_connection_is_rejected(db):
    connected, code = _connect_and_close(AnonymousUser(), tenant_id=1)

    assert connected is False
    assert code == WS_CLOSE_UNAUTHENTICATED


@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
def test_authenticated_member_is_accepted(db):
    tenant = _make_tenant("member-tenant")
    user = _make_user("member@example.com")
    Membership.objects.create(user=user, tenant=tenant, role="Analyst", display_name="Member")

    connected, code = _connect_and_close(user, tenant_id=tenant.pk)

    assert connected is True
    assert code is None


@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
def test_authenticated_non_member_is_rejected(db):
    tenant = _make_tenant("closed-tenant")
    user = _make_user("outsider@example.com")  # no Membership at all

    connected, code = _connect_and_close(user, tenant_id=tenant.pk)

    assert connected is False
    assert code == WS_CLOSE_FORBIDDEN


@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
def test_cross_tenant_member_is_rejected(db):
    home = _make_tenant("home-tenant")
    other = _make_tenant("other-tenant")
    user = _make_user("cross@example.com")
    Membership.objects.create(user=user, tenant=home, role="Viewer", display_name="Cross")

    # Member of `home`, but attempts to subscribe to `other`.
    connected, code = _connect_and_close(user, tenant_id=other.pk)

    assert connected is False
    assert code == WS_CLOSE_FORBIDDEN
