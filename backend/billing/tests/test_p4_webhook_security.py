"""Temporary adversarial probes for the Razorpay webhook. Deleted after run."""

import hashlib
import hmac
import json

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from billing.models import Order, WebhookEvent
from core.models import Membership, Tenant


def _tenant(slug="adv", role="Owner"):
    t = Tenant.objects.create(name=slug.title(), slug=slug)
    u = User.objects.create_user(
        username=f"o@{slug}.in", email=f"o@{slug}.in", password="x", is_active=True
    )
    Membership.objects.create(user=u, tenant=t, role=role, display_name="O")
    return t, u


def _order(t, oid="order_adv", status="created"):
    return Order.objects.create(
        tenant=t,
        plan="growth",
        amount_paise=1499900,
        razorpay_order_id=oid,
        receipt=f"vx-{oid}",
        status=status,
    )


def _sign(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _post(c, raw, sig=None, event_id=None):
    headers = {}
    if sig is not None:
        headers["HTTP_X_RAZORPAY_SIGNATURE"] = sig
    if event_id is not None:
        headers["HTTP_X_RAZORPAY_EVENT_ID"] = event_id
    return c.post("/webhooks/razorpay", data=raw, content_type="application/json", **headers)


@pytest.fixture
def cfg(settings):
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"
    settings.RAZORPAY_WEBHOOK_SECRET = "whsec"
    return settings


@pytest.mark.django_db
def test_valid_sig_marks_paid(cfg):
    t, _ = _tenant()
    _order(t)
    raw = json.dumps(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_adv", "id": "pay_1"}}},
        },
        separators=(",", ":"),
    ).encode()
    r = _post(APIClient(), raw, _sign(raw, "whsec"), "evt_ok")
    assert r.status_code == 200, r.content
    assert Order.objects.get(razorpay_order_id="order_adv").status == "paid"


@pytest.mark.django_db
def test_tampered_body_after_signing_rejected(cfg):
    """Sign ORIGINAL body, then flip a byte — raw body hash must not match."""
    t, _ = _tenant()
    _order(t, oid="order_tamper")
    raw = json.dumps(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_tamper", "id": "pay_1"}}},
        },
        separators=(",", ":"),
    ).encode()
    sig = _sign(raw, "whsec")
    tampered = raw.replace(b"pay_1", b"pay_9")
    r = _post(APIClient(), tampered, sig, "evt_t")
    assert r.status_code == 401, r.content
    assert Order.objects.get(razorpay_order_id="order_tamper").status == "created"


@pytest.mark.django_db
def test_signature_over_parsed_subset_cannot_bypass(cfg):
    """Attack: sign a *different* body that a naive parser would treat the same.
    Reordered/whitespaced JSON must still be rejected because RAW bytes differ."""
    t, _ = _tenant()
    _order(t, oid="order_reorder")
    canonical = b'{"event":"payment.captured","payload":{"payment":{"entity":{"order_id":"order_reorder","id":"pay_1"}}}}'  # noqa: E501 — raw JSON bytes; whitespace is significant for HMAC
    sig = _sign(canonical, "whsec")
    # Same semantic JSON, different byte serialization.
    different = b'{ "event": "payment.captured", "payload": { "payment": { "entity": { "order_id": "order_reorder", "id": "pay_1" } } } }'  # noqa: E501 — raw JSON bytes; whitespace is significant for HMAC
    r = _post(APIClient(), different, sig, "evt_r")
    assert r.status_code == 401, r.content
    assert Order.objects.get(razorpay_order_id="order_reorder").status == "created"


@pytest.mark.django_db
def test_dedupe_same_event_id(cfg):
    t, _ = _tenant()
    _order(t, oid="order_dup")
    raw = json.dumps(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_dup", "id": "pay_1"}}},
        },
        separators=(",", ":"),
    ).encode()
    sig = _sign(raw, "whsec")
    r1 = _post(APIClient(), raw, sig, "evt_dup")
    r2 = _post(APIClient(), raw, sig, "evt_dup")
    assert r1.status_code == 200
    assert r2.status_code == 200 and r2.json().get("status") == "duplicate", r2.content
    assert WebhookEvent.objects.filter(event_id="evt_dup").count() == 1


