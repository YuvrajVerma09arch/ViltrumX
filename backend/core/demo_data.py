"""
PayKraft demo fixtures — a 1:1 transliteration of frontend/src/data/mock.ts.

These dicts ARE the API contract (docs/ARCHITECTURE.md §10): stub views serve
them verbatim, so the frontend renders identically whether VITE_USE_API is on
or off. As each real implementation lands (Weeks 1–4), the corresponding view
stops importing from this module — a screen is "done" when deleting its
fixture here changes nothing.

Field names are camelCase to match the TS types exactly. Keep it that way in
real serializers too — renaming fields breaks the built frontend.
"""

AGENTS = [
    {"id": "ingest", "name": "Ontology Sync", "role": "Ingestion", "status": "active", "currentTask": "Resolving CloudTrail batch → 214 objects", "stat": "48.2k events/hr"},
    {"id": "noise", "name": "Noise-Gate", "role": "Triage", "status": "active", "currentTask": "Clustered 312 alerts → 9 candidates", "stat": "97.1% suppressed"},
    {"id": "predict", "name": "Threat Prediction", "role": "Forecasting", "status": "idle", "currentTask": "Next risk forecast at 04:00 IST", "stat": "3 entities trending ↑"},
    {"id": "detect", "name": "Detection", "role": "Behavioral ML", "status": "active", "currentTask": "Scoring login anomaly — priya.sharma", "stat": "IF score 0.94"},
    {"id": "invest", "name": "Digital Detective", "role": "Investigation", "status": "active", "currentTask": "Building attack chain for INC-042", "stat": "5-step chain"},
    {"id": "critic", "name": "Verification Critic", "role": "Adversarial review", "status": "active", "currentTask": "Attempting to refute INC-042 finding", "stat": "refutation failed"},
    {"id": "respond", "name": "Response Commander", "role": "Governed actions", "status": "awaiting approval", "currentTask": "L4 proposal: disable priya.sharma", "stat": "3 actions fired"},
    {"id": "explain", "name": "Explainability", "role": "Reporting", "status": "active", "currentTask": "Rendering narrative — EN·HI·GU", "stat": "CERT-In draft ready"},
]

INCIDENTS = [
    {"id": "INC-042", "title": "Credential compromise chain: impossible travel → PAT abuse → S3 exfil attempt", "severity": "critical", "status": "contained", "entity": "priya.sharma@paykraft.in", "time": "03:31 IST today", "mitre": ["T1078", "T1621", "T1098", "T1530"]},
    {"id": "INC-041", "title": "Brute-force burst against VPN gateway (410 attempts, 6 min)", "severity": "high", "status": "contained", "entity": "vpn.paykraft.in", "time": "yesterday 21:14", "mitre": ["T1110"]},
    {"id": "INC-040", "title": "Dormant service account attempted privilege escalation", "severity": "medium", "status": "resolved", "entity": "backup-svc@paykraft.in", "time": "2 days ago", "mitre": ["T1078.004"]},
    {"id": "INC-039", "title": "Anomalous OAuth grant to unverified third-party app", "severity": "low", "status": "resolved", "entity": "rohan.iyer@paykraft.in", "time": "4 days ago", "mitre": ["T1550"]},
    {"id": "INC-038", "title": "S3 bucket policy drift — public read on staging assets", "severity": "medium", "status": "resolved", "entity": "s3://paykraft-staging-assets", "time": "6 days ago", "mitre": ["T1530"]},
]

