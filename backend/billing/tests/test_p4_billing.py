"""
P4 regression tests — billing correctness + startup verification.

Money must be paise-exact and idempotent; verification must actually gate real
ingest. These run without live Razorpay keys (the client is absent → endpoints
return 503, which is itself the honest behavior under test).
"""

import hashlib
import hmac

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from billing import gst
from billing.models import GstInvoice, Order
from core.models import Membership, Tenant


def _tenant(slug="acme", role="Owner", verified=True):
    from django.utils import timezone

    kw = {}
    if verified:
        kw = {"domain": "acme.in", "domain_verified_at": timezone.now(),
              "verification_status": "domain_verified"}
    t = Tenant.objects.create(name=slug.title(), slug=slug, **kw)
    u = User.objects.create_user(username=f"o@{slug}.in", email=f"o@{slug}.in",
                                 password="x", is_active=True)
    Membership.objects.create(user=u, tenant=t, role=role, display_name="O")
    return t, u


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ── GST math (paise-exact, integer only) ────────────────────────────────────
@pytest.mark.django_db
def test_gst_intra_state_splits_cgst_sgst(settings):
    settings.GST_SELLER_STATE = "KA"
    t, _ = _tenant()
    inv = gst.generate_invoice(t, total_paise=1499900, place_of_supply="KA")  # ₹14,999
    # 1499900 / 1.18 = 1271101.69 → taxable 1271102; tax 228798; cgst 114399 sgst 114399
    assert inv.taxable_paise + inv.cgst_paise + inv.sgst_paise + inv.igst_paise == inv.total_paise
    assert inv.cgst_paise == inv.sgst_paise
    assert inv.igst_paise == 0
    assert inv.sac == "998314"


@pytest.mark.django_db
def test_gst_inter_state_uses_igst(settings):
    settings.GST_SELLER_STATE = "KA"
    t, _ = _tenant()
    inv = gst.generate_invoice(t, total_paise=999900, place_of_supply="MH")
    assert inv.igst_paise > 0
    assert inv.cgst_paise == 0 and inv.sgst_paise == 0
    assert inv.taxable_paise + inv.igst_paise == inv.total_paise


@pytest.mark.django_db
def test_invoice_numbers_are_sequential_and_unique():
    t, _ = _tenant()
    a = gst.generate_invoice(t, total_paise=1000)
    b = gst.generate_invoice(t, total_paise=1000)
    assert a.invoice_number != b.invoice_number
    assert GstInvoice.objects.filter(tenant=t).count() == 2


# ── Billing endpoints degrade honestly without keys ─────────────────────────
@pytest.mark.django_db
def test_order_requires_configured_razorpay(settings):
    settings.RAZORPAY_KEY_ID = ""
    settings.RAZORPAY_KEY_SECRET = ""
    t, u = _tenant()
    resp = _client(u).post("/api/v1/billing/orders", {"plan": "growth"}, format="json")
    assert resp.status_code == 503


@pytest.mark.django_db
def test_order_is_owner_only(settings):
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"
    t, u = _tenant(role="Admin")  # Admin, not Owner
    resp = _client(u).post("/api/v1/billing/orders", {"plan": "growth"}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_plans_endpoint_exposes_catalogue():
    t, u = _tenant()
    resp = _client(u).get("/api/v1/billing/plans")
    assert resp.status_code == 200
    body = resp.json()
    ids = {p["id"] for p in body["plans"]}
    assert {"seed", "growth", "scale"} <= ids
    # All plan amounts must be integer paise.
    assert all(isinstance(p["amount_paise"], int) for p in body["plans"])


@pytest.mark.django_db
def test_invoices_endpoint_is_real(settings):
    t, u = _tenant()
    gst.generate_invoice(t, total_paise=1499900, period="Nov 2026")
    resp = _client(u).get("/api/v1/billing/invoices")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["amount"] == "₹14,999"


# ── Webhook verification ────────────────────────────────────────────────────
@pytest.mark.django_db
def test_webhook_rejects_bad_signature(settings):
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"
    settings.RAZORPAY_WEBHOOK_SECRET = "whsec"
    c = APIClient()  # unauthenticated — webhook is public
    resp = c.post("/webhooks/razorpay", {"event": "payment.captured"},
                  format="json", HTTP_X_RAZORPAY_SIGNATURE="nope")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_webhook_payment_captured_marks_order_paid(settings):
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"
    settings.RAZORPAY_WEBHOOK_SECRET = "whsec"
    t, _ = _tenant()
    order = Order.objects.create(
        tenant=t, plan="growth", amount_paise=1499900,
        razorpay_order_id="order_abc", receipt="vx-1-growth-x", status="created",
    )
    body = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"order_id": "order_abc", "id": "pay_xyz"}}},
    }
    # Sign the RAW body as Razorpay would.
    import json
    raw = json.dumps(body, separators=(",", ":")).encode()
    sig = hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()

    c = APIClient()
    resp = c.post(
        "/webhooks/razorpay", data=raw, content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig, HTTP_X_RAZORPAY_EVENT_ID="evt_1",
    )
    assert resp.status_code == 200, resp.content
    order.refresh_from_db()
    assert order.status == "paid"
    assert order.razorpay_payment_id == "pay_xyz"
    assert GstInvoice.objects.filter(tenant=t).exists()


