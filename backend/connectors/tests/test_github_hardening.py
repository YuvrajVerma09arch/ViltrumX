"""Hardening tests for the GitHub connector.

Covers the three production gaps from tasks/plan.md: unsigned webhooks when no
secret is configured, mock OAuth codes accepted in every environment, and
tenant selection by slug substring instead of exact connector mapping.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from connectors.models import Connector, OAuthState
from connectors.views import _tenant_for_org
from core.models import Tenant

WEBHOOK_URL = "/webhooks/github"
CALLBACK_URL = "/api/v1/connectors/gh/oauth/callback"
SECRET = "test-webhook-secret"  # noqa: S105 — test-only constant


def _payload(org: str) -> dict:
    return {
        "action": "created",
        "organization": {"login": org},
        "repository": {"full_name": f"{org}/repo", "owner": {"login": org}},
        "sender": {"login": "octocat"},
    }


def _signed_post(client: APIClient, payload: dict, secret: str = SECRET):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=signature,
        HTTP_X_GITHUB_EVENT="push",
    )


@pytest.fixture
def api():
    return APIClient()


@override_settings(DEBUG=False, GITHUB_WEBHOOK_SECRET="")
def test_unsigned_webhook_rejected_when_secret_absent_in_production(db, api):
    """Production fails closed with 503 instead of trusting an unsigned payload."""
    response = api.post(
        WEBHOOK_URL,
        data=json.dumps(_payload("acme")).encode(),
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="push",
    )
    assert response.status_code == 503


@override_settings(DEBUG=True, GITHUB_WEBHOOK_SECRET="")
def test_unsigned_webhook_still_allowed_in_debug_dev_mock(db, api):
    """The dev mock is preserved — but only when DEBUG is True."""
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    Connector.objects.create(tenant=tenant, connector_id="gh", github_org_login="acme")

    with patch("connectors.views.ingest_event.delay") as delay:
        response = api.post(
            WEBHOOK_URL,
            data=json.dumps(_payload("acme")).encode(),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
        )
    assert response.status_code == 200
    delay.assert_called_once()


@override_settings(DEBUG=False, GITHUB_WEBHOOK_SECRET=SECRET)
def test_invalid_signature_rejected(db, api):
    response = api.post(
        WEBHOOK_URL,
        data=json.dumps(_payload("acme")).encode(),
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=deadbeef",
        HTTP_X_GITHUB_EVENT="push",
    )
    assert response.status_code == 401


@override_settings(DEBUG=False, GITHUB_WEBHOOK_SECRET=SECRET)
def test_valid_signature_accepted_for_mapped_tenant(db, api):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    Connector.objects.create(
        tenant=tenant, connector_id="gh", github_org_login="acme", status="connected"
    )

    with patch("connectors.views.ingest_event.delay") as delay:
        response = _signed_post(api, _payload("acme"))

    assert response.status_code == 200
    assert response.json() == {"queued": True}
    delay.assert_called_once()
    assert delay.call_args.args[0] == tenant.id


@override_settings(DEBUG=False, GITHUB_WEBHOOK_SECRET=SECRET)
def test_unknown_org_rejected(db, api):
    with patch("connectors.views.ingest_event.delay") as delay:
        response = _signed_post(api, _payload("unknown-org"))
    assert response.status_code == 404
    delay.assert_not_called()


@override_settings(DEBUG=False, GITHUB_WEBHOOK_SECRET=SECRET)
def test_substring_lookalike_tenant_not_mapped(db, api):
    """Only a lookalike tenant whose slug CONTAINS the org exists.

    The old ``slug__icontains`` logic would route the webhook there. The exact
    connector mapping (plus the tight demo fallback) must reject it instead.
    """
    lookalike = Tenant.objects.create(name="PayKraft Clone", slug="paykraft-clone")
    with patch("connectors.views.ingest_event.delay") as delay:
        response = _signed_post(api, _payload("paykraft"))
    assert response.status_code == 404
    delay.assert_not_called()
    assert lookalike.connectors.count() == 0


def test_tenant_for_org_uses_exact_connector_mapping(db):
    real = Tenant.objects.create(name="Acme", slug="acme")
    lookalike = Tenant.objects.create(name="Acme Clone", slug="acme-clone")
    Connector.objects.create(tenant=real, connector_id="gh", github_org_login="Acme")
    Connector.objects.create(tenant=lookalike, connector_id="gh", github_org_login="acme-clone")

    assert _tenant_for_org("acme") == real
    assert _tenant_for_org("ACME") == real  # case-insensitive, still exact
    assert _tenant_for_org("acme-clone") == lookalike
    assert _tenant_for_org("not-an-acme") is None


@override_settings(DEBUG=False)
def test_mock_oauth_code_rejected_when_debug_false(db, api):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    OAuthState.objects.create(
        state="state-123",
        tenant_id=tenant.id,
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    response = api.get(CALLBACK_URL, {"state": "state-123", "code": "demo-code-abc"})

    assert response.status_code == 400
    assert not Connector.objects.filter(
        tenant=tenant, connector_id="gh", status="connected"
    ).exists()