@pytest.mark.django_db
def test_payment_failed_does_not_lock(cfg):
    t, _ = _tenant()
    _order(t, oid="order_fail", status="created")
    fail = json.dumps(
        {
            "event": "payment.failed",
            "payload": {"payment": {"entity": {"order_id": "order_fail", "id": "pay_bad"}}},
        },
        separators=(",", ":"),
    ).encode()
    r = _post(APIClient(), fail, _sign(fail, "whsec"), "evt_fail")
    assert r.status_code == 200, r.content
    o = Order.objects.get(razorpay_order_id="order_fail")
    assert o.status == "created", f"payment.failed must NOT lock; got {o.status}"
    assert o.razorpay_payment_id == ""
    # A later capture on the same order still pays (UPI retry).
    cap = json.dumps(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_fail", "id": "pay_good"}}},
        },
        separators=(",", ":"),
    ).encode()
    r2 = _post(APIClient(), cap, _sign(cap, "whsec"), "evt_cap")
    assert r2.status_code == 200
    o.refresh_from_db()
    assert o.status == "paid" and o.razorpay_payment_id == "pay_good"


@pytest.mark.django_db
def test_absent_signature_rejected(cfg):
    t, _ = _tenant()
    _order(t, oid="order_nosig")
    raw = b'{"event":"payment.captured"}'
    r = _post(APIClient(), raw, None, "evt_n")
    assert r.status_code == 401


@pytest.mark.django_db
def test_no_webhook_secret_fails_closed(settings):
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"
    settings.RAZORPAY_WEBHOOK_SECRET = ""
    t, _ = _tenant()
    _order(t, oid="order_nosec")
    raw = b'{"event":"payment.captured"}'
    # Even a "correctly" signed-with-empty body must be rejected when unconfigured.
    r = _post(APIClient(), raw, _sign(raw, ""), "evt_s")
    assert r.status_code == 401, r.content


@pytest.mark.django_db
def test_wrong_secret_rejected(cfg):
    t, _ = _tenant()
    _order(t, oid="order_wrongsec")
    raw = json.dumps(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_wrongsec", "id": "pay_1"}}},
        },
        separators=(",", ":"),
    ).encode()
    r = _post(APIClient(), raw, _sign(raw, "ATTACKER_SECRET"), "evt_ws")
    assert r.status_code == 401, r.content
    assert Order.objects.get(razorpay_order_id="order_wrongsec").status == "created"


@pytest.mark.django_db
def test_dedupe_inserted_before_fulfil_failure_loses_payment(cfg, monkeypatch):
    """Probe: if fulfilment raises AFTER dedupe row is committed, a Razorpay retry
    is swallowed as 'duplicate' and the order is never paid."""
    t, _ = _tenant()
    _order(t, oid="order_lost")
    raw = json.dumps(
        {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": "order_lost", "id": "pay_1"}}},
        },
        separators=(",", ":"),
    ).encode()
    sig = _sign(raw, "whsec")
    from billing import views as bv

    boom = {"n": 0}
    orig = bv.RazorpayWebhookView._fulfil

    def flaky(self, order_id, payment_id):
        boom["n"] += 1
        raise RuntimeError("transient DB blip")

    monkeypatch.setattr(bv.RazorpayWebhookView, "_fulfil", flaky)
    c = APIClient()
    c.raise_request_exception = False
    r1 = _post(c, raw, sig, "evt_lost")
    # If view propagates the exception -> 500 (no dedupe commit would matter if same txn)
    print("FIRST STATUS", r1.status_code)
    # Retry as Razorpay would:
    monkeypatch.setattr(bv.RazorpayWebhookView, "_fulfil", orig)
    r2 = _post(c, raw, sig, "evt_lost")
    print("RETRY STATUS", r2.status_code, r2.json() if r2.status_code == 200 else r2.content)
    print("ORDER STATUS", Order.objects.get(razorpay_order_id="order_lost").status)
    print("EVENT ROW EXISTS", WebhookEvent.objects.filter(event_id="evt_lost").exists())