ACTIVITY_FEED = [
    {"t": "03:31:12", "agent": "Response", "line": "ACT-2212 block_ip 185.220.101.34 executed (L3, auto-rollback 04:31)", "tone": "action"},
    {"t": "03:31:09", "agent": "Response", "line": "ACT-2211 rotate_key AWS AKIA···X7Q executed (L2) — owner notified", "tone": "action"},
    {"t": "03:31:04", "agent": "Response", "line": "ACT-2210 revoke_session priya.sharma executed (L2) — Slack notify sent", "tone": "action"},
    {"t": "03:30:58", "agent": "Critic", "line": "INC-042 finding survives adversarial review — confidence 0.96", "tone": "ok"},
    {"t": "03:29:41", "agent": "Detective", "line": "Attack chain assembled: 5 steps, 4 MITRE techniques, 2 crown jewels in blast radius", "tone": "warn"},
    {"t": "03:27:10", "agent": "Detection", "line": "s3:GetObject burst on customers-db-backups — 2.3 GB requested, anomaly 0.94", "tone": "warn"},
    {"t": "03:19:33", "agent": "Ingestion", "line": "GitHub audit: PAT #4821 created on priya.sharma session — linked to ontology", "tone": "info"},
    {"t": "03:11:02", "agent": "Detection", "line": "Impossible travel: Bengaluru 22:47 → Moscow 03:11 (4,970 km / 4.4 h)", "tone": "warn"},
    {"t": "03:00:00", "agent": "PurpleTeam", "line": "Nightly validation sweep complete — 4/4 scenarios caught, readiness 94%", "tone": "ok"},
]

ONT_NODES = [
    {"id": "u-arjun", "label": "arjun.mehta", "type": "user", "criticality": "high", "x": 40, "y": 40, "meta": "Founder & CEO · Owner role"},
    {"id": "u-priya", "label": "priya.sharma", "type": "user", "criticality": "high", "x": 40, "y": 190, "compromised": True, "meta": "CTO · Admin on AWS + GitHub"},
    {"id": "u-rohan", "label": "rohan.iyer", "type": "user", "criticality": "medium", "x": 40, "y": 340, "meta": "Backend engineer"},
    {"id": "u-deepa", "label": "deepa.nair", "type": "user", "criticality": "medium", "x": 40, "y": 490, "meta": "Finance lead · Razorpay access"},
    {"id": "s-ci", "label": "ci-deploy-bot", "type": "service", "criticality": "high", "x": 300, "y": 40, "meta": "Service account · deploys prod"},
    {"id": "k-pat", "label": "GitHub PAT #4821", "type": "apikey", "criticality": "high", "x": 300, "y": 190, "compromised": True, "meta": "Created 03:19 IST — revoked"},
    {"id": "k-aws", "label": "AWS key AKIA···X7Q", "type": "apikey", "criticality": "crown-jewel", "x": 300, "y": 340, "compromised": True, "meta": "Found in repo history — rotated"},
    {"id": "d-priya", "label": "priya-macbook", "type": "device", "criticality": "medium", "x": 300, "y": 490, "meta": "Last seen Bengaluru 22:47"},
    {"id": "r-core", "label": "paykraft-core", "type": "repo", "criticality": "crown-jewel", "x": 560, "y": 120, "meta": "Payments monolith · private"},
    {"id": "r-infra", "label": "paykraft-infra", "type": "repo", "criticality": "high", "x": 560, "y": 270, "meta": "Terraform + secrets history"},
    {"id": "c-s3", "label": "s3://customers-db-backups", "type": "cloud", "criticality": "crown-jewel", "x": 820, "y": 120, "compromised": True, "meta": "Nightly PII dumps · 2.3 GB targeted"},
    {"id": "c-rds", "label": "rds/payments-db", "type": "cloud", "criticality": "crown-jewel", "x": 820, "y": 270, "meta": "Production ledger"},
    {"id": "c-ec2", "label": "ec2/prod-api", "type": "cloud", "criticality": "high", "x": 820, "y": 420, "meta": "6 instances · ap-south-1"},
    {"id": "sa-gw", "label": "Google Workspace", "type": "saas", "criticality": "high", "x": 560, "y": 420, "meta": "68 identities · SSO root"},
    {"id": "sa-rzp", "label": "Razorpay", "type": "saas", "criticality": "crown-jewel", "x": 560, "y": 540, "meta": "Payment rail · settlement acct"},
    {"id": "dt-pii", "label": "Customer PII dataset", "type": "data", "criticality": "crown-jewel", "x": 1080, "y": 190, "meta": "412k records · DPDP-scoped"},
]

