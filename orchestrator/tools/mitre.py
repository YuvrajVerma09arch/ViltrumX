"""
MITRE ATT&CK mapping tool (CLAUDE.md §4 Agent 5).

The Investigation agent calls `lookup(event_signature)` to attach a MITRE
technique ID + name to each attack-chain step. Mapping is kept deliberately
small but covers every demo + realistic startup attack vector — anything not
here falls back to a 'Unspecified Behavior' sentinel which the Critic then
weakens the confidence on (intentional cost of an unmapped technique).

Each entry carries a `confidence` between 0–1 — T1078 impossible-travel is
high-confidence because the impossible-travel ML feature is the trigger,
T1621 MFA-fatigue is medium-confidence because it relies on MFA-attempt-count.
"""

from __future__ import annotations

UNKNOWN = {"id": "T9999", "name": "Unspecified Behavior", "tactic": "unknown", "confidence": 0.4}

_MITRE = {
    "T1078": {"id": "T1078", "name": "Valid Accounts", "tactic": "Defense Evasion + Persistence + Initial Access", "confidence": 0.85},  # noqa: E501
    "T1110": {"id": "T1110", "name": "Brute Force", "tactic": "Credential Access", "confidence": 0.9},  # noqa: E501
    "T1621": {"id": "T1621", "name": "Multi-Factor Authentication Request Generation", "tactic": "Credential Access", "confidence": 0.78},  # noqa: E501
    "T1098": {"id": "T1098", "name": "Account Manipulation", "tactic": "Persistence + Privilege Escalation", "confidence": 0.82},  # noqa: E501
    "T1098.001": {"id": "T1098.001", "name": "Additional Cloud Credentials", "tactic": "Persistence", "confidence": 0.85},  # noqa: E501
    "T1552": {"id": "T1552", "name": "Unsecured Credentials", "tactic": "Credential Access", "confidence": 0.88},  # noqa: E501
    "T1552.001": {"id": "T1552.001", "name": "Credentials In Files", "tactic": "Credential Access", "confidence": 0.88},  # noqa: E501
    "T1213": {"id": "T1213", "name": "Data from Information Repositories", "tactic": "Collection", "confidence": 0.75},  # noqa: E501
    "T1530": {"id": "T1530", "name": "Data from Cloud Storage", "tactic": "Collection", "confidence": 0.92},  # noqa: E501
    "T1048": {"id": "T1048", "name": "Exfiltration Over Alternative Protocol", "tactic": "Exfiltration", "confidence": 0.9},  # noqa: E501
    "T1537": {"id": "T1537", "name": "Transfer Data to Cloud Account", "tactic": "Exfiltration", "confidence": 0.88},  # noqa: E501
    "T1078.004": {"id": "T1078.004", "name": "Cloud Accounts", "tactic": "Initial Access", "confidence": 0.85},  # noqa: E501
    "T1136": {"id": "T1136", "name": "Create Account", "tactic": "Persistence", "confidence": 0.8},  # noqa: E501
    "T1090": {"id": "T1090", "name": "Proxy", "tactic": "Command and Control", "confidence": 0.65},  # noqa: E501
    "T1027": {"id": "T1027", "name": "Obfuscated Files or Information", "tactic": "Defense Evasion", "confidence": 0.6},  # noqa: E501
}

# Signature → MITRE technique ID(s). A battle chain is built by the
# Investigation agent matching each step against this map.
SIGNATURES = {
    "impossible_travel": "T1078",
    "login_failure": "T1110",           # repeated login failures = brute force
    "mfa_fatigue": "T1621",             # MFA-push-spam attacks
    "login_success_anomaly": "T1078.004",  # successful login after fatigue
    "token_creation": "T1098.001",       # PAT or new cloud key created
    "key_creation": "T1098.001",
    "repo_clone_elevated": "T1213",      # cloning infra repos for secrets
    "secret_discovery": "T1552.001",     # AWS keys found in terraform history
    "s3_exfil_burst": "T1530",           # bulk GetObject to a backup bucket
    "data_exfil": "T1048",
    "insider_export": "T1530",           # PT-02 insider bulk export
    "priv_escalation": "T1078.004",
    "anomaly": "T1078",
}


def lookup(signature: str) -> dict:
    """Resolve a finding signature to its MITRE technique (dict). Empty/unknown
    signatures return the sentinel so the Critic can penalize unmapped chains.
    """
    if not signature:
        return dict(UNKNOWN)
    tid = SIGNATURES.get(signature)
    if tid and tid in _MITRE:
        m = _MITRE[tid]
        return {"id": m["id"], "name": m["name"], "tactic": m["tactic"],
                "confidence": m["confidence"], "signature": signature}
    return dict(UNKNOWN)


def tactic_for(technique_id: str) -> str:
    return _MITRE.get(technique_id, {}).get("tactic", "unknown")
