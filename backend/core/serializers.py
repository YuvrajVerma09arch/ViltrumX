"""
DRF serializers for the v1 API.

Field names are camelCase because frontend/src/data/mock.ts is the contract
(docs/ARCHITECTURE.md §10). Do not rename fields here without changing the
frontend types in the same PR.
"""

from rest_framework import serializers

from actions.models import Action, ProvenanceStep
from core.models import AgentState, AttackStep, EvidenceItem, FeedLine, Incident, Membership


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