ONT_EDGES = [
    {"id": "e1", "source": "u-priya", "target": "sa-gw", "label": "authenticates_to"},
    {"id": "e2", "source": "u-priya", "target": "k-pat", "label": "owns", "attack": True},
    {"id": "e3", "source": "k-pat", "target": "r-core", "label": "has_access_to", "attack": True},
    {"id": "e4", "source": "r-infra", "target": "k-aws", "label": "leaked_in_history", "attack": True},
    {"id": "e5", "source": "k-aws", "target": "c-s3", "label": "has_access_to", "attack": True},
    {"id": "e6", "source": "c-s3", "target": "dt-pii", "label": "contains"},
    {"id": "e7", "source": "u-arjun", "target": "sa-gw", "label": "authenticates_to"},
    {"id": "e8", "source": "u-rohan", "target": "r-core", "label": "has_access_to"},
    {"id": "e9", "source": "u-deepa", "target": "sa-rzp", "label": "has_access_to"},
    {"id": "e10", "source": "s-ci", "target": "c-ec2", "label": "deploys_to"},
    {"id": "e11", "source": "s-ci", "target": "r-core", "label": "has_access_to"},
    {"id": "e12", "source": "d-priya", "target": "u-priya", "label": "owned_by"},
    {"id": "e13", "source": "c-rds", "target": "dt-pii", "label": "contains"},
    {"id": "e14", "source": "u-priya", "target": "r-infra", "label": "has_access_to"},
    {"id": "e15", "source": "c-ec2", "target": "c-rds", "label": "communicates_with"},
]

ATTACK_CHAIN = [
    {"time": "03:11", "title": "Impossible-travel login", "detail": "priya.sharma authenticated from 185.220.101.34 (Moscow). Last Bengaluru login 22:47 — 4,970 km in 4.4 h. Isolation Forest anomaly 0.94.", "mitre": "T1078", "mitreName": "Valid Accounts", "severity": "high"},
    {"time": "03:14", "title": "MFA fatigue", "detail": "4 push prompts in 90 s; 3 denied, 4th approved. Cohort baseline: 0 night-time prompts in 90 days.", "mitre": "T1621", "mitreName": "MFA Request Generation", "severity": "high"},
    {"time": "03:19", "title": "Persistence via new PAT", "detail": "GitHub PAT #4821 created with repo + admin:org scopes from the compromised session.", "mitre": "T1098", "mitreName": "Account Manipulation", "severity": "critical"},
    {"time": "03:26", "title": "Secrets discovery in repo history", "detail": "paykraft-infra cloned; AWS key AKIA···X7Q present in Terraform state committed 14 months ago.", "mitre": "T1552", "mitreName": "Unsecured Credentials", "severity": "critical"},
    {"time": "03:31", "title": "S3 exfiltration attempt — blocked", "detail": "s3:GetObject burst on customers-db-backups (2.3 GB, 412k customer records). Session revoked + key rotated mid-transfer; 0 objects retrieved.", "mitre": "T1530", "mitreName": "Data from Cloud Storage", "severity": "critical"},
]

EVIDENCE = [
    {"id": "EV-1", "kind": "GeoIP record", "source": "Google Workspace audit", "excerpt": "ip=185.220.101.34 asn=AS205100 geo=RU-MOW conf=0.98"},
    {"id": "EV-2", "kind": "Auth log", "source": "Workspace login events", "excerpt": "login.success user=priya.sharma mfa=push_approved attempt=4"},
    {"id": "EV-3", "kind": "GitHub audit event", "source": "GitHub connector", "excerpt": "personal_access_token.create scopes=[repo,admin:org] actor=priya.sharma"},
    {"id": "EV-4", "kind": "CloudTrail burst", "source": "AWS CloudTrail", "excerpt": "GetObject x1,842 bucket=customers-db-backups bytes_requested=2.3e9"},
    {"id": "EV-5", "kind": "ML anomaly scores", "source": "Detection agent", "excerpt": "isolation_forest=0.94 peer_cohort_z=4.7 xgboost_tp_prob=0.91"},
]

