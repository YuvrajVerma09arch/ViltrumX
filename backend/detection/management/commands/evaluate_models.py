"""
Evaluate detection ML models with proper train/test split and metrics (CLAUDE.md §6).

This command loads or generates events, splits them chronologically (to avoid
look-ahead leakage), trains on the training window, and evaluates on the
held-out test window — reporting precision, recall, F1 per model and class.

Usage:
  python manage.py evaluate_models
  python manage.py evaluate_models --seed       # generate events if needed
  python manage.py evaluate_models --test-size 0.3 --cv 5  # custom splits

Outputs:
  - Per-model metrics (precision, recall, F1, support) for attack vs benign
  - Confusion matrices
  - Overall weighted/macro F1 (the number to compare against the 0.99 claim)
"""
from __future__ import annotations

import json
import os
from collections import Counter

from django.core.management.base import BaseCommand

# NOTE: this is a real Django management command. Django configures settings,
# sets up apps and connects to the (already migrated) database before handle()
# runs, so no standalone shim (settings.configure / django.setup / "migrate")
# belongs here. Keep module import side-effect free: model imports happen lazily
# inside handle()/helpers. See evaluate_models_standalone.py for standalone use.

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models_store")
MODEL_DIR = os.path.abspath(MODEL_DIR)


class Command(BaseCommand):
    help = "Evaluate trained models on a chronological train/test split with full metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            action="store_true",
            help="Generate synthetic events if DB has none",
        )
        parser.add_argument(
            "--test-size",
            type=float,
            default=0.3,
            help="Fraction of events to hold out as test (chronological split)",
        )
        parser.add_argument(
            "--cv",
            type=int,
            default=0,
            help="K-fold CV on training set (0 = skip, >0 = run CV)",
        )
        parser.add_argument(
            "--save-report",
            type=str,
            default="",
            help="Path to write JSON evaluation report",
        )

    def handle(self, *args, **opts):
        # Imported lazily so importing this module has no side effects and Django
        # is fully initialised (apps ready, DB configured) before models load.
        from connectors.models import RawEvent

        test_size = opts["test_size"]
        cv_folds = opts["cv"]
        save_path = opts["save_report"]

        if RawEvent.objects.count() < 50:
            if not opts["seed"]:
                self.stdout.write(self.style.WARNING(
                    f"only {RawEvent.objects.count()} RawEvents — "
                    "run with --seed or replay scenarios first."
                ))
                return
            self._seed()

        events = list(RawEvent.objects.order_by("occurred_at"))
        self.stdout.write(f"loaded {len(events)} events")

        # Chronological split — no leakage!
        split_idx = int(len(events) * (1 - test_size))
        train_events = events[:split_idx]
        test_events = events[split_idx:]

        self.stdout.write(f"train: {len(train_events)}, test: {len(test_events)}")
        self._print_label_dist(train_events, "train")
        self._print_label_dist(test_events, "test")

        from detection.features import build_context, featurize_with_context

        train_ctx = build_context(None, train_events)
        test_ctx = build_context(None, test_events)

        X_train = [featurize_with_context(e, train_ctx) for e in train_events]
        y_train = [1 if e.is_attack else 0 for e in train_events]
        insider_train = self._insider_labels(train_events)

        X_test = [featurize_with_context(e, test_ctx) for e in test_events]
        y_test = [1 if e.is_attack else 0 for e in test_events]
        insider_test = self._insider_labels(test_events)

        # Train all models on training set
        self.stdout.write("\n--- Training on train split ---")
        iso_model = self._train_isolation(X_train)
        xgb_model = self._train_xgboost(X_train, y_train)
        rf_model = self._train_random_forest(X_train, insider_train)
        hdb_model = self._train_hdbscan(X_train)

        # Evaluate on held-out test set
        self.stdout.write("\n--- Evaluation on held-out test set ---")
        report = {}

        if xgb_model is not None:
            report["xgboost"] = self._eval_classifier(
                "XGBoost (attack detection)", xgb_model, X_test, y_test
            )

        if rf_model is not None:
            report["random_forest"] = self._eval_classifier(
                "Random Forest (insider threat)", rf_model, X_test, insider_test
            )

        if iso_model is not None:
            report["isolation_forest"] = self._eval_isolation(
                iso_model, X_test, y_test
            )

        if hdb_model is not None:
            report["hdbscan"] = self._eval_hdbscan(hdb_model, X_test, y_test)

        # Print summary
        self._print_summary(report)

        if save_path:
            with open(save_path, "w") as f:
                json.dump(report, f, indent=2, default=str)
            self.stdout.write(f"\nreport saved to {save_path}")

        # Run CV if requested
        if cv_folds > 0:
            self.stdout.write(f"\n--- {cv_folds}-fold CV on training set ---")
            self._run_cv(cv_folds, X_train, y_train, insider_train)

    def _print_label_dist(self, events, label):
        cnt = Counter(1 if e.is_attack else 0 for e in events)
        self.stdout.write(f"  {label}: benign={cnt[0]}, attack={cnt[1]}")

    def _insider_labels(self, events) -> list:
        """Insider = attacked with a known-benign IP / principal (PT-02 pattern)."""
        from connectors.synthetic import BLR_IPS
        labels = []
        for e in events:
            if not e.is_attack:
                labels.append(0)
                continue
            if e.ip in BLR_IPS and "GetObject" == str(e.event_type):
                labels.append(1)
            elif str(e.event_type).startswith("GetObject") and e.ip in BLR_IPS:
                labels.append(1)
            else:
                labels.append(0)
        return labels

    def _seed(self):
        from connectors.models import RawEvent
        from connectors.synthetic import SCENARIOS
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

    # ── Model training (copied from train_models for consistency) ──────────────

    def _train_isolation(self, X):
        import joblib
        from sklearn.ensemble import IsolationForest
        model = IsolationForest(n_estimators=200, contamination=0.08, random_state=42)
        model.fit(X)
        joblib.dump(model, os.path.join(MODEL_DIR, "isolation_forest.joblib"))
        self.stdout.write("  isolation_forest.joblib")
        return model

    def _train_xgboost(self, X, y):
        import joblib
        import numpy as np
        import xgboost as xgb
        if sum(y) == 0 or sum(y) == len(y):
            self.stdout.write(self.style.WARNING("skipping XGBoost — need both classes"))
            return None
        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", random_state=42, n_jobs=1,
        )
        model.fit(np.array(X), np.array(y))
        joblib.dump(model, os.path.join(MODEL_DIR, "xgboost.joblib"))
        self.stdout.write("  xgboost.joblib")
        return model

    def _train_random_forest(self, X, y):
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        if sum(y) == 0:
            self.stdout.write(self.style.WARNING("skipping RF — no insider labels"))
            return None
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
        model.fit(X, y)
        joblib.dump(model, os.path.join(MODEL_DIR, "random_forest.joblib"))
        self.stdout.write("  random_forest.joblib")
        return model

    def _train_hdbscan(self, X):
        import joblib
        try:
            import hdbscan
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"HDBSCAN unavailable: {exc}"))
            return None
        clusterer = hdbscan.HDBSCAN(min_cluster_size=3, min_samples=2)
        clusterer.fit(X)
        joblib.dump(clusterer, os.path.join(MODEL_DIR, "hdbscan.joblib"))
        self.stdout.write("  hdbscan.joblib")
        return clusterer

    # ── Evaluation ────────────────────────────────────────────────────────────

    def _eval_classifier(self, name, model, X, y):
        import numpy as np
        from sklearn.metrics import (
            confusion_matrix,
            precision_recall_fscore_support,
        )

        X_arr = np.array(X)
        y_arr = np.array(y)
        y_pred = model.predict(X_arr)

        prec, rec, f1, sup = precision_recall_fscore_support(
            y_arr, y_pred, average=None, zero_division=0
        )
        macro_prec, macro_rec, macro_f1, _ = precision_recall_fscore_support(
            y_arr, y_pred, average="macro", zero_division=0
        )
        weighted_prec, weighted_rec, weighted_f1, _ = precision_recall_fscore_support(
            y_arr, y_pred, average="weighted", zero_division=0
        )
        cm = confusion_matrix(y_arr, y_pred)

        self.stdout.write(f"\n{name}:")
        self.stdout.write(f"  Per-class:  prec={prec}  rec={rec}  f1={f1}  support={sup}")
        self.stdout.write(f"  Macro F1:   {macro_f1:.4f}")
        self.stdout.write(f"  Weighted F1: {weighted_f1:.4f}")
        self.stdout.write(f"  Confusion Matrix:\n{cm}")

        return {
            "per_class": {
                "precision": prec.tolist(),
                "recall": rec.tolist(),
                "f1": f1.tolist(),
                "support": sup.tolist(),
            },
            "macro": {"precision": macro_prec, "recall": macro_rec, "f1": macro_f1},
            "weighted": {"precision": weighted_prec, "recall": weighted_rec, "f1": weighted_f1},
            "confusion_matrix": cm.tolist(),
        }

    def _eval_isolation(self, model, X, y):
        import numpy as np
        from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

        X_arr = np.array(X)
        y_arr = np.array(y)
        # IsolationForest: -1 = anomaly, 1 = normal → flip to 1=attack, 0=benign
        raw_pred = model.predict(X_arr)
        y_pred = (raw_pred == -1).astype(int)

        prec, rec, f1, sup = precision_recall_fscore_support(
            y_arr, y_pred, average=None, zero_division=0
        )
        macro_f1 = precision_recall_fscore_support(
            y_arr, y_pred, average="macro", zero_division=0
        )[2]
        cm = confusion_matrix(y_arr, y_pred)

        self.stdout.write("\nIsolation Forest (anomaly detection):")
        self.stdout.write(f"  Per-class:  prec={prec}  rec={rec}  f1={f1}  support={sup}")
        self.stdout.write(f"  Macro F1:   {macro_f1:.4f}")
        self.stdout.write(f"  Confusion Matrix:\n{cm}")

        return {
            "per_class": {
                "precision": prec.tolist(),
                "recall": rec.tolist(),
                "f1": f1.tolist(),
                "support": sup.tolist(),
            },
            "macro_f1": macro_f1,
            "confusion_matrix": cm.tolist(),
        }

    def _eval_hdbscan(self, model, X, y):
        import numpy as np
        from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

        X_arr = np.array(X)
        y_arr = np.array(y)
        # HDBSCAN: -1 = noise/outlier (treat as attack), cluster >=0 = normal
        raw_pred = model.labels_ if hasattr(model, "labels_") else model.fit_predict(X_arr)
        y_pred = (raw_pred == -1).astype(int)

        prec, rec, f1, sup = precision_recall_fscore_support(
            y_arr, y_pred, average=None, zero_division=0
        )
        macro_f1 = precision_recall_fscore_support(
            y_arr, y_pred, average="macro", zero_division=0
        )[2]
        cm = confusion_matrix(y_arr, y_pred)

        self.stdout.write("\nHDBSCAN (noise-gate clustering):")
        self.stdout.write(f"  Per-class:  prec={prec}  rec={rec}  f1={f1}  support={sup}")
        self.stdout.write(f"  Macro F1:   {macro_f1:.4f}")
        self.stdout.write(f"  Confusion Matrix:\n{cm}")

        return {
            "per_class": {
                "precision": prec.tolist(),
                "recall": rec.tolist(),
                "f1": f1.tolist(),
                "support": sup.tolist(),
            },
            "macro_f1": macro_f1,
            "confusion_matrix": cm.tolist(),
        }

    def _print_summary(self, report):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SUMMARY — Weighted F1 (primary metric for imbalanced data)")
        self.stdout.write("=" * 60)
        for model_name, metrics in report.items():
            if "weighted" in metrics:
                f1 = metrics["weighted"]["f1"]
                self.stdout.write(f"  {model_name:20s}: F1 = {f1:.4f}")
            elif "macro_f1" in metrics:
                f1 = metrics["macro_f1"]
                self.stdout.write(f"  {model_name:20s}: Macro F1 = {f1:.4f}")

    def _run_cv(self, cv_folds, X, y, insider_y):
        import numpy as np
        from sklearn.metrics import precision_recall_fscore_support
        from sklearn.model_selection import StratifiedKFold

        X_arr = np.array(X)
        y_arr = np.array(y)
        insider_arr = np.array(insider_y)

        skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)

        # XGBoost CV
        import xgboost as xgb
        xgb_f1s = []
        for train_idx, val_idx in skf.split(X_arr, y_arr):
            model = xgb.XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.1,
                eval_metric="logloss", random_state=42, n_jobs=1,
            )
            model.fit(X_arr[train_idx], y_arr[train_idx])
            pred = model.predict(X_arr[val_idx])
            _, _, f1, _ = precision_recall_fscore_support(
                y_arr[val_idx], pred, average="weighted", zero_division=0
            )
            xgb_f1s.append(f1)
        self.stdout.write(f"  XGBoost weighted F1: {np.mean(xgb_f1s):.4f} ± {np.std(xgb_f1s):.4f}")

        # RF CV (if insider labels exist)
        if sum(insider_arr) > 0:
            from sklearn.ensemble import RandomForestClassifier
            rf_f1s = []
            for train_idx, val_idx in skf.split(X_arr, insider_arr):
                model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
                model.fit(X_arr[train_idx], insider_arr[train_idx])
                pred = model.predict(X_arr[val_idx])
                _, _, f1, _ = precision_recall_fscore_support(
                    insider_arr[val_idx], pred, average="weighted", zero_division=0
                )
                rf_f1s.append(f1)
            self.stdout.write(
                f"  Random Forest weighted F1: {np.mean(rf_f1s):.4f} ± {np.std(rf_f1s):.4f}"
            )