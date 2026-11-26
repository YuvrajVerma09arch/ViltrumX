"""Billing API (P4): create order, verify payment, webhook, invoices.

Follows Razorpay's live-mode guidance:
  * order amounts are integer paise; receipts are ASCII+unique (idempotency key);
  * verify is idempotent (select_for_update; a replayed verify never double-credits);
  * the webhook verifies the RAW body against X-Razorpay-Signature and dedupes on
    X-Razorpay-Event-Id; payment.failed does NOT lock the order (UPI retry can
    still capture).
Keys come from settings (env). With no keys the endpoints return 503 — honest,
never a fake success.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import gst, razorpay_client
from billing.models import GstInvoice, Order, WebhookEvent
from core.tenancy import role_for, tenant_for

logger = logging.getLogger(__name__)


class _TenantView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = tenant_for(request)


def _to_inr(paise: int) -> str:
    return f"₹{paise // 100:,}"


class CreateOrderView(_TenantView):
    """Create a Razorpay order for a plan. Billing is Owner-only."""

    def post(self, request):
        if role_for(request, self.tenant) != "Owner":
            return Response({"detail": "Billing is Owner-only."}, status=403)
        plan = (request.data.get("plan") or "").strip().lower()
        amount = razorpay_client.plan_amount_paise(plan)
        if amount is None:
            return Response(
                {"detail": f"Unknown plan. Choose one of {list(razorpay_client.PLANS)}."},
                status=400,
            )
        client = razorpay_client.get_client()
        if client is None:
            return Response({"detail": "Billing is not configured."}, status=503)

        # Unique ASCII receipt acts as the idempotency key (<=40 chars).
        receipt = f"vx-{self.tenant.id}-{plan}-{int(timezone.now().timestamp())}"[:40]
        try:
            order = client.order.create({
                "amount": amount,
                "currency": "INR",
                "receipt": receipt,
                "notes": {"tenant_id": str(self.tenant.id), "plan": plan},
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("Razorpay order create failed")
            return Response({"detail": f"Could not create order: {exc}"}, status=502)

        Order.objects.create(
            tenant=self.tenant,
            plan=plan,
            amount_paise=amount,
            razorpay_order_id=order["id"],
            receipt=receipt,
            notes={"plan": plan},
            status="created",
        )
        # Return the PUBLIC key id only — never the secret.
        return Response(
            {
                "order_id": order["id"],
                "amount": amount,
                "currency": "INR",
                "key_id": settings.RAZORPAY_KEY_ID,
                "plan": plan,
                "prefill": {"email": request.user.email},
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyPaymentView(_TenantView):
    """Verify a payment signature after Checkout; mark the order paid (once)."""

    def post(self, request):
        if role_for(request, self.tenant) != "Owner":
            return Response({"detail": "Billing is Owner-only."}, status=403)
        oid = (request.data.get("razorpay_order_id") or "").strip()
        pid = (request.data.get("razorpay_payment_id") or "").strip()
        sig = (request.data.get("razorpay_signature") or "").strip()
        if not (oid and pid and sig):
            return Response({"detail": "Missing payment parameters."}, status=400)

        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .filter(tenant=self.tenant, razorpay_order_id=oid)
                .first()
            )
            if order is None:
                return Response({"detail": "Order not found."}, status=404)
            if order.status == "paid":
                # Idempotent: a replayed verify must not re-provision.
                return Response({"status": "already_verified"})

            if not razorpay_client.verify_payment_signature(oid, pid, sig):
                order.status = "failed"
                order.save(update_fields=["status"])
                return Response({"status": "failed", "detail": "Invalid signature"}, status=400)

            order.status = "paid"
            order.razorpay_payment_id = pid
            order.paid_at = timezone.now()
            order.save(update_fields=["status", "razorpay_payment_id", "paid_at"])

        gst.generate_invoice(
            self.tenant,
            total_paise=order.amount_paise,
            razorpay_payment_id=pid,
            razorpay_order_id=oid,
            buyer_gstin=request.data.get("gstin", ""),
            place_of_supply=request.data.get("place_of_supply", ""),
        )
        return Response({"status": "success", "plan": order.plan, "amount": order.amount_paise})


@method_decorator(csrf_exempt, name="dispatch")
class RazorpayWebhookView(APIView):
    """Webhook: verify RAW body, dedupe on event id, fulfill idempotently."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.body  # RAW bytes — verify before parsing
        sig = request.headers.get("X-Razorpay-Signature", "")
        if not razorpay_client.verify_webhook_signature(body, sig):
            return Response({"detail": "Invalid signature."}, status=401)

        payload = request.data or {}
        event = payload.get("event", "")
        entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
        order_id = entity.get("order_id")
        payment_id = entity.get("id")
        event_id = request.headers.get("X-Razorpay-Event-Id", "")

        # Dedupe row + fulfilment are committed in ONE transaction. If fulfilment
        # fails, the dedupe row rolls back too, so Razorpay's retry is not
        # swallowed as a 'duplicate' and the payment is not lost.
        try:
            with transaction.atomic():
                if event_id:
                    _, created = WebhookEvent.objects.get_or_create(
                        event_id=event_id, defaults={"event_type": event}
                    )
                    if not created:
                        return Response({"status": "duplicate"})
                if event == "payment.captured" and order_id:
                    self._fulfil(order_id, payment_id)
        except Exception as exc:  # noqa: BLE001
            # Non-2xx so Razorpay retries the delivery.
            logger.exception("Webhook fulfilment failed for %s", event_id)
            return Response({"detail": f"fulfilment failed: {exc}"}, status=500)

        # payment.failed intentionally does NOT lock the order (UPI retry can still capture).
        return Response({"status": "ok"})

    @staticmethod
    def _fulfil(order_id: str, payment_id: str):
        order = (
            Order.objects.select_for_update()
            .filter(razorpay_order_id=order_id)
            .first()
        )
        if order is None or order.status == "paid":
            return
        order.status = "paid"
        order.razorpay_payment_id = payment_id or ""
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "razorpay_payment_id", "paid_at"])
        gst.generate_invoice(
            order.tenant,
            total_paise=order.amount_paise,
            razorpay_payment_id=payment_id or "",
            razorpay_order_id=order_id,
        )


class BillingPlansView(_TenantView):
    """The plan catalogue + whether billing is live (for the UI)."""

    def get(self, request):
        return Response(
            {
                "configured": razorpay_client.is_configured(),
                "plans": [
                    {"id": key, "name": p["name"], "amount_paise": p["amount_inr"] * 100,
                     "amount_inr": p["amount_inr"]}
                    for key, p in razorpay_client.PLANS.items()
                ],
            }
        )


class RealInvoiceListView(_TenantView):
    """Real GST invoices for this tenant (replaces the demo fixture endpoint)."""

    def get(self, request):
        rows = GstInvoice.objects.filter(tenant=self.tenant)[:50]
        return Response(
            [
                {
                    "id": inv.invoice_number,
                    "period": inv.period,
                    "amount": _to_inr(inv.total_paise),
                    "gst": "GST 18% incl.",
                    "status": inv.status,
                }
                for inv in rows
            ]
        )
