"""
Synthetic log generator (Week 2 step 3 — the highest-value code here).

One generator, three consumers:
  1. demo — replay the INC-042 attack live (POST /ingest/replay)
  2. ML   — weeks of baseline traffic + labeled attacks to train on (Week 3)
  3. proof — the purple team replays these same scenarios nightly (Week 4)

Log lines come out in the real source formats (Google Workspace admin audit,
AWS CloudTrail, GitHub audit log) so the parser in tasks.py is honest work,
not a toy.
"""

import random
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

STAFF = [
    ("arjun.mehta@paykraft.in", "high"),
    ("priya.sharma@paykraft.in", "high"),
    ("rohan.iyer@paykraft.in", "medium"),
    ("deepa.nair@paykraft.in", "high"),
]

BLR_IPS = ["49.207.184.12", "106.51.72.89", "122.171.20.44", "14.142.110.7"]
OFFICE_GEO = "IN-KA"
MOSCOW_IP = "185.220.101.34"

REPOS = ["paykraft-core", "paykraft-infra", "paykraft-web"]
BUCKETS = ["customers-db-backups", "paykraft-staging-assets"]


def _workspace_login(ts, user, ip, geo, mfa="push_approved", success=True, attempt=1):
    return {
        "source": "workspace",
        "id": {"time": ts.isoformat(), "applicationName": "login"},
        "actor": {"email": user},
        "ipAddress": ip,
        "events": [{
            "type": "login",
            "name": "login_success" if success else "login_failure",
            "parameters": [
                {"name": "login_type", "value": "google_password"},
                {"name": "login_challenge_method", "value": mfa},
                {"name": "challenge_attempt", "intValue": attempt},
                {"name": "geo", "value": geo},
            ],
        }],
    }


def _cloudtrail(ts, user, event_name, ip, *, bucket=None, key_id=None, extra=None):
    record = {
        "source": "cloudtrail",
        "eventTime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eventSource": "s3.amazonaws.com" if bucket else "iam.amazonaws.com",
        "eventName": event_name,
        "awsRegion": "ap-south-1",
        "sourceIPAddress": ip,
        "userIdentity": {"type": "IAMUser", "userName": user,
                         **({"accessKeyId": key_id} if key_id else {})},
        "requestParameters": {**({"bucketName": bucket} if bucket else {}), **(extra or {})},
    }
    return record


def _github(ts, actor, action, **fields):
    return {
        "source": "github",
        "@timestamp": int(ts.timestamp() * 1000),
        "action": action,
        "actor": actor.split("@")[0].replace(".", ""),
        "actor_email": actor,
        "org": "paykraft",
        **fields,
    }


def generate_baseline(days=14, seed=42):
    """Weeks of normal-looking activity: office-hours logins, pushes, S3 ops."""
    rng = random.Random(seed)
    now = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    for day_offset in range(days, 0, -1):
        day = now - timedelta(days=day_offset)
        if day.weekday() >= 5 and rng.random() < 0.7:
            continue  # most weekends are quiet
        for user, _crit in STAFF:
            ip = rng.choice(BLR_IPS)
            login_at = day.replace(hour=rng.randint(8, 11), minute=rng.randint(0, 59))
            events.append(_workspace_login(login_at, user, ip, OFFICE_GEO))
            # engineers push; finance touches settlement exports
            if "rohan" in user or "priya" in user:
                for _ in range(rng.randint(1, 5)):
                    push_at = login_at + timedelta(hours=rng.uniform(0.5, 8))
                    events.append(_github(push_at, user, "git.push",
                                          repo=f"paykraft/{rng.choice(REPOS)}"))
            if "priya" in user or "arjun" in user:
                for _ in range(rng.randint(0, 3)):
                    op_at = login_at + timedelta(hours=rng.uniform(1, 7))
                    events.append(_cloudtrail(op_at, user.split("@")[0], "GetObject",
                                              ip, bucket=rng.choice(BUCKETS),
                                              extra={"key": f"reports/daily-{day:%Y%m%d}.csv"}))
        # nightly backup job — the normal reason the backup bucket sees traffic
        backup_at = day.replace(hour=2, minute=15)
        events.append(_cloudtrail(backup_at, "backup-svc", "PutObject", "10.0.3.21",
                                  bucket="customers-db-backups",
                                  extra={"key": f"nightly/{day:%Y%m%d}.dump.gz"}))
    events.sort(key=_event_time)
    return events