ACTIONS = [
    {"id": "ACT-2213", "type": "disable_identity", "target": "priya.sharma@paykraft.in", "level": "L4", "status": "proposed", "blastRadius": 0.82, "time": "03:32 IST", "rollback": "re-enable identity + restore sessions"},
    {"id": "ACT-2212", "type": "block_ip", "target": "185.220.101.34", "level": "L3", "status": "executed", "blastRadius": 0.08, "time": "03:31 IST", "rollback": "auto-unblock at 04:31 IST (timer)"},
    {"id": "ACT-2211", "type": "rotate_key", "target": "AWS AKIA···X7Q", "level": "L2", "status": "executed", "blastRadius": 0.24, "time": "03:31 IST", "rollback": "previous key kept in escrow 24 h"},
    {"id": "ACT-2210", "type": "revoke_session", "target": "priya.sharma (Moscow session)", "level": "L2", "status": "executed", "blastRadius": 0.12, "time": "03:31 IST", "rollback": "n/a — user re-authenticates"},
    {"id": "ACT-2201", "type": "block_ip", "target": "91.243.44.18 (VPN brute-force)", "level": "L3", "status": "rolled-back", "blastRadius": 0.06, "time": "yesterday 22:14", "rollback": "auto-rolled-back after 1 h, no recurrence"},
    {"id": "ACT-2188", "type": "force_mfa", "target": "backup-svc@paykraft.in", "level": "L2", "status": "executed", "blastRadius": 0.1, "time": "2 days ago", "rollback": "policy revert available"},
]

PROVENANCE_TRACE = [
    {"step": "Trigger", "detail": "Detection agent flagged impossible-travel + MFA fatigue on priya.sharma (confidence 0.96, Critic-verified)", "ok": True},
    {"step": "Precondition · identity has active session", "detail": "2 active sessions found (Bengaluru laptop, Moscow web) — Moscow session selected", "ok": True},
    {"step": "Precondition · not a break-glass account", "detail": "priya.sharma not in break-glass list", "ok": True},
    {"step": "Precondition · connector write-scope granted", "detail": "Workspace admin scope verified at 03:31:01", "ok": True},
    {"step": "Blast radius", "detail": "0.12 (low) — single session, no dependent service accounts; criticality weight ×1.4 (High identity) applied", "ok": True},
    {"step": "Policy gate", "detail": "revoke_session policy = L2 for High-criticality identities → auto-execute + notify permitted", "ok": True},
    {"step": "Execute", "detail": "Workspace API: session token invalidated at 03:31:04 (214 ms)", "ok": True},
    {"step": "Notify", "detail": "Slack #security-ops + founder WhatsApp digest queued", "ok": True},
    {"step": "Rollback plan", "detail": "None required — user re-authenticates; provenance snapshot stored immutably", "ok": True},
]

RISK_TREND = [
    {"day": "Jun 26", "org": 22, "forecast": None},
    {"day": "Jun 28", "org": 24, "forecast": None},
    {"day": "Jun 30", "org": 21, "forecast": None},
    {"day": "Jul 02", "org": 28, "forecast": None},
    {"day": "Jul 04", "org": 26, "forecast": None},
    {"day": "Jul 06", "org": 31, "forecast": None},
    {"day": "Jul 08", "org": 34, "forecast": None},
    {"day": "Jul 09", "org": 58, "forecast": 58},
    {"day": "Jul 11", "org": None, "forecast": 41},
    {"day": "Jul 13", "org": None, "forecast": 33},
]

ENTITY_RISK = [
    {"entity": "priya.sharma", "type": "Identity", "score": 91, "trend": "+44", "reason": "Active compromise chain (INC-042)"},
    {"entity": "s3://customers-db-backups", "type": "Cloud", "score": 74, "trend": "+31", "reason": "Targeted by exfil attempt; crown jewel"},
    {"entity": "paykraft-infra", "type": "Repo", "score": 62, "trend": "+18", "reason": "Secrets found in history — cleanup pending"},
    {"entity": "backup-svc", "type": "Service acct", "score": 48, "trend": "-6", "reason": "MFA enforced after INC-040"},
    {"entity": "vpn.paykraft.in", "type": "Gateway", "score": 39, "trend": "-12", "reason": "Brute-force source blocked, geo-fence applied"},
]

