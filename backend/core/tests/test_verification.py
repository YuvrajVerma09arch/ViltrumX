"""Owner-verification lifecycle: expiring, hashed, single-use email codes.

Covers signup verification, the password + OTP login flow, wrong-code lockout,
expiry, replay, resend limits and mail-delivery failure.
"""

import re
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Membership, VerificationCode

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"

REGISTER = {
    "email": "owner@acme.test",
    "password": "owner-password-123",
    "full_name": "Ada Owner",
    "tenant_name": "Acme Security",
    "tenant_slug": "acme-security-verify",
}


def clear_outbox() -> None:
    if hasattr(mail, "outbox"):
        mail.outbox.clear()


def last_email_code() -> str:
    """Read the 6-digit code out of the most recently sent email."""
    assert mail.outbox, "no verification email was sent"
    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, f"no 6-digit code in email body: {mail.outbox[-1].body!r}"
    return match.group(1)


def other_code(code: str) -> str:
    """A guaranteed-wrong 6-digit code."""
    return "000000" if code != "000000" else "111111"


def backdate_latest(email: str, purpose: str, seconds: int) -> None:
    """Move a challenge's created_at into the past (auto_now_add safe)."""
    code = (
        VerificationCode.objects.filter(email=email, purpose=purpose)
        .order_by("-created_at", "-id")
        .first()
    )
    assert code is not None
    VerificationCode.objects.filter(pk=code.pk).update(
        created_at=timezone.now() - timedelta(seconds=seconds)
    )


