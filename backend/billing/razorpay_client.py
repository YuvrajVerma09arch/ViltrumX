"""Razorpay client singleton + plan catalogue (P4).

Mirrors the SkillMap reference (`create_order` / `verify_payment_signature`), but
reads keys from Django settings (env-sourced) and works in integer paise.
"""

from __future__ import annotations

import logging

import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


def is_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def get_client() -> razorpay.Client | None:
    """Return a configured Razorpay client, or None when keys are absent."""
    global _client
    if not is_configured():
        return None
    if _client is None:
        _client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    return _client


# Plan catalogue — INR, GST-inclusive prices. Keep the entry tier under the
# ₹15,000 RBI e-mandate no-AFA threshold so monthly auto-debit needs no bank
# AFA each cycle. (Growth/Scale above 15k would require bank AFA per charge.)
PLANS = {
    "seed": {"name": "Seed", "amount_inr": 9999, "tier": "Seed"},
    "growth": {"name": "Growth", "amount_inr": 14999, "tier": "Growth"},
    "scale": {"name": "Scale", "amount_inr": 74999, "tier": "Scale"},
}


def plan_amount_paise(plan: str) -> int | None:
    p = PLANS.get(plan)
    return p["amount_inr"] * 100 if p else None


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Server-side HMAC check that the payment really came from Razorpay."""
    client = get_client()
    if client is None:
        return False
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Razorpay signature verify failed: %s", exc)
        return False


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify a webhook over the RAW body against the webhook secret."""
    secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "") or ""
    client = get_client()
    if client is None or not secret:
        return False
    try:
        client.utility.verify_webhook_signature(
            body.decode(), signature, secret
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Razorpay webhook verify failed: %s", exc)
        return False