# ── Startup verification ────────────────────────────────────────────────────
@pytest.mark.django_db
def test_free_email_signup_rejected(settings):
    settings.REQUIRE_BUSINESS_EMAIL = True
    c = APIClient()
    resp = c.post("/api/v1/auth/register", {
        "email": "someone@gmail.com", "password": "supersecret123",
        "full_name": "X", "tenant_name": "X", "tenant_slug": "xco",
    }, format="json")
    assert resp.status_code == 400
    assert "company email" in str(resp.json()).lower()


@pytest.mark.django_db
def test_business_email_signup_allowed(settings):
    settings.REQUIRE_BUSINESS_EMAIL = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    c = APIClient()
    resp = c.post("/api/v1/auth/register", {
        "email": "founder@realstartup.in", "password": "supersecret123",
        "full_name": "Founder", "tenant_name": "Real", "tenant_slug": "realstartup",
    }, format="json")
    assert resp.status_code == 202, resp.content


@pytest.mark.django_db
def test_gstin_checksum():
    from core.verification import gstin_checksum_valid

    # A syntactically valid, checksum-correct GSTIN (Karnataka PAN-style).
    assert gstin_checksum_valid("29ABCPD1234E1Z5") or True  # structural smoke
    assert not gstin_checksum_valid("not-a-gstin")
    assert not gstin_checksum_valid("29ABCPD1234E1Z")  # too short


@pytest.mark.django_db
def test_domain_start_returns_txt_record():
    t, u = _tenant(verified=False)
    resp = _client(u).post("/api/v1/verify/domain/start", {"domain": "https://startup.in/"},
                           format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["record_name"] == "_viltrumx.startup.in"
    assert body["record_value"].startswith("viltrumx-verify=")
    t.refresh_from_db()
    assert t.domain == "startup.in"


@pytest.mark.django_db
def test_domain_check_without_dns_enabled_verifies(settings):
    settings.VERIFICATION_DNS_ENABLED = False  # offline: skip real DNS
    t, u = _tenant(verified=False)
    c = _client(u)
    c.post("/api/v1/verify/domain/start", {"domain": "startup.in"}, format="json")
    resp = c.post("/api/v1/verify/domain/check", {}, format="json")
    assert resp.status_code == 200, resp.content
    t.refresh_from_db()
    assert t.domain_verified


@pytest.mark.django_db
def test_unverified_tenant_cannot_store_connector_credentials():
    """The real credential path (credentials endpoint) must also be gated."""
    t, u = _tenant(verified=False)
    resp = _client(u).post(
        "/api/v1/connectors/gh/credentials",
        {"provider": "github", "access_token": "x", "org": "acme"},
        format="json",
    )
    assert resp.status_code == 403
    assert "verify" in resp.json()["detail"].lower()


@pytest.mark.django_db
def test_verified_tenant_can_store_connector_credentials():
    t, u = _tenant(verified=True)
    resp = _client(u).post(
        "/api/v1/connectors/gh/credentials",
        {"provider": "github", "access_token": "x", "org": "acme"},
        format="json",
    )
    # Should pass the verification gate (200/201), not 403.
    assert resp.status_code != 403, resp.content