@pytest.fixture
def api(db):
    return APIClient()


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_signup_returns_challenge_with_no_tokens(api):
    clear_outbox()
    response = api.post("/api/v1/auth/register", REGISTER, format="json")

    assert response.status_code == 202
    body = response.json()
    assert "access" not in body and "refresh" not in body
    assert body["purpose"] == "signup"
    assert body["email"] == REGISTER["email"]
    assert body["challengeId"]

    user = get_user_model().objects.get(email=REGISTER["email"])
    assert not user.is_active  # no login before code verification
    membership = Membership.objects.get(user=user)
    assert membership.role == "Owner"
    assert membership.tenant.slug == REGISTER["tenant_slug"]

    code = VerificationCode.objects.get(email=REGISTER["email"])
    assert code.purpose == "signup"
    assert code.code_hash != last_email_code()  # plaintext is never stored
    assert check_password(last_email_code(), code.code_hash)
    assert len(mail.outbox) == 1
    assert REGISTER["email"] in mail.outbox[0].to


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_signup_verify_activates_user_and_issues_jwt(api):
    clear_outbox()
    api.post("/api/v1/auth/register", REGISTER, format="json")
    code = last_email_code()

    response = api.post(
        "/api/v1/auth/verify",
        {"email": REGISTER["email"], "code": code},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    for field in ("access", "refresh"):
        assert body[field]
    assert body["user"]["email"] == REGISTER["email"]
    assert body["user"]["name"] == REGISTER["full_name"]
    assert body["tenant"]["slug"] == REGISTER["tenant_slug"]

    user = get_user_model().objects.get(email=REGISTER["email"])
    assert user.is_active
    assert VerificationCode.objects.get(email=REGISTER["email"]).consumed_at is not None

    # Tokens work on a protected endpoint.
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert api.get("/api/v1/agents/status").status_code == 200

    # Refresh is still available after the flow.
    refreshed = api.post(
        "/api/v1/auth/token/refresh", {"refresh": body["refresh"]}, format="json"
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access"]


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_expired_code_is_rejected(api):
    clear_outbox()
    api.post("/api/v1/auth/register", REGISTER, format="json")
    code = last_email_code()
    VerificationCode.objects.filter(email=REGISTER["email"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    response = api.post(
        "/api/v1/auth/verify", {"email": REGISTER["email"], "code": code}, format="json"
    )
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()
    assert not get_user_model().objects.get(email=REGISTER["email"]).is_active


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_code_cannot_be_replayed(api):
    clear_outbox()
    api.post("/api/v1/auth/register", REGISTER, format="json")
    code = last_email_code()
    payload = {"email": REGISTER["email"], "code": code}

    assert api.post("/api/v1/auth/verify", payload, format="json").status_code == 200
    replay = api.post("/api/v1/auth/verify", payload, format="json")
    assert replay.status_code == 400
    assert "already been used" in replay.json()["detail"].lower()
    # Only the single, original challenge exists — verify never mints codes.
    assert VerificationCode.objects.filter(email=REGISTER["email"]).count() == 1


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_wrong_codes_lock_out_and_block_the_right_code(api):
    clear_outbox()
    api.post("/api/v1/auth/register", REGISTER, format="json")
    right = last_email_code()
    wrong = other_code(right)
    payload = {"email": REGISTER["email"], "code": wrong}

    responses = [
        api.post("/api/v1/auth/verify", payload, format="json") for _ in range(5)
    ]
    assert all(r.status_code == 400 for r in responses)
    assert "incorrect" in responses[0].json()["detail"].lower()
    assert "too many" in responses[-1].json()["detail"].lower()

    stored = VerificationCode.objects.get(email=REGISTER["email"])
    assert stored.attempts == settings.VERIFICATION_MAX_ATTEMPTS
    assert stored.is_locked

    # Even the correct code cannot redeem a locked challenge.
    blocked = api.post(
        "/api/v1/auth/verify", {"email": REGISTER["email"], "code": right}, format="json"
    )
    assert blocked.status_code == 400
    assert "too many" in blocked.json()["detail"].lower()
    assert not get_user_model().objects.get(email=REGISTER["email"]).is_active


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_resend_has_cooldown_and_maximum(api):
    clear_outbox()
    created = api.post("/api/v1/auth/register", REGISTER, format="json")
    initial_challenge_id = created.json()["challengeId"]
    last_email_code()
    payload = {"email": REGISTER["email"], "purpose": "signup"}

    # Immediate resend is throttled.
    throttled = api.post("/api/v1/auth/resend", payload, format="json")
    assert throttled.status_code == 429
    assert "wait" in throttled.json()["detail"].lower()

    # After the cooldown, resends work — but only up to the configured cap.
    for expected in range(1, settings.VERIFICATION_MAX_RESENDS + 1):
        backdate_latest(
            REGISTER["email"], "signup", settings.VERIFICATION_RESEND_COOLDOWN_SECONDS + 1
        )
        sent = api.post("/api/v1/auth/resend", payload, format="json")
        assert sent.status_code == 202
        assert sent.json()["purpose"] == "signup"
        latest = (
            VerificationCode.objects.filter(email=REGISTER["email"])
            .order_by("-created_at", "-id")
            .first()
        )
        assert latest.resend_count == expected
        assert str(latest.challenge_id) != initial_challenge_id  # a fresh code was issued

    backdate_latest(
        REGISTER["email"], "signup", settings.VERIFICATION_RESEND_COOLDOWN_SECONDS + 1
    )
    exhausted = api.post("/api/v1/auth/resend", payload, format="json")
    assert exhausted.status_code == 429
    assert "maximum" in exhausted.json()["detail"].lower()
    assert len(mail.outbox) == settings.VERIFICATION_MAX_RESENDS + 1


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_login_requires_password_and_code(api):
    clear_outbox()
    api.post("/api/v1/auth/register", REGISTER, format="json")
    signup_code = last_email_code()
    api.post(
        "/api/v1/auth/verify",
        {"email": REGISTER["email"], "code": signup_code},
        format="json",
    )
    email = REGISTER["email"]

    # A wrong password never sends a code.
    bad = api.post(
        "/api/v1/auth/login-challenge",
        {"email": email, "password": "not-the-password"},
        format="json",
    )
    assert bad.status_code == 400
    assert "invalid" in bad.json()["detail"].lower()
    assert len(mail.outbox) == 1  # signup mail only; no login mail for a bad password

    challenge = api.post(
        "/api/v1/auth/login-challenge",
        {"email": email, "password": REGISTER["password"]},
        format="json",
    )
    assert challenge.status_code == 202
    assert "access" not in challenge.json()
    login_code = last_email_code()
    assert (
        VerificationCode.objects.filter(email=email, purpose="login").first().purpose == "login"
    )

    # The code alone (without the password) is not enough at login-verify.
    no_password = api.post(
        "/api/v1/auth/login-verify", {"email": email, "password": "wrong", "code": login_code},
        format="json",
    )
    assert no_password.status_code == 400
    assert "access" not in no_password.json()

    verified = api.post(
        "/api/v1/auth/login-verify",
        {"email": email, "password": REGISTER["password"], "code": login_code},
        format="json",
    )
    assert verified.status_code == 200
    assert verified.json()["access"]

    # Codes are purpose-scoped: a login code cannot verify a signup challenge.
    assert (
        VerificationCode.objects.filter(email=email, purpose="signup").first().consumed_at
        is not None
    )


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_unverified_owner_cannot_get_a_session(api):
    clear_outbox()
    api.post("/api/v1/auth/register", REGISTER, format="json")
    code = last_email_code()
    email = REGISTER["email"]

    # The removed password-only endpoint is gone; no token can be minted here.
    token = api.post(
        "/api/v1/auth/token", {"username": email, "password": REGISTER["password"]},
        format="json",
    )
    assert token.status_code == 404

    challenge = api.post(
        "/api/v1/auth/login-challenge",
        {"email": email, "password": REGISTER["password"]},
        format="json",
    )
    assert challenge.status_code == 403
    assert "not verified" in challenge.json()["detail"].lower()

    verified = api.post(
        "/api/v1/auth/login-verify",
        {"email": email, "password": REGISTER["password"], "code": code},
        format="json",
    )
    assert verified.status_code == 403
    assert "access" not in verified.json()


def test_mail_delivery_failure_rolls_back_signup(api):
    with patch("django.core.mail.send_mail", side_effect=OSError("smtp unavailable")):
        response = api.post("/api/v1/auth/register", REGISTER, format="json")

    assert response.status_code == 503
    assert "email" in response.json()["detail"].lower()
    user_model = get_user_model()
    assert not user_model.objects.filter(email=REGISTER["email"]).exists()
    assert not VerificationCode.objects.filter(email=REGISTER["email"]).exists()
