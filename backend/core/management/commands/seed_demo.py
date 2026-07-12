"""
Seed the PayKraft demo tenant.

Stub phase: creates the demo login (API data still comes from fixtures).
WEEK 1: extend to create Tenant/Membership/Incident/Action rows, and add
--reset to wipe + reseed in one command (the viva reset button).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

DEMO_EMAIL = "arjun.mehta@paykraft.in"
DEMO_PASSWORD = "viltrumx-demo"  # noqa: S105 — demo tenant only, never prod


class Command(BaseCommand):
    help = "Create the PayKraft demo user (idempotent)."

    def handle(self, *args, **options):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=DEMO_EMAIL,
            defaults={"email": DEMO_EMAIL, "is_staff": True},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo user {DEMO_EMAIL}"))
        else:
            self.stdout.write(f"Demo user {DEMO_EMAIL} already exists")
        self.stdout.write(f"Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
