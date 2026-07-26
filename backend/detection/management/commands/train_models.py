"""
Train detection ML models (CLAUDE.md §6).

Loads (or generates) baseline + labelled-attack events, featurizes them
through detection.features.featurize_with_context, and trains:

  - Isolation Forest     → backend/models_store/isolation_forest.joblib
  - XGBoost classifier   → .../xgboost.joblib            (label = is_attack)
  - Random Forest        → .../random_forest.joblib       (insider-threat)
  - HDBSCAN clusterer    → .../hdbscan.joblib             (noise-gate)

Usage:
  python manage.py train_models
  python manage.py train_models --clear       # wipe models_store first
  python manage.py train_models --seed        # generate RawEvents if none exist

Idempotent — re-running overwrites the joblibs. Safe under Celery eager mode.
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand

from connectors.models import RawEvent
from connectors.synthetic import SCENARIOS

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models_store")
MODEL_DIR = os.path.abspath(MODEL_DIR)


class Command(BaseCommand):
    help = "Train the Isolation Forest, XGBoost, Random Forest and HDBSCAN models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true", help="Wipe models_store before training"
        )
        parser.add_argument(
            "--seed", action="store_true", help="Generate synthetic events if DB has none"
        )

    def handle(self, *args, **opts):
        os.makedirs(MODEL_DIR, exist_ok=True)
        if opts["clear"]:
            for f in os.listdir(MODEL_DIR):
                if f.endswith(".joblib"):
                    os.remove(os.path.join(MODEL_DIR, f))
            self.stdout.write("cleared models_store/")

        if RawEvent.objects.count() < 50:
            if not opts["seed"]:
                self.stdout.write(self.style.WARNING(
                    f"only {RawEvent.objects.count()} RawEvents — "
                    "run with --seed or replay scenarios first."
                ))
                return
            self._seed()

        events = list(RawEvent.objects.order_by("occurred_at"))
        self.stdout.write(f"featurizing {len(events)} events...")
        from detection.features import build_context, featurize_with_context

        ctx = build_context(None, events)
        X = [featurize_with_context(e, ctx) for e in events]
        y = [1 if e.is_attack else 0 for e in events]
        insider_y = self._insider_labels(events)

        self._train_isolation(X)
        self._train_xgboost(X, y)
        self._train_random_forest(X, insider_y)
        self._train_hdbscan(X)
        self.stdout.write(self.style.SUCCESS("training complete"))

    def _insider_labels(self, events) -> list:
        """Insider = attacked with a known-benign IP / principal (PT-02 pattern)."""
        from connectors.synthetic import BLR_IPS
        labels = []
        for e in events:
            if not e.is_attack:
                labels.append(0)
                continue
            # PT-02's deepa.nair-style bulk export off-hours from Bangalore IP
            if e.ip in BLR_IPS and "GetObject" == str(e.event_type):
                labels.append(1)
            elif str(e.event_type).startswith("GetObject") and e.ip in BLR_IPS:
                labels.append(1)
            else:
                labels.append(0)
        return labels

    def _seed(self):
        from core.models import Tenant
        tenant = Tenant.objects.first()
        if tenant is None:
            self.stdout.write(self.style.ERROR("no tenant — run seed_demo first"))
            return
        for name in ("baseline", "inc-042", "insider-export"):
            events = SCENARIOS[name]()
            for raw in events:
                from connectors.synthetic import normalize
                RawEvent.objects.create(
                    tenant=tenant, is_attack=raw.get("attack", False),
                    **normalize(raw),
                )
        self.stdout.write(f"seeded {RawEvent.objects.count()} events")

    def _train_isolation(self, X):
        import joblib
        from sklearn.ensemble import IsolationForest
        model = IsolationForest(n_estimators=200, contamination=0.08, random_state=42)
        model.fit(X)
        joblib.dump(model, os.path.join(MODEL_DIR, "isolation_forest.joblib"))
        self.stdout.write("  isolation_forest.joblib")

    def _train_xgboost(self, X, y):
        import joblib
        import numpy as np
        import xgboost as xgb
        if sum(y) == 0 or sum(y) == len(y):
            self.stdout.write(self.style.WARNING("skipping XGBoost — need both classes"))
            return
        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", random_state=42, n_jobs=1,
        )
        model.fit(np.array(X), np.array(y))
        joblib.dump(model, os.path.join(MODEL_DIR, "xgboost.joblib"))
        self.stdout.write("  xgboost.joblib")

    def _train_random_forest(self, X, y):
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        if sum(y) == 0:
            self.stdout.write(self.style.WARNING("skipping RF — no insider labels"))
            return
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
        model.fit(X, y)
        joblib.dump(model, os.path.join(MODEL_DIR, "random_forest.joblib"))
        self.stdout.write("  random_forest.joblib")

    def _train_hdbscan(self, X):
        import joblib
        try:
            import hdbscan
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"HDBSCAN unavailable: {exc}"))
            return
        clusterer = hdbscan.HDBSCAN(min_cluster_size=3, min_samples=2)
        clusterer.fit(X)
        joblib.dump(clusterer, os.path.join(MODEL_DIR, "hdbscan.joblib"))
        self.stdout.write("  hdbscan.joblib")