READINESS_HISTORY = [
    {"week": "W23", "score": 71}, {"week": "W24", "score": 78}, {"week": "W25", "score": 83},
    {"week": "W26", "score": 88}, {"week": "W27", "score": 91}, {"week": "W28", "score": 94},
]

INV_IDENTITIES = [
    {"name": "arjun.mehta@paykraft.in", "kind": "User · Owner", "mfa": True, "risk": 18, "criticality": "high"},
    {"name": "priya.sharma@paykraft.in", "kind": "User · Admin", "mfa": True, "risk": 91, "criticality": "high"},
    {"name": "rohan.iyer@paykraft.in", "kind": "User", "mfa": True, "risk": 22, "criticality": "medium"},
    {"name": "deepa.nair@paykraft.in", "kind": "User · Finance", "mfa": True, "risk": 27, "criticality": "high"},
    {"name": "ci-deploy-bot", "kind": "Service account", "mfa": False, "risk": 35, "criticality": "high"},
    {"name": "backup-svc", "kind": "Service account", "mfa": True, "risk": 48, "criticality": "medium"},
]

INV_CLOUD = [
    {"name": "s3://customers-db-backups", "kind": "S3 bucket", "posture": "Encrypted · private · access-logged", "risk": 74, "criticality": "crown-jewel"},
    {"name": "rds/payments-db", "kind": "RDS Postgres", "posture": "Encrypted · no public endpoint", "risk": 31, "criticality": "crown-jewel"},
    {"name": "ec2/prod-api", "kind": "EC2 ×6", "posture": "IMDSv2 · patched 4 d ago", "risk": 26, "criticality": "high"},
    {"name": "s3://paykraft-staging-assets", "kind": "S3 bucket", "posture": "Public-read fixed (INC-038)", "risk": 12, "criticality": "low"},
]

INV_REPOS = [
    {"name": "paykraft-core", "kind": "Private repo", "posture": "Branch protection · secret scanning ON", "risk": 24, "criticality": "crown-jewel"},
    {"name": "paykraft-infra", "kind": "Private repo", "posture": "Secrets in history — purge scheduled", "risk": 62, "criticality": "high"},
    {"name": "paykraft-web", "kind": "Private repo", "posture": "Branch protection ON", "risk": 15, "criticality": "medium"},
]

INV_SAAS = [
    {"name": "Google Workspace", "kind": "68 identities", "posture": "SSO root · admin alerts wired", "risk": 20, "criticality": "high"},
    {"name": "Razorpay", "kind": "Payment rail", "posture": "Webhook signing · IP allowlist", "risk": 22, "criticality": "crown-jewel"},
    {"name": "Slack", "kind": "64 members", "posture": "App approvals restricted", "risk": 9, "criticality": "medium"},
]

PT_SCENARIOS = [
    {"id": "PT-01", "name": "Credential theft chain", "desc": "Impossible travel → token mint → cloud data pull (mirrors INC-042)", "lastRun": "Last night 03:00", "result": "passed", "detection": "41 s", "containment": "3 m 12 s"},
    {"id": "PT-02", "name": "Insider bulk export", "desc": "Legit identity pulls full customer table outside hours", "lastRun": "Last night 03:12", "result": "passed", "detection": "58 s", "containment": "2 m 40 s"},
    {"id": "PT-03", "name": "Ransomware canary trip", "desc": "Mass-rename + encrypt canary files on shared drive", "lastRun": "Last night 03:24", "result": "warning", "detection": "6 m 02 s", "containment": "8 m 15 s"},
    {"id": "PT-04", "name": "Payment API abuse", "desc": "Replay + amount-tamper against Razorpay webhook path", "lastRun": "Scheduled tonight 03:00", "result": "scheduled", "detection": "—", "containment": "—"},
]

