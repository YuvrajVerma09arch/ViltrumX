"""
DRF serializers for the v1 API.

Field names are camelCase because frontend/src/data/mock.ts is the contract
(docs/ARCHITECTURE.md §10). Do not rename fields here without changing the
frontend types in the same PR.
"""

from rest_framework import serializers

from actions.models import Action, ProvenanceStep
from core.models import (
    AgentState,
    AttackStep,
    EvidenceItem,
    FeedLine,
    Incident,
    Membership,
    Tenant,
    VerificationCode,
)


class IncidentSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="external_id")
    time = serializers.CharField(source="time_label")

    class Meta:
        model = Incident
        fields = ["id", "title", "severity", "status", "entity", "time", "mitre"]


class AttackStepSerializer(serializers.ModelSerializer):
    time = serializers.CharField(source="time_label")
    mitreName = serializers.CharField(source="mitre_name")

    class Meta:
        model = AttackStep
        fields = ["time", "title", "detail", "mitre", "mitreName", "severity"]


class EvidenceSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="external_id")

    class Meta:
        model = EvidenceItem
        fields = ["id", "kind", "source", "excerpt"]


class AgentStateSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="agent_id")
    currentTask = serializers.CharField(source="current_task")

    class Meta:
        model = AgentState
        fields = ["id", "name", "role", "status", "currentTask", "stat"]


class FeedLineSerializer(serializers.ModelSerializer):
    t = serializers.CharField(source="time_label")

    class Meta:
        model = FeedLine
        fields = ["t", "agent", "line", "tone"]


class ActionSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="external_id")
    type = serializers.CharField(source="action_type")
    blastRadius = serializers.FloatField(source="blast_radius")
    time = serializers.CharField(source="time_label")
    rollback = serializers.CharField(source="rollback_plan")

    class Meta:
        model = Action
        fields = ["id", "type", "target", "level", "status", "blastRadius", "time", "rollback"]


class ProvenanceStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProvenanceStep
        fields = ["step", "detail", "ok"]


class MemberSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name")
    email = serializers.SerializerMethodField()
    last = serializers.CharField(source="last_label")

    class Meta:
        model = Membership
        fields = ["name", "email", "role", "last"]

    def get_email(self, obj) -> str:
        return obj.user.email or obj.user.username


class RegisterSerializer(serializers.Serializer):
    """Founder signup: creates an inactive User + Tenant + Owner Membership.

    The account stays inactive until the emailed signup code is verified — no
    JWT is issued by registration.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=120)
    tenant_name = serializers.CharField(max_length=120)
    tenant_slug = serializers.SlugField(max_length=60)

    def validate_tenant_slug(self, value):
        if Tenant.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Tenant slug already taken.")
        return value

    def validate_email(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email already registered.")
        return email

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        from django.db import transaction

        User = get_user_model()

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["email"],
                email=validated_data["email"],
                password=validated_data["password"],
                is_active=False,
            )
            tenant = Tenant.objects.create(
                name=validated_data["tenant_name"],
                slug=validated_data["tenant_slug"],
            )
            membership = Membership.objects.create(
                user=user,
                tenant=tenant,
                role="Owner",
                display_name=validated_data["full_name"],
                last_label="",
            )
        return {"user": user, "tenant": tenant, "membership": membership}


class VerifySerializer(serializers.Serializer):
    """Step 2 of signup: exchange {email, code} for a session."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=20, trim_whitespace=True)

    def validate_email(self, value):
        return value.strip().lower()


class LoginChallengeSerializer(serializers.Serializer):
    """Step 1 of login: check the password, then email a one-time code."""

    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)  # legacy clients
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = (attrs.get("email") or attrs.get("username") or "").strip().lower()
        if not identifier:
            raise serializers.ValidationError({"email": "Email is required."})
        attrs["email"] = identifier
        return attrs


class LoginVerifySerializer(LoginChallengeSerializer):
    """Step 2 of login: the code alone is not enough — re-check the password."""

    code = serializers.CharField(max_length=20, trim_whitespace=True)


class ResendSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=VerificationCode.PURPOSE_CHOICES, default="signup"
    )

    def validate_email(self, value):
        return value.strip().lower()
