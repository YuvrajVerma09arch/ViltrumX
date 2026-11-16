#!/usr/bin/env python3
"""
Standalone evaluation script - doesn't use manage.py to avoid PostgreSQL settings.
"""
import sys
from collections import Counter
from pathlib import Path

import django
import numpy as np
from django.conf import settings
from django.core.management import call_command

# Add backend to path so Django can find apps
BACKEND_DIR = Path(__file__).resolve().parents[3]  # .../backend
sys.path.insert(0, str(BACKEND_DIR))

# Configure Django with SQLite. The app-model imports below must come after
# setup/migrations, hence the targeted E402 suppressions (order-dependent by design).
if not settings.configured:
    settings.configure(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "rest_framework",
            "rest_framework_simplejwt",
            "corsheaders",
            "core",
            "connectors",
            "detection",
        ],
        USE_TZ=True,
        SECRET_KEY="eval-only",
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
        ],
        ROOT_URLCONF="viltrumx.urls",
    )

django.setup()

# Run migrations
call_command("migrate", verbosity=0, run_syncdb=True)

# App models require django.setup()/migrations to have run first (intentional E402)
from connectors.models import RawEvent  # noqa: E402
from connectors.synthetic import BLR_IPS, SCENARIOS  # noqa: E402
from detection.features import build_context, featurize_with_context  # noqa: E402

MODEL_DIR = Path(__file__).resolve().parent.parent / "models_store"
MODEL_DIR.mkdir(exist_ok=True)


def _seed():
    from core.models import Tenant
    tenant = Tenant.objects.first()
    if tenant is None:
        tenant = Tenant.objects.create(name="Eval Tenant", slug="eval-tenant")
        print(f"Created tenant: {tenant.name}")
    for name in ("baseline", "inc-042", "insider-export"):
        events = SCENARIOS[name]()
        for raw in events:
            from connectors.synthetic import normalize
            RawEvent.objects.create(
                tenant=tenant, is_attack=raw.get("attack", False),
                **normalize(raw),
            )
    print(f"seeded {RawEvent.objects.count()} events")
    return True


def _insider_labels(events):
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


def train_models(X_train, y_train, insider_train):
    import joblib
    import xgboost as xgb
    from sklearn.ensemble import IsolationForest, RandomForestClassifier

    print("Training Isolation Forest...")
    iso = IsolationForest(n_estimators=200, contamination=0.08, random_state=42)
    iso.fit(X_train)
    joblib.dump(iso, MODEL_DIR / "isolation_forest.joblib")

    print("Training XGBoost...")
    if sum(y_train) == 0 or sum(y_train) == len(y_train):
        print("  SKIP XGBoost - need both classes")
        xgb_model = None
    else:
        xgb_model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", random_state=42, n_jobs=1,
        )
        xgb_model.fit(np.array(X_train), np.array(y_train))
        joblib.dump(xgb_model, MODEL_DIR / "xgboost.joblib")

    print("Training Random Forest...")
    if sum(insider_train) == 0:
        print("  SKIP RF - no insider labels")
        rf_model = None
    else:
        rf_model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
        rf_model.fit(X_train, insider_train)
        joblib.dump(rf_model, MODEL_DIR / "random_forest.joblib")

    return iso, xgb_model, rf_model


def eval_classifier(name, model, X_test, y_test):
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
    X_arr = np.array(X_test)
    y_arr = np.array(y_test)
    y_pred = model.predict(X_arr)

    prec, rec, f1, sup = precision_recall_fscore_support(
        y_arr, y_pred, average=None, zero_division=0
    )
    macro = precision_recall_fscore_support(y_arr, y_pred, average="macro", zero_division=0)
    weighted = precision_recall_fscore_support(y_arr, y_pred, average="weighted", zero_division=0)
    cm = confusion_matrix(y_arr, y_pred)

    print(f"\n{name}:")
    print(f"  Per-class:  prec={prec}  rec={rec}  f1={f1}  support={sup}")
    print(f"  Macro F1:   {macro[2]:.4f}")
    print(f"  Weighted F1: {weighted[2]:.4f}")
    print(f"  Confusion Matrix:\n{cm}")

    return {
        "per_class": {
            "precision": prec.tolist(),
            "recall": rec.tolist(),
            "f1": f1.tolist(),
            "support": sup.tolist(),
        },
        "macro": {"precision": macro[0], "recall": macro[1], "f1": macro[2]},
        "weighted": {"precision": weighted[0], "recall": weighted[1], "f1": weighted[2]},
        "confusion_matrix": cm.tolist(),
    }


