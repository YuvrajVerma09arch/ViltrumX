"""
Billing models (P4) — Razorpay orders, subscriptions, GST invoices.

Money is stored as integer **paise** everywhere (₹1 = 100 paise) — never floats.
A one-off ``Order`` covers annual/one-time payments; a ``Subscription`` covers
monthly INR billing (Razorpay Subscriptions, RBI e-mandate aware). A ``GstInvoice``
is generated in Django from the charge details because Razorpay's own invoice API
only issues non-GST invoices.
"""

from django.db import models

from core.models import Tenant


class Order(models.Model):
    STATUS = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="orders")
    plan = models.CharField(max_length=40)
    amount_paise = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    razorpay_order_id = models.CharField(max_length=64, unique=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS, default="created")
    receipt = models.CharField(max_length=40, unique=True)
    notes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.receipt} {self.plan} ₹{self.amount_paise / 100:.0f} [{self.status}]"


class Subscription(models.Model):
    STATUS = [
        ("created", "Created"),
        ("active", "Active"),
        ("halted", "Halted"),
        ("cancelled", "Cancelled"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="subscriptions")
    plan_id = models.CharField(max_length=64)  # Razorpay plan id
    plan = models.CharField(max_length=40)  # our plan slug
    razorpay_subscription_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=STATUS, default="created")
    current_start = models.DateTimeField(null=True, blank=True)
    current_end = models.DateTimeField(null=True, blank=True)
    charge_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"sub {self.razorpay_subscription_id} [{self.status}]"


class GstInvoice(models.Model):
    """A GST-compliant tax invoice we generate ourselves on each charge.

    Prices are GST-inclusive; we back the tax out of the charged amount.
    SAC 998314 (IT software services). CGST+SGST when the place of supply is the
    seller's state, otherwise IGST.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="gst_invoices")
    invoice_number = models.CharField(max_length=32, unique=True)
    period = models.CharField(max_length=40)  # "Nov 2026"
    razorpay_payment_id = models.CharField(max_length=64, blank=True, default="")
    razorpay_order_id = models.CharField(max_length=64, blank=True, default="")
    place_of_supply = models.CharField(max_length=60, blank=True, default="")
    seller_gstin = models.CharField(max_length=15, blank=True, default="")
    buyer_gstin = models.CharField(max_length=15, blank=True, default="")
    taxable_paise = models.BigIntegerField(default=0)
    cgst_paise = models.BigIntegerField(default=0)
    sgst_paise = models.BigIntegerField(default=0)
    igst_paise = models.BigIntegerField(default=0)
    total_paise = models.BigIntegerField(default=0)
    sac = models.CharField(max_length=8, default="998314")
    status = models.CharField(max_length=10, default="paid")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} ₹{self.total_paise / 100:.0f} ({self.period})"

    @classmethod
    def next_number(cls, tenant) -> str:
        """Sequential per fiscal-ish counter: VX-<slug>-0001."""
        count = cls.objects.filter(tenant=tenant).count() + 1
        return f"VX-{tenant.slug.upper()[:8]}-{count:04d}"[:32]


class WebhookEvent(models.Model):
    """Idempotency ledger for Razorpay webhook deliveries (X-Razorpay-Event-Id)."""

    event_id = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=60, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type}:{self.event_id[:20]}"
