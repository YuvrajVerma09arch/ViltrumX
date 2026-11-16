"""
API v1 — real implementations over the Week-1 ledger (Postgres), the Week-2
ontology (Neo4j with a Postgres-mirror fallback), Week-3 detection scores,
and Week-4 reports. Response shapes match frontend/src/data/mock.ts exactly
(camelCase — the built frontend depends on them).
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail as django_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from actions import executor
from actions.models import Action, AutonomyPolicy
from core import demo_data
from core.models import AgentState, FeedLine, Incident, Membership, VerificationCode
from core.serializers import (
    ActionSerializer,
    AgentStateSerializer,
    AttackStepSerializer,
    EvidenceSerializer,
    FeedLineSerializer,
    IncidentSerializer,
    LoginChallengeSerializer,
    LoginVerifySerializer,
    MemberSerializer,
    ProvenanceStepSerializer,
    RegisterSerializer,
    ResendSerializer,
    VerifySerializer,
)
from core.tenancy import tenant_for


class VerificationEmailError(Exception):
    """The one-time code could not be delivered — do not leave a pending challenge."""


def _send_verification_email(email: str, raw_code: str, purpose: str) -> None:
    """Send the plaintext code over email. Never log or persist the plaintext."""
    label = "signup" if purpose == "signup" else "login"
    minutes = settings.VERIFICATION_CODE_TTL_SECONDS // 60
    try:
        django_mail.send_mail(
            subject=f"Your ViltrumX {label} verification code",
            message=(
                f"Your ViltrumX verification code is {raw_code}.\n\n"
                f"It expires in {minutes} minute(s) and can be used once. "
                "If you did not request it, you can ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        raise VerificationEmailError("verification email delivery failed") from exc


def _issue_verification_code(email: str, purpose: str, resend_count: int = 0):
    """Create a fresh hashed code, superseding any pending one for this email.

    Callers wrap this in ``transaction.atomic()`` so a mail failure rolls back
    both the new code and the invalidation of the previous one.
    """
    email = (email or "").strip().lower()
    now = timezone.now()
    VerificationCode.objects.filter(
        email=email, purpose=purpose, consumed_at__isnull=True
    ).update(consumed_at=now)
    raw_code = f"{secrets.randbelow(1_000_000):06d}"
    code = VerificationCode.objects.create(
        email=email,
        code_hash=make_password(raw_code),
        purpose=purpose,
        expires_at=now + timedelta(seconds=settings.VERIFICATION_CODE_TTL_SECONDS),
        resend_count=resend_count,
    )
    return code, raw_code


def _latest_code(email: str, purpose: str):
    return (
        VerificationCode.objects.filter(email=(email or "").strip().lower(), purpose=purpose)
        .order_by("-created_at", "-id")
        .first()
    )


def _consume_code(email: str, purpose: str, raw_code: str):
    """Atomically validate + consume a code. Returns (code, error_message)."""
    with transaction.atomic():
        code = (
            VerificationCode.objects.select_for_update()
            .filter(email=(email or "").strip().lower(), purpose=purpose)
            .order_by("-created_at", "-id")
            .first()
        )
        if code is None:
            return None, "No verification challenge found. Request a new code."
        if code.consumed_at is not None:
            return None, "This verification code has already been used. Request a new one."
        if code.is_expired:
            return None, "This verification code has expired. Request a new one."
        if code.is_locked:
            return None, "Too many incorrect attempts. Request a new code."
        if not code.check_code(raw_code):
            code.attempts += 1
            code.save(update_fields=["attempts"])
            remaining = max(settings.VERIFICATION_MAX_ATTEMPTS - code.attempts, 0)
            if remaining == 0:
                return None, "Too many incorrect attempts. Request a new code."
            return None, f"Incorrect verification code. {remaining} attempt(s) remaining."
        code.consumed_at = timezone.now()
        code.save(update_fields=["consumed_at"])
        return code, None


def _token_payload(user) -> dict:
    """Same access/refresh/user/tenant shape the pre-verification login returned."""
    membership = Membership.objects.filter(user=user).order_by("id").first()
    refresh = RefreshToken.for_user(user)
    payload = {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {"id": user.id, "email": user.email, "name": user.username},
    }
    if membership:
        payload["user"]["name"] = membership.display_name
        payload["tenant"] = {
            "id": membership.tenant.id,
            "name": membership.tenant.name,
            "slug": membership.tenant.slug,
        }
    return payload


def _challenge_payload(code, email: str, purpose: str) -> dict:
    return {
        "challengeId": str(code.challenge_id),
        "email": email.strip().lower(),
        "purpose": purpose,
    }


class RegisterView(APIView):
    """Public: founder signup → inactive User + Tenant + Owner + emailed code.

    No JWT is issued here. The account is activated only by ``VerifyView``.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            with transaction.atomic():
                serializer.save()
                code, raw_code = _issue_verification_code(email, "signup")
                _send_verification_email(email, raw_code, "signup")
        except VerificationEmailError:
            return Response(
                {"detail": "Could not deliver the verification email. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(_challenge_payload(code, email, "signup"), status=status.HTTP_202_ACCEPTED)


class VerifyView(APIView):
    """Public: exchange an emailed signup code for a session and activate the owner."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code, error = _consume_code(email, "signup", serializer.validated_data["code"])
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            return Response(
                {"detail": "No verification challenge found. Request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
        return Response(_token_payload(user), status=status.HTTP_200_OK)


class LoginChallengeView(APIView):
    """Public: verify the password, then email a one-time login code (no JWT yet)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginChallengeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.check_password(serializer.validated_data["password"]):
            return Response(
                {"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user.is_active:
            return Response(
                {"detail": "Account not verified. Use the signup code sent to your email."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            with transaction.atomic():
                code, raw_code = _issue_verification_code(email, "login")
                _send_verification_email(user.email, raw_code, "login")
        except VerificationEmailError:
            return Response(
                {"detail": "Could not deliver the verification email. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(_challenge_payload(code, email, "login"), status=status.HTTP_202_ACCEPTED)


class LoginVerifyView(APIView):
    """Public: re-check password + consume the emailed code, then issue the JWT."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.check_password(serializer.validated_data["password"]):
            return Response(
                {"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user.is_active:
            return Response(
                {"detail": "Account not verified. Use the signup code sent to your email."},
                status=status.HTTP_403_FORBIDDEN,
            )
        _, error = _consume_code(email, "login", serializer.validated_data["code"])
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_token_payload(user), status=status.HTTP_200_OK)


class ResendView(APIView):
    """Public: re-email a pending code, bounded by a cooldown and a resend cap."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        purpose = serializer.validated_data["purpose"]
        latest = _latest_code(email, purpose)
        if latest is None or latest.consumed_at is not None:
            return Response(
                {"detail": "No pending verification to resend."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cooldown = settings.VERIFICATION_RESEND_COOLDOWN_SECONDS
        elapsed = (timezone.now() - latest.created_at).total_seconds()
        if elapsed < cooldown:
            wait = int(cooldown - elapsed) + 1
            return Response(
                {"detail": f"Please wait {wait} second(s) before requesting another code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if latest.resend_count >= settings.VERIFICATION_MAX_RESENDS:
            return Response(
                {"detail": "Maximum resend limit reached. Request a new challenge."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            with transaction.atomic():
                code, raw_code = _issue_verification_code(
                    email, purpose, resend_count=latest.resend_count + 1
                )
                _send_verification_email(email, raw_code, purpose)
        except VerificationEmailError:
            return Response(
                {"detail": "Could not deliver the verification email. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(_challenge_payload(code, email, purpose), status=status.HTTP_202_ACCEPTED)


class TenantAPIView(APIView):
    """Base: resolves the caller's tenant once per request."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = tenant_for(request)


# ── Command Deck ─────────────────────────────────────────────────────────────
class AgentStatusView(TenantAPIView):
    def get(self, request):
        states = AgentState.objects.filter(tenant=self.tenant)
        return Response(AgentStateSerializer(states, many=True).data)


class ActivityFeedView(TenantAPIView):
    def get(self, request):
        lines = FeedLine.objects.filter(tenant=self.tenant)[:40]
        return Response(FeedLineSerializer(lines, many=True).data)


class IncidentListView(TenantAPIView):
    def get(self, request):
        incidents = Incident.objects.filter(tenant=self.tenant)
        return Response(IncidentSerializer(incidents, many=True).data)


class IncidentDetailView(TenantAPIView):
    def get(self, request, incident_id: str):
        incident = Incident.objects.filter(
            tenant=self.tenant, external_id=incident_id
        ).first()
        if incident is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(
            {
                **IncidentSerializer(incident).data,
                "attackChain": AttackStepSerializer(
                    incident.attack_steps.all(), many=True
                ).data,
                "evidence": EvidenceSerializer(incident.evidence_items.all(), many=True).data,
            }
        )


class IncidentNarrativeView(TenantAPIView):
    def get(self, request, incident_id: str):
        from reports.narratives import get_narrative

        # A narrative belongs to a real incident in this tenant's ledger. Never
        # fall through to the shared demo fixture for an unknown incident id.
        if not Incident.objects.filter(tenant=self.tenant, external_id=incident_id).exists():
            return Response({"detail": "Not found."}, status=404)
        lang = request.query_params.get("lang", "en")
        narrative = get_narrative(self.tenant, incident_id, lang)
        if narrative is None:
            return Response({"detail": "lang must be one of ['en', 'gu', 'hi']"}, status=400)
        return Response(narrative)


# ── Ontology / inventory / onboarding ────────────────────────────────────────
class OntologyGraphView(TenantAPIView):
    def get(self, request):
        from ontology.graph import get_graph

        return Response(get_graph(self.tenant))


class InventoryView(TenantAPIView):
    def get(self, request):
        from ontology.graph import get_inventory
        from ontology.models import OntologyNode

        category = request.query_params.get("category", "identities")
        valid = ["cloud", "identities", "repos", "saas"]
        rows = get_inventory(self.tenant, category)
        if rows is None:
            return Response({"detail": f"category must be one of {valid}"}, status=400)
        # get_inventory() falls back to demo fixtures when the tenant has no
        # ontology nodes. An empty customer ledger must stay empty; only the
        # pre-seeded demo tenant may see the fixtures.
        if not _is_demo_tenant(self.tenant) and not OntologyNode.objects.filter(
            tenant=self.tenant
        ).exists():
            return Response([])
        return Response(rows)


class ConnectorListView(TenantAPIView):
    def get(self, request):
        from connectors.models import Connector

        rows = []
        db_states = {c.connector_id: c for c in Connector.objects.filter(tenant=self.tenant)}
        for fixture in demo_data.CONNECTORS:
            state = db_states.get(fixture["id"])
            if state:
                status = state.status
            else:
                # Not configured for this tenant → available
                status = "available"
            rows.append({**fixture, "status": status})
        return Response(rows)


class ConnectorConnectView(TenantAPIView):
    def post(self, request, connector_id: str):
        from connectors.models import Connector
        from ontology import graph as og

        known = {c["id"]: c for c in demo_data.CONNECTORS}
        if connector_id not in known:
            return Response({"detail": "Unknown connector."}, status=404)
        # Only GitHub has a real OAuth flow; the other connectors are demo-only
        # mocks. A customer tenant must not be told they are "connected".
        if not _is_demo_tenant(self.tenant) and connector_id != "gh":
            return Response({"detail": "Connector not implemented."}, status=503)
        connector, _ = Connector.objects.update_or_create(
            tenant=self.tenant, connector_id=connector_id,
            defaults={"name": known[connector_id]["name"], "status": "connected"},
        )

        # Sync connector into ontology graph
        try:
            if connector_id == "gw":
                og.upsert_node(self.tenant, "sa-gw", "Google Workspace", "saas", criticality="high",
                              meta="Identity provider + admin audit", x=560, y=420)
                og.upsert_edge(self.tenant, "e-gw-user", "sa-gw", "u-user", "authenticates_to")
            elif connector_id == "aws":
                og.upsert_node(self.tenant, "sa-aws", "AWS CloudTrail", "cloud", criticality="high",
                              meta="API activity + S3 access", x=820, y=120)
                og.upsert_edge(self.tenant, "e-aws-s3", "sa-aws", "c-s3", "logs_access")
        except Exception:
            pass

        return Response({**known[connector_id], "status": connector.status})


class IngestReplayView(TenantAPIView):
    def post(self, request):
        from connectors.tasks import replay_synthetic_logs

        scenario = request.data.get("scenario", "inc-042")
        result = replay_synthetic_logs.delay(self.tenant.id, scenario)
        return Response({"queued": True, "taskId": str(result.id), "scenario": scenario})


# ── Risk / purple team / compliance ──────────────────────────────────────────
DEMO_TENANT_SLUG = "paykraft"


def _is_demo_tenant(tenant) -> bool:
    """Return True only for the pre-seeded demo tenant."""
    return tenant.slug == DEMO_TENANT_SLUG


class RiskTrendView(TenantAPIView):
    def get(self, request):
        from detection.models import RiskSnapshot

        if not _is_demo_tenant(self.tenant):
            rows = RiskSnapshot.objects.filter(tenant=self.tenant).order_by("day_label")
            if not rows.exists():
                return Response([])
            return Response(
                [{"day": r.day_label, "org": r.org_score, "forecast": r.forecast} for r in rows]
            )
        rows = RiskSnapshot.objects.filter(tenant=self.tenant).order_by("day_label")
        if not rows.exists():
            return Response(demo_data.RISK_TREND)
        return Response(
            [{"day": r.day_label, "org": r.org_score, "forecast": r.forecast} for r in rows]
        )


class EntityRiskView(TenantAPIView):
    def get(self, request):
        from detection.models import EntityRisk

        if not _is_demo_tenant(self.tenant):
            rows = EntityRisk.objects.filter(tenant=self.tenant).order_by("-score")[:5]
            if not rows.exists():
                return Response([])
            return Response(
                [
                    {
                        "entity": r.entity, "type": r.entity_type, "score": r.score,
                        "trend": r.trend, "reason": r.reason,
                    }
                    for r in rows
                ]
            )
        rows = EntityRisk.objects.filter(tenant=self.tenant).order_by("-score")[:5]
        if not rows.exists():
            return Response(demo_data.ENTITY_RISK)
        return Response(
            [
                {
                    "entity": r.entity, "type": r.entity_type, "score": r.score,
                    "trend": r.trend, "reason": r.reason,
                }
                for r in rows
            ]
        )


class ReadinessView(TenantAPIView):
    def get(self, request):
        from reports.models import ReadinessScore

        if not _is_demo_tenant(self.tenant):
            rows = ReadinessScore.objects.filter(tenant=self.tenant).order_by("id")
            if not rows.exists():
                return Response([])
            return Response([{"week": r.week_label, "score": r.score} for r in rows])
        rows = ReadinessScore.objects.filter(tenant=self.tenant).order_by("id")
        if not rows.exists():
            return Response(demo_data.READINESS_HISTORY)
        return Response([{"week": r.week_label, "score": r.score} for r in rows])


class PurpleScenariosView(TenantAPIView):
    def get(self, request):
        from reports.models import PurpleScenario

        if not _is_demo_tenant(self.tenant):
            rows = PurpleScenario.objects.filter(tenant=self.tenant).order_by("external_id")
            if not rows.exists():
                return Response([])
            return Response(
                [
                    {
                        "id": r.external_id, "name": r.name, "desc": r.desc,
                        "lastRun": r.last_run_label, "result": r.result,
                        "detection": r.detection_label, "containment": r.containment_label,
                    }
                    for r in rows
                ]
            )
        rows = PurpleScenario.objects.filter(tenant=self.tenant).order_by("external_id")
        if not rows.exists():
            return Response(demo_data.PT_SCENARIOS)
        return Response(
            [
                {
                    "id": r.external_id, "name": r.name, "desc": r.desc,
                    "lastRun": r.last_run_label, "result": r.result,
                    "detection": r.detection_label, "containment": r.containment_label,
                }
                for r in rows
            ]
        )


class PurpleRunView(TenantAPIView):
    def post(self, request, scenario_id: str):
        from reports.purple import run_scenario

        row = run_scenario(self.tenant, scenario_id)
        if row is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(row)


class FrameworksView(TenantAPIView):
    def get(self, request):
        # The framework list is a PayKraft demo fixture. A customer tenant
        # must not inherit the demo org's compliance posture.
        if not _is_demo_tenant(self.tenant):
            return Response([])
        return Response(demo_data.FRAMEWORKS)


class RecentExportsView(TenantAPIView):
    def get(self, request):
        from reports.models import ComplianceExport

        rows = ComplianceExport.objects.filter(tenant=self.tenant).order_by("-created_at")[:10]
        if not rows.exists():
            if not _is_demo_tenant(self.tenant):
                return Response([])
            return Response(demo_data.RECENT_EXPORTS)
        return Response([{"name": r.name, "kind": r.kind, "when": r.when_label} for r in rows])


class ComplianceExportView(TenantAPIView):
    def post(self, request, framework_id: str):
        from reports.compliance import generate_export

        row = generate_export(self.tenant, framework_id, actor=request.user.username)
        if row is None:
            return Response({"detail": "Unknown framework."}, status=404)
        return Response(row, status=201)


class ComplianceExportDownloadView(TenantAPIView):
    """Download the actual PDF file for a compliance export."""
    def get(self, request, framework_id: str):
        from django.http import FileResponse

        from reports.compliance import generate_pdf

        pdf_buffer = generate_pdf(self.tenant, framework_id)
        filename = f"{framework_id}-{self.tenant.slug}-{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=filename,
            content_type="application/pdf",
        )


# ── Settings ─────────────────────────────────────────────────────────────────
class MemberListView(TenantAPIView):
    def get(self, request):
        members = Membership.objects.filter(tenant=self.tenant).select_related("user")
        return Response(MemberSerializer(members, many=True).data)


class InvoiceListView(TenantAPIView):
    # stub-tier for viva (BUILD-PLAN: billing stays fixture-backed)
    def get(self, request):
        if not _is_demo_tenant(self.tenant):
            return Response([])
        return Response(demo_data.INVOICES)


# ── Actions / policies (governed lifecycle) ──────────────────────────────────
class ActionListView(TenantAPIView):
    def get(self, request):
        actions = Action.objects.filter(tenant=self.tenant)
        return Response(ActionSerializer(actions, many=True).data)


class ActionTraceView(TenantAPIView):
    def get(self, request, action_id: str):
        action = Action.objects.filter(tenant=self.tenant, external_id=action_id).first()
        if action is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(ProvenanceStepSerializer(action.trace.all(), many=True).data)


class ActionRollbackView(TenantAPIView):
    def post(self, request, action_id: str):
        action = Action.objects.filter(tenant=self.tenant, external_id=action_id).first()
        if action is None or executor.rollback_action(action, request.user.username) is None:
            return Response({"detail": "Not found or not rollbackable."}, status=409)
        return Response(ActionSerializer(action).data)


class ActionDecisionView(TenantAPIView):
    def post(self, request, action_id: str):
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            return Response({"detail": "decision must be 'approve' or 'reject'"}, status=400)
        action = Action.objects.filter(tenant=self.tenant, external_id=action_id).first()
        decided = (
            executor.decide_action(action, decision, request.user.username)
            if action is not None
            else None
        )
        if decided is None:
            return Response({"detail": "Not found or not pending."}, status=409)
        return Response(ActionSerializer(action).data)


class PolicyView(TenantAPIView):
    def get(self, request):
        policy = AutonomyPolicy.current_for(self.tenant)
        return Response(policy.as_rows() if policy else [])

    def put(self, request):
        try:
            policy = executor.save_policy(self.tenant, request.data, request.user.username)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(policy.as_rows())
