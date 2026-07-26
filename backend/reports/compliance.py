"""
CERT-In and DPDP compliance evidence export (Week 4).

One done well beats four done shallow (BUILD-PLAN §4 Week 4 step 4).
CERT-In is the primary: 6 legally required fields, pulled from the
provenance trace, bilingual EN/HI.
"""

from django.utils import timezone

from core import demo_data

KNOWN_FRAMEWORKS = {f["id"]: f for f in demo_data.FRAMEWORKS}


def generate_export(tenant, framework_id: str, actor: str):
    if framework_id not in KNOWN_FRAMEWORKS:
        return None

    from reports.models import ComplianceExport

    now = timezone.now()
    if framework_id == "certin":
        content = _certin_pack(tenant, now)
        name = f"CERT-In incident report — {now.strftime('%d %b %Y')}"
        kind = "PDF · bilingual EN/HI"
    elif framework_id == "dpdp":
        content = _dpdp_pack(tenant, now)
        name = f"DPDP evidence pack — {now.strftime('%B %Y')}"
        kind = "PDF + JSON manifest"
    else:
        content = {"framework": framework_id, "generated_at": now.isoformat()}
        name = f"{KNOWN_FRAMEWORKS[framework_id]['name']} export — {now.strftime('%B %Y')}"
        kind = "PDF"

    export = ComplianceExport.objects.create(
        tenant=tenant,
        framework_id=framework_id,
        name=name,
        kind=kind,
        when_label=now.strftime("today %H:%M IST"),
        content=content,
    )
    return {"name": export.name, "kind": export.kind, "when": export.when_label}


def _certin_pack(tenant, now) -> dict:
    """
    CERT-In Directions 2022 — 6 mandatory fields for a reportable incident.
    Pulled from the INC-042 provenance trace.
    """
    from actions.models import Action
    from core.models import Incident

    incident = Incident.objects.filter(tenant=tenant, external_id="INC-042").first()
    actions = list(
        Action.objects.filter(tenant=tenant, incident=incident).order_by("created_at")
    ) if incident else []

    return {
        "framework": "CERT-In Directions 2022",
        "report_type": "Cyber Security Incident Report",
        "fields": {
            "1_incident_type": "Unauthorised access to IT systems / data",
            "2_date_time_of_incident": (
                incident.occurred_at.strftime("%d %b %Y %H:%M IST") if incident
                else now.strftime("%d %b %Y %H:%M IST")
            ),
            "3_date_time_of_detection": now.strftime("%d %b %Y %H:%M IST"),
            "4_affected_systems": [
                "Google Workspace (priya.sharma@paykraft.in)",
                "GitHub (paykraft-infra repository)",
                "AWS S3 (customers-db-backups)",
            ],
            "5_nature_of_incident": (
                "Credential compromise via impossible-travel login and MFA fatigue. "
                "Attacker minted a GitHub PAT, recovered an AWS key from repository history, "
                "and attempted bulk exfiltration of 412k customer PII records. "
                "Session revoked and key rotated mid-transfer; zero records exfiltrated."
            ),
            "6_actions_taken": [
                f"{a.action_type} on {a.target} ({a.level}, {a.status})"
                for a in actions
            ] or [
                "revoke_session on priya.sharma (L2, executed)",
                "rotate_key on AWS AKIA···X7Q (L2, executed)",
                "block_ip on 185.220.101.34 (L3, executed — auto-rollback 1h)",
                "disable_identity proposed (L4, awaiting founder approval)",
            ],
        },
        "reporting_window_hours": 6,
        "generated_at": now.isoformat(),
        "generated_by": "ViltrumX automated evidence pack",
        "hindi_summary": (
            "यह रिपोर्ट CERT-In निर्देश 2022 के अनुसार तैयार की गई है। "
            "घटना INC-042: priya.sharma का खाता मास्को से अनधिकृत रूप से एक्सेस किया गया। "
            "ViltrumX ने सत्र रद्द किया और AWS कुंजी बदली — कोई डेटा बाहर नहीं गया।"
        ),
    }


def _dpdp_pack(tenant, now) -> dict:
    return {
        "framework": "Digital Personal Data Protection Act 2023",
        "obligations_phase": "Phase 1 (in force Nov 2025)",
        "data_fiduciary": tenant.name,
        "personal_data_involved": (
            "Customer PII — 412k records (names, contact, transaction history)"
        ),
        "breach_occurred": False,
        "breach_prevented_by": "ViltrumX automated containment (session revoke + key rotation)",
        "notification_required": False,
        "notification_reason": "No personal data was exfiltrated — breach was prevented",
        "controls_mapped": 42,
        "controls_total": 47,
        "gap_list": [
            "Data retention policy not yet formalised in system",
            "Consent management module not yet integrated",
            "Data localisation audit pending for Razorpay settlement data",
            "Grievance officer appointment not yet recorded",
            "Cross-border transfer assessment pending",
        ],
        "generated_at": now.isoformat(),
    }
