"""
Seed the PayKraft demo tenant — the viva reset button.

`python manage.py seed_demo`          → idempotent create-if-missing
`python manage.py seed_demo --reset`  → wipe the tenant's data and rebuild
                                        the exact INC-042 demo state
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from actions.models import Action, AutonomyPolicy, PolicyRule, ProvenanceStep
from core import demo_data
from core.models import (
    AgentState,
    AttackStep,
    EvidenceItem,
    FeedLine,
    Incident,
    Membership,
    Tenant,
)
from ontology import graph as og
from ontology import neo
from ontology.models import OntologyEdge, OntologyNode

DEMO_EMAIL = "arjun.mehta@paykraft.in"
DEMO_PASSWORD = "viltrumx-demo"  # noqa: S105 — demo tenant only, never prod

# Hours-ago offsets keep incident ordering stable however often you reseed.
INCIDENT_AGE_HOURS = {"INC-042": 0, "INC-041": 30, "INC-040": 48, "INC-039": 96, "INC-038": 144}

ACTION_TRACES = {
    "ACT-2210": demo_data.PROVENANCE_TRACE,
    # Other executed actions get a compact generated trace in _seed_actions.
}


class Command(BaseCommand):
    help = "Create (or --reset) the PayKraft demo tenant with the INC-042 scenario."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete the tenant's incidents/actions/policies and reseed from fixtures.",
        )

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(slug="paykraft", defaults={"name": "PayKraft"})

        if options["reset"]:
            Action.objects.filter(tenant=tenant).delete()
            AutonomyPolicy.objects.filter(tenant=tenant).delete()
            Incident.objects.filter(tenant=tenant).delete()
            AgentState.objects.filter(tenant=tenant).delete()
            FeedLine.objects.filter(tenant=tenant).delete()
            OntologyEdge.objects.filter(tenant=tenant).delete()
            OntologyNode.objects.filter(tenant=tenant).delete()
            neo.wipe_tenant(tenant.id)
            self.stdout.write(
                "Reset: cleared incidents, actions, policies, agents, feed, ontology."
            )

        self._seed_users(tenant)
        self._seed_ontology(tenant)
        self._seed_incidents(tenant)
        self._seed_policy(tenant)
        self._seed_actions(tenant)
        self._seed_agents_and_feed(tenant)

        self.stdout.write(self.style.SUCCESS("PayKraft demo tenant ready."))
        self.stdout.write(f"Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")

    # ── users & memberships ──────────────────────────────────────────────────
    def _seed_users(self, tenant):
        user_model = get_user_model()
        role_by_email = {m["email"]: m for m in demo_data.MEMBERS}
        for email, member in role_by_email.items():
            user, created = user_model.objects.get_or_create(
                username=email, defaults={"email": email, "is_staff": email == DEMO_EMAIL}
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            Membership.objects.update_or_create(
                user=user,
                tenant=tenant,
                defaults={
                    "role": member["role"],
                    "display_name": member["name"],
                    "last_label": member["last"],
                },
            )

    # ── ontology graph (Postgres mirror + Neo4j) ─────────────────────────────
    def _seed_ontology(self, tenant):
        """PayKraft's world as a graph — the Ontology Explorer's data source
        and what makes blast-radius scoring real (demo §14 step 2).

        Writes through ontology.graph so each node/edge lands in BOTH the
        Postgres mirror (read path, always available) and Neo4j (analytics).
        If Neo4j is down the facade degrades silently and the demo still runs.
        """
        for node in demo_data.ONT_NODES:
            og.upsert_node(
                tenant, node["id"], node["label"], node["type"],
                criticality=node["criticality"],
                compromised=node.get("compromised", False),
                meta=node.get("meta", ""),
                x=node.get("x", 0), y=node.get("y", 0),
            )
        for edge in demo_data.ONT_EDGES:
            og.upsert_edge(
                tenant, edge["id"], edge["source"], edge["target"], edge["label"],
                attack=edge.get("attack", False),
            )
        where = "Postgres + Neo4j" if neo.is_available() else "Postgres (Neo4j offline)"
        self.stdout.write(
            f"Ontology: {len(demo_data.ONT_NODES)} nodes, "
            f"{len(demo_data.ONT_EDGES)} edges → {where}"
        )

    # ── incidents + attack chain + evidence ──────────────────────────────────
    def _seed_incidents(self, tenant):
        now = timezone.now()
        for row in demo_data.INCIDENTS:
            incident, _ = Incident.objects.update_or_create(
                tenant=tenant,
                external_id=row["id"],
                defaults={
                    "title": row["title"],
                    "severity": row["severity"],
                    "status": row["status"],
                    "entity": row["entity"],
                    "time_label": row["time"],
                    "occurred_at": now - timedelta(hours=INCIDENT_AGE_HOURS[row["id"]]),
                    "mitre": row["mitre"],
                    "confidence": 0.96 if row["id"] == "INC-042" else None,
                },
            )
            if row["id"] == "INC-042":
                incident.attack_steps.all().delete()
                for i, step in enumerate(demo_data.ATTACK_CHAIN, start=1):
                    AttackStep.objects.create(
                        incident=incident, order=i,
                        time_label=step["time"], title=step["title"], detail=step["detail"],
                        mitre=step["mitre"], mitre_name=step["mitreName"],
                        severity=step["severity"],
                    )
                incident.evidence_items.all().delete()
                for i, item in enumerate(demo_data.EVIDENCE, start=1):
                    EvidenceItem.objects.create(
                        incident=incident, order=i, external_id=item["id"],
                        kind=item["kind"], source=item["source"], excerpt=item["excerpt"],
                    )

    # ── autonomy dial v1 ─────────────────────────────────────────────────────
    def _seed_policy(self, tenant):
        if AutonomyPolicy.objects.filter(tenant=tenant).exists():
            return
        policy = AutonomyPolicy.objects.create(tenant=tenant, version=1, created_by="seed_demo")
        for i, row in enumerate(demo_data.DEFAULT_POLICIES):
            PolicyRule.objects.create(
                policy=policy, action_type=row["actionType"], level=row["level"],
                crown_jewel_override=row["crownJewelOverride"], order=i,
            )

    # ── actions + provenance ─────────────────────────────────────────────────
    def _seed_actions(self, tenant):
        inc042 = Incident.objects.get(tenant=tenant, external_id="INC-042")
        policy = AutonomyPolicy.current_for(tenant)
        now = timezone.now()
        for i, row in enumerate(demo_data.ACTIONS):
            action, created = Action.objects.update_or_create(
                tenant=tenant,
                external_id=row["id"],
                defaults={
                    "incident": inc042 if row["id"].startswith("ACT-221") else None,
                    "action_type": row["type"],
                    "target": row["target"],
                    "level": row["level"],
                    "status": row["status"],
                    "blast_radius": row["blastRadius"],
                    "time_label": row["time"],
                    "rollback_plan": row["rollback"],
                    "policy_version": policy.version if policy else None,
                    "executed_at": now if row["status"] == "executed" else None,
                },
            )
            # ordering: fixtures are newest-first; stagger created_at to match
            Action.objects.filter(pk=action.pk).update(
                created_at=now - timedelta(minutes=i)
            )
            action.trace.all().delete()
            trace = ACTION_TRACES.get(
                row["id"],
                [
                    {
                        "step": "Trigger",
                        "detail": f"{row['type']} proposed on {row['target']}",
                        "ok": True,
                    },
                    {"step": "Blast radius", "detail": f"{row['blastRadius']:.2f}", "ok": True},
                    {
                        "step": "Policy gate",
                        "detail": f"{row['type']} resolves to {row['level']} (policy v1)",
                        "ok": True,
                    },
                    {"step": "Execute" if row["status"] != "proposed" else "Awaiting approval",
                     "detail": f"status: {row['status']}", "ok": True},
                ],
            )
            for j, step in enumerate(trace, start=1):
                ProvenanceStep.objects.create(
                    action=action, order=j, step=step["step"],
                    detail=step["detail"], ok=step["ok"],
                )

    # ── agent states + activity feed ─────────────────────────────────────────
    def _seed_agents_and_feed(self, tenant):
        for i, agent in enumerate(demo_data.AGENTS):
            AgentState.objects.update_or_create(
                tenant=tenant, agent_id=agent["id"],
                defaults={
                    "name": agent["name"], "role": agent["role"], "status": agent["status"],
                    "current_task": agent["currentTask"], "stat": agent["stat"], "order": i,
                },
            )
        if not FeedLine.objects.filter(tenant=tenant).exists():
            # fixtures are newest-first; create oldest-first so ordering holds
            for row in reversed(demo_data.ACTIVITY_FEED):
                FeedLine.objects.create(
                    tenant=tenant, time_label=row["t"], agent=row["agent"],
                    line=row["line"], tone=row["tone"],
                )