def generate_inc042(attack_day=None):
    """The INC-042 chain: impossible travel → MFA fatigue → PAT → key → S3 exfil."""
    day = attack_day or datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    user = "priya.sharma@paykraft.in"
    events = []

    # 22:47 previous evening — legitimate Bengaluru login (the travel baseline)
    events.append(_workspace_login(day - timedelta(hours=1, minutes=13), user,
                                   BLR_IPS[1], OFFICE_GEO))
    t = day + timedelta(hours=3, minutes=11)
    # 03:11 — Moscow login after MFA fatigue (3 denials then an approval)
    for attempt in range(1, 4):
        events.append(_workspace_login(t + timedelta(seconds=20 * attempt), user,
                                       MOSCOW_IP, "RU-MOW", mfa="push_denied",
                                       success=False, attempt=attempt))
    events.append(_workspace_login(t + timedelta(minutes=3), user, MOSCOW_IP, "RU-MOW",
                                   mfa="push_approved", attempt=4))
    # 03:19 — persistence: new PAT with broad scopes
    events.append(_github(day + timedelta(hours=3, minutes=19), user,
                          "personal_access_token.create",
                          token_id=4821, scopes=["repo", "admin:org"]))
    # 03:26 — clone infra repo (where the AWS key lives in Terraform history)
    events.append(_github(day + timedelta(hours=3, minutes=26), user, "git.clone",
                          repo="paykraft/paykraft-infra", token_id=4821))
    # 03:31 — S3 exfil burst with the recovered key
    exfil_start = day + timedelta(hours=3, minutes=31)
    for i in range(12):  # a burst of GetObject (downsampled from 1,842 for replay)
        events.append(_cloudtrail(exfil_start + timedelta(seconds=2 * i), "priya.sharma",
                                  "GetObject", MOSCOW_IP, bucket="customers-db-backups",
                                  key_id="AKIA55XN7QX7Q",
                                  extra={"key": f"nightly/part-{i:03d}.dump.gz"}))
    for e in events:
        e["attack"] = True
        e["scenario"] = "inc-042"
    return events


def generate_insider_export(attack_day=None):
    """PT-02: a legitimate identity bulk-exports the customer table off-hours."""
    day = attack_day or datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    user = "deepa.nair@paykraft.in"
    t = day + timedelta(hours=23, minutes=40)
    events = [_workspace_login(t, user, BLR_IPS[3], OFFICE_GEO)]
    for i in range(8):
        events.append(_cloudtrail(t + timedelta(minutes=5 + i), "deepa.nair", "GetObject",
                                  BLR_IPS[3], bucket="customers-db-backups",
                                  extra={"key": f"nightly/part-{i:03d}.dump.gz"}))
    for e in events:
        e["attack"] = True
        e["scenario"] = "insider-export"
    return events


SCENARIOS = {
    "baseline": generate_baseline,
    "inc-042": generate_inc042,
    "insider-export": generate_insider_export,
}


def _event_time(event) -> datetime:
    if event["source"] == "workspace":
        return datetime.fromisoformat(event["id"]["time"])
    if event["source"] == "cloudtrail":
        return datetime.strptime(event["eventTime"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    return datetime.fromtimestamp(event["@timestamp"] / 1000, tz=timezone.utc)


def normalize(event) -> dict:
    """Flatten any of the three source formats into the RawEvent envelope."""
    when = _event_time(event)
    if event["source"] == "workspace":
        params = {p["name"]: p.get("value", p.get("intValue"))
                  for p in event["events"][0]["parameters"]}
        return {
            "source": "workspace",
            "event_type": event["events"][0]["name"],
            "principal": event["actor"]["email"],
            "target": "google-workspace",
            "ip": event["ipAddress"],
            "geo": params.get("geo", ""),
            "occurred_at": when,
            "payload": {"mfa": params.get("login_challenge_method"),
                        "attempt": params.get("challenge_attempt")},
        }
    if event["source"] == "cloudtrail":
        return {
            "source": "cloudtrail",
            "event_type": event["eventName"],
            "principal": event["userIdentity"]["userName"],
            "target": event["requestParameters"].get("bucketName", "aws"),
            "ip": event["sourceIPAddress"],
            "geo": "",
            "occurred_at": when,
            "payload": {"key": event["requestParameters"].get("key"),
                        "accessKeyId": event["userIdentity"].get("accessKeyId")},
        }
    return {
        "source": "github",
        "event_type": event["action"],
        "principal": event.get("actor_email", event["actor"]),
        "target": event.get("repo", "github"),
        "ip": None,
        "geo": "",
        "occurred_at": when,
        "payload": {k: v for k, v in event.items()
                    if k in ("token_id", "scopes", "repo", "org")},
    }
