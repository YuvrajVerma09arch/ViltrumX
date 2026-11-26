"""GST invoice generation (P4).

Razorpay's invoice API can only issue non-GST invoices, so we generate the
GST-compliant tax invoice ourselves on each successful charge. Prices are
GST-inclusive; the tax is backed out of the charged amount.

SAC 998314 = "IT software services". Intra-state → CGST 9% + SGST 9%;
inter-state → IGST 18%. The default place of supply is the seller's state
(declared via ``GST_SELLER_STATE``) unless the buyer's GSTIN state code differs.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

from billing.models import GstInvoice

logger = logging.getLogger(__name__)

GST_RATE_PCT = 18
SAC = "998314"


def _split_gst(total_paise: int, place_of_supply: str) -> tuple[int, int, int, int]:
    """Back GST out of a GST-inclusive total.

    Returns (taxable, cgst, sgst, igst) in paise. Integer math, paise-accurate:
    taxable = total / 1.18; tax = total - taxable.
    """
    taxable = round(total_paise * 100 / (100 + GST_RATE_PCT))
    tax = total_paise - taxable
    seller_state = getattr(settings, "GST_SELLER_STATE", "") or ""
    intra = place_of_supply and seller_state and place_of_supply == seller_state
    if intra:
        cgst = tax // 2
        sgst = tax - cgst
        return taxable, cgst, sgst, 0
    return taxable, 0, 0, tax


def generate_invoice(
    tenant,
    *,
    total_paise: int,
    period: str = "",
    place_of_supply: str = "",
    buyer_gstin: str = "",
    razorpay_payment_id: str = "",
    razorpay_order_id: str = "",
) -> GstInvoice:
    """Create and persist a GST invoice for a successful charge."""
    period = period or timezone.now().strftime("%b %Y")
    place_of_supply = place_of_supply or (getattr(settings, "GST_SELLER_STATE", "") or "")
    taxable, cgst, sgst, igst = _split_gst(total_paise, place_of_supply)
    return GstInvoice.objects.create(
        tenant=tenant,
        invoice_number=GstInvoice.next_number(tenant),
        period=period,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_order_id=razorpay_order_id,
        place_of_supply=place_of_supply,
        seller_gstin=getattr(settings, "GST_SELLER_GSTIN", "") or "",
        buyer_gstin=buyer_gstin,
        taxable_paise=taxable,
        cgst_paise=cgst,
        sgst_paise=sgst,
        igst_paise=igst,
        total_paise=total_paise,
        sac=SAC,
        status="paid",
    )
