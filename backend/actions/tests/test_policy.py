"""
Unit tests for resolve_level() — the policy gate.
Pure Python, no Django, no DB.
"""


from actions.policy import resolve_level

DEFAULT_RULES = [
    {"actionType": "revoke_session", "level": "L2", "crownJewelOverride": "L2"},
    {"actionType": "force_mfa", "level": "L2", "crownJewelOverride": "L2"},
    {"actionType": "rotate_key", "level": "L2", "crownJewelOverride": "L3"},
    {"actionType": "block_ip", "level": "L3", "crownJewelOverride": "L3"},
    {"actionType": "quarantine_device", "level": "L3", "crownJewelOverride": "L4"},
    {"actionType": "disable_identity", "level": "L4", "crownJewelOverride": "L4"},
]


def test_normal_low_criticality():
    assert resolve_level("revoke_session", "low", DEFAULT_RULES) == "L2"


def test_normal_medium_criticality():
    assert resolve_level("block_ip", "medium", DEFAULT_RULES) == "L3"


def test_high_criticality_bumps_to_l2_minimum():
    # rotate_key base is L2 — high criticality keeps it at L2 (already ≥ L2)
    assert resolve_level("rotate_key", "high", DEFAULT_RULES) == "L2"


def test_crown_jewel_triggers_override():
    # rotate_key: base L2, crownJewelOverride L3 → crown jewel target → L3
    assert resolve_level("rotate_key", "crown-jewel", DEFAULT_RULES) == "L3"


def test_crown_jewel_within_2_hops_triggers_override():
    # quarantine_device: base L3, override L4 → crown jewel in blast set → L4
    assert (
        resolve_level(
            "quarantine_device", "medium", DEFAULT_RULES, crown_jewel_within_2_hops=True
        )
        == "L4"
    )


def test_unknown_action_type_defaults_to_l4():
    assert resolve_level("nuke_everything", "low", DEFAULT_RULES) == "L4"


def test_empty_policy_defaults_to_l4():
    assert resolve_level("revoke_session", "low", []) == "L4"


def test_disable_identity_always_l4():
    for criticality in ("low", "medium", "high", "crown-jewel"):
        assert resolve_level("disable_identity", criticality, DEFAULT_RULES) == "L4"


def test_high_criticality_never_resolves_below_l2():
    # Hypothetical rule with L1 base — high criticality must bump to L2
    rules = [{"actionType": "enrich_only", "level": "L1", "crownJewelOverride": "L1"}]
    assert resolve_level("enrich_only", "high", rules) == "L2"


def test_crown_jewel_underscore_variant_normalised():
    # Some callers may pass "crown_jewel" (DB enum) instead of "crown-jewel"
    assert resolve_level("rotate_key", "crown_jewel", DEFAULT_RULES) == "L3"