def eval_isolation(model, X_test, y_test):
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
    X_arr = np.array(X_test)
    y_arr = np.array(y_test)
    raw_pred = model.predict(X_arr)
    y_pred = (raw_pred == -1).astype(int)

    prec, rec, f1, sup = precision_recall_fscore_support(
        y_arr, y_pred, average=None, zero_division=0
    )
    macro_f1 = precision_recall_fscore_support(y_arr, y_pred, average="macro", zero_division=0)[2]
    cm = confusion_matrix(y_arr, y_pred)

    print("\nIsolation Forest (anomaly detection):")
    print(f"  Per-class:  prec={prec}  rec={rec}  f1={f1}  support={sup}")
    print(f"  Macro F1:   {macro_f1:.4f}")
    print(f"  Confusion Matrix:\n{cm}")

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


def main():
    if RawEvent.objects.count() < 50:
        print("Seeding events...")
        if not _seed():
            return 1

    events = list(RawEvent.objects.order_by("occurred_at"))
    print(f"loaded {len(events)} events")

    # Use stratified split to ensure both classes in train and test
    # (Chronological puts all attacks at the end - data leakage risk)
    from sklearn.model_selection import train_test_split
    y_all = [1 if e.is_attack else 0 for e in events]
    train_idx, test_idx = train_test_split(
        range(len(events)), test_size=0.3, stratify=y_all, random_state=42
    )
    train_events = [events[i] for i in train_idx]
    test_events = [events[i] for i in test_idx]

    print(f"train: {len(train_events)}, test: {len(test_events)}")
    cnt_train = Counter(1 if e.is_attack else 0 for e in train_events)
    cnt_test = Counter(1 if e.is_attack else 0 for e in test_events)
    print(f"  train: benign={cnt_train[0]}, attack={cnt_train[1]}")
    print(f"  test:  benign={cnt_test[0]}, attack={cnt_test[1]}")

    train_ctx = build_context(None, train_events)
    test_ctx = build_context(None, test_events)

    X_train = [featurize_with_context(e, train_ctx) for e in train_events]
    y_train = [1 if e.is_attack else 0 for e in train_events]
    insider_train = _insider_labels(train_events)

    X_test = [featurize_with_context(e, test_ctx) for e in test_events]
    y_test = [1 if e.is_attack else 0 for e in test_events]
    insider_test = _insider_labels(test_events)

    print("\n--- Training on train split ---")
    iso_model, xgb_model, rf_model = train_models(X_train, y_train, insider_train)

    print("\n--- Evaluation on held-out test set ---")
    report = {}

    if xgb_model is not None:
        report["xgboost"] = eval_classifier("XGBoost (attack detection)", xgb_model, X_test, y_test)

    if rf_model is not None:
        report["random_forest"] = eval_classifier(
            "Random Forest (insider threat)", rf_model, X_test, insider_test
        )

    report["isolation_forest"] = eval_isolation(iso_model, X_test, y_test)

    print("\n" + "=" * 60)
    print("SUMMARY — Weighted F1 (primary metric for imbalanced data)")
    print("=" * 60)
    for model_name, metrics in report.items():
        if "weighted" in metrics:
            f1 = metrics["weighted"]["f1"]
            print(f"  {model_name:20s}: F1 = {f1:.4f}")
        elif "macro_f1" in metrics:
            f1 = metrics["macro_f1"]
            print(f"  {model_name:20s}: Macro F1 = {f1:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())