FRAMEWORKS = [
    {"id": "dpdp", "name": "DPDP Act 2023", "region": "India", "status": "Evidence pack ready", "controls": "42/47 controls mapped", "note": "Rules in force Nov 2025; obligations phase in by May 2027. Penalties up to ₹250 Cr."},
    {"id": "certin", "name": "CERT-In Directions", "region": "India", "status": "Incident report drafted", "controls": "6-hour breach window", "note": "INC-042 report auto-drafted at 03:33 IST — 5 h 27 m remaining on the clock."},
    {"id": "rbi", "name": "RBI Cybersecurity Framework", "region": "India · BFSI", "status": "Partial", "controls": "28/61 controls mapped", "note": "Applies via Razorpay settlement account; gap list generated."},
    {"id": "soc2", "name": "SOC 2 Type I", "region": "Global", "status": "In progress", "controls": "31/64 criteria evidenced", "note": "Exports to Sprinto/Scrut-compatible evidence format."},
]

RECENT_EXPORTS = [
    {"name": "CERT-In incident report — INC-042", "kind": "PDF · bilingual EN/HI", "when": "today 03:33 IST"},
    {"name": "DPDP evidence pack — June 2026", "kind": "PDF + JSON manifest", "when": "Jul 01"},
    {"name": "Board security summary — Q1 FY27", "kind": "PDF · Founder Mode", "when": "Jun 28"},
]

MEMBERS = [
    {"name": "Arjun Mehta", "email": "arjun.mehta@paykraft.in", "role": "Owner", "last": "2 m ago"},
    {"name": "Priya Sharma", "email": "priya.sharma@paykraft.in", "role": "Admin", "last": "sessions revoked 03:31"},
    {"name": "Rohan Iyer", "email": "rohan.iyer@paykraft.in", "role": "Analyst", "last": "1 h ago"},
    {"name": "Deepa Nair", "email": "deepa.nair@paykraft.in", "role": "Viewer", "last": "yesterday"},
]

INVOICES = [
    {"id": "VX-2026-072", "period": "Jul 2026", "amount": "₹29,499", "gst": "GST 18% incl.", "status": "paid (UPI autopay)"},
    {"id": "VX-2026-061", "period": "Jun 2026", "amount": "₹29,499", "gst": "GST 18% incl.", "status": "paid (UPI autopay)"},
    {"id": "VX-2026-051", "period": "May 2026", "amount": "₹29,499", "gst": "GST 18% incl.", "status": "paid (UPI autopay)"},
]

CONNECTORS = [
    {"id": "gw", "name": "Google Workspace", "desc": "Identities, login events, admin audit", "status": "connected", "time": "~2 min"},
    {"id": "gh", "name": "GitHub", "desc": "Repos, audit log, PAT & deploy-key events", "status": "connected", "time": "~90 sec"},
    {"id": "aws", "name": "AWS CloudTrail", "desc": "Cloud resources, API activity, S3 access", "status": "connected", "time": "~3 min"},
    {"id": "rzp", "name": "Razorpay", "desc": "Payment events, settlement anomalies", "status": "available", "time": "~2 min"},
    {"id": "slack", "name": "Slack", "desc": "Alert delivery + app-grant monitoring", "status": "available", "time": "~1 min"},
    {"id": "m365", "name": "Microsoft 365", "desc": "Alternative identity + mail telemetry", "status": "available", "time": "~3 min"},
]

DEFAULT_POLICIES = [
    {"actionType": "revoke_session", "level": "L2", "crownJewelOverride": "L2"},
    {"actionType": "force_mfa", "level": "L2", "crownJewelOverride": "L2"},
    {"actionType": "rotate_key", "level": "L2", "crownJewelOverride": "L3"},
    {"actionType": "block_ip", "level": "L3", "crownJewelOverride": "L3"},
    {"actionType": "quarantine_device", "level": "L3", "crownJewelOverride": "L4"},
    {"actionType": "disable_identity", "level": "L4", "crownJewelOverride": "L4"},
]
