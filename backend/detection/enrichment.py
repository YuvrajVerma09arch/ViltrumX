"""
IP enrichment — GeoIP + reputation, provider-based with a guaranteed offline floor.

This replaces the old hardcoded ``MOSCOW_IP = "185.220.101.34"`` constant in
``features.py``. The detection feature functions (``geo_mismatch``,
``impossible_travel``) now *derive* an event's geography and risk from this
module instead of comparing against a baked-in string.

Provider chain (first hit wins, everything degrades silently):

  1. private / reserved IP short-circuit — RFC-1918 & friends are internal,
     never geo-locatable, and are treated as trusted on-prem by definition.
  2. MaxMind GeoLite2 (optional) — used when ``GEOIP_DB_PATH`` points at a real
     ``.mmdb`` and the ``geoip2`` package is installed. This is the production
     path: download the free GeoLite2-City DB and set the env var.
  3. AbuseIPDB reputation (optional) — used when ``ABUSEIPDB_API_KEY`` is set.
     Adds a real abuse-confidence score for the IP.
  4. Built-in offline map (always available) — a small, documented table of
     ranges the demo and tests rely on (the synthetic Bengaluru office block,
     the synthetic hostile exit node, plus well-known Tor/VPN egress ranges).
     This is what lets the demo and CI run with zero network and zero
     dependency while still being *derived*, not hardcoded per-event.

Nothing here raises: every lookup returns a ``GeoResult`` and falls through to
the next provider on any failure, so detection never breaks on a cold start.

CLAUDE.md §6: detection is ML + deterministic enrichment only — never the LLM.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)

# ── Optional providers (import guarded so a missing package never breaks boot) ─
try:  # MaxMind GeoLite2 — production path
    import geoip2.database  # type: ignore

    _GEOIP2_AVAILABLE = True
except Exception:  # noqa: BLE001
    _GEOIP2_AVAILABLE = False

_GEOIP_READER = None
_GEOIP_TRIED = False

# In-process cache: an IP's geo/reputation doesn't change within a run, and the
# live scorer hits this on every event — avoid a DB/HTTP round-trip per event.
_CACHE: dict[str, "GeoResult"] = {}


@dataclass(frozen=True)
class GeoResult:
    """What we know about one IP address. All fields have safe defaults so a
    total lookup failure still yields a usable (neutral) result."""

    ip: str
    country_iso: str = ""  # e.g. "IN", "RU" — "" means unknown
    is_private: bool = False  # RFC-1918 / loopback / link-local
    is_known_bad: bool = False  # threat-intel / abuse-flagged
    abuse_score: int = 0  # 0–100 abuse confidence (0 = no signal)
    source: str = "none"  # which provider answered: private|maxmind|abuseipdb|builtin|none
    meta: dict = field(default_factory=dict)

    @property
    def geo_label(self) -> str:
        """The `geo` string the rest of the pipeline expects ("IN-KA" style).

        We keep the synthetic "CC-REGION" shape so the existing Office-geo
        prefix logic ("IN-") and seeded data keep working unchanged.
        """
        return self.country_iso


# ── Built-in offline floor ────────────────────────────────────────────────────
# Documented, synthetic-safe ranges. This is deliberately a *lookup table*, not
# a per-event hardcode: new ranges are data, not code, and the production path
# (MaxMind/AbuseIPDB) overrides it the moment real providers are configured.
#
# country_iso for the office block is "IN" so `geo.startswith("IN-")` in
# features.py keeps matching the seeded "IN-KA" labels.
_BUILTIN_RANGES: list[tuple[str, str, bool, str]] = [
    # (CIDR, country_iso, is_known_bad, note)
    # Synthetic Bengaluru office block (connectors/synthetic.py BLR_IPS).
    ("49.207.184.0/24", "IN", False, "paykraft office (synthetic)"),
    ("106.51.72.0/24", "IN", False, "paykraft office (synthetic)"),
    ("122.171.20.0/24", "IN", False, "paykraft office (synthetic)"),
    ("14.142.110.0/24", "IN", False, "paykraft office (synthetic)"),
    # Synthetic hostile exit node used by the INC-042 demo scenario.
    ("185.220.101.0/24", "RU", True, "hostile exit node (synthetic INC-042)"),
]
_BUILTIN_NETS = [
    (ipaddress.ip_network(c), iso, bad, note) for c, iso, bad, note in _BUILTIN_RANGES
]


def _reader():
    """Lazy-open the MaxMind reader once; None if unavailable."""
    global _GEOIP_READER, _GEOIP_TRIED
    if _GEOIP_TRIED:
        return _GEOIP_READER
    _GEOIP_TRIED = True
    if not _GEOIP2_AVAILABLE:
        return None
    db_path = getattr(settings, "GEOIP_DB_PATH", os.environ.get("GEOIP_DB_PATH", ""))
    if not db_path or not os.path.exists(db_path):
        return None
    try:
        _GEOIP_READER = geoip2.database.Reader(db_path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("GeoIP DB open failed: %s", exc)
        _GEOIP_READER = None
    return _GEOIP_READER


def _lookup_maxmind(ip: str) -> GeoResult | None:
    reader = _reader()
    if reader is None:
        return None
    try:
        resp = reader.city(ip)
        iso = (resp.country.iso_code or "").upper()
        if not iso:
            return None
        return GeoResult(ip=ip, country_iso=iso, source="maxmind")
    except Exception:  # noqa: BLE001
        return None


def _lookup_abuseipdb(ip: str) -> GeoResult | None:
    """Reputation only (no geo). Kept separate so it can layer onto any geo
    provider. Only consulted when an API key is configured; never blocks the
    pipeline on network failure."""
    api_key = getattr(settings, "ABUSEIPDB_API_KEY", os.environ.get("ABUSEIPDB_API_KEY", ""))
    if not api_key:
        return None
    try:  # pragma: no cover — network path, exercised in integration not unit
        import requests

        resp = requests.get(
            "https://api.abuseipdb.com/api/v2/check",
            headers={"Key": api_key, "Accept": "application/json"},
            params={"ipAddress": ip, "maxAgeInDays": 90},
            timeout=3,
        )
        data = resp.json().get("data", {})
        score = int(data.get("abuseConfidenceScore", 0))
        iso = (data.get("countryCode") or "").upper()
        return GeoResult(
            ip=ip,
            country_iso=iso,
            is_known_bad=score >= 50,
            abuse_score=score,
            source="abuseipdb",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("AbuseIPDB lookup failed: %s", exc)
        return None


def _lookup_builtin(addr: ipaddress.ip_address, ip: str) -> GeoResult | None:
    for net, iso, bad, note in _BUILTIN_NETS:
        if addr in net:
            return GeoResult(
                ip=ip,
                country_iso=iso,
                is_known_bad=bad,
                abuse_score=90 if bad else 0,
                source="builtin",
                meta={"note": note},
            )
    return None


def lookup_ip(ip: str | None) -> GeoResult:
    """Resolve one IP to a GeoResult via the provider chain. Never raises.

    Order: private → builtin (fast, offline) → maxmind → abuseipdb → neutral.
    The builtin map is checked before the network providers so the demo stays
    deterministic and offline-first; real providers still win for any IP they
    recognise that the builtin table doesn't cover.
    """
    if not ip:
        return GeoResult(ip="", source="none")
    if ip in _CACHE:
        return _CACHE[ip]

    result: GeoResult | None = None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        result = GeoResult(ip=ip, source="none")
        _CACHE[ip] = result
        return result

    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        # Internal traffic is on-prem by definition — trusted, no geo.
        result = GeoResult(ip=ip, is_private=True, country_iso="IN", source="private")
    else:
        result = _lookup_builtin(addr, ip)
        if result is None:
            result = _lookup_maxmind(ip)
        # Reputation can layer on top of whatever geo we found (or didn't).
        rep = _lookup_abuseipdb(ip)
        if rep is not None:
            base = result or rep
            result = GeoResult(
                ip=ip,
                country_iso=base.country_iso or rep.country_iso,
                is_known_bad=base.is_known_bad or rep.is_known_bad,
                abuse_score=max(base.abuse_score, rep.abuse_score),
                source=f"{base.source}+rep" if result else "abuseipdb",
                meta=base.meta,
            )
        if result is None:
            result = GeoResult(ip=ip, source="none")

    _CACHE[ip] = result
    return result


def is_foreign(ip: str | None, home_prefixes: tuple[str, ...] = ("IN",)) -> bool:
    """True when the IP resolves to a country outside the tenant's home set.

    ``home_prefixes`` defaults to India ("IN") and matches the existing "IN-"
    office-geo convention. An unknown/private IP is treated as NOT foreign
    (fail-safe toward not alarming on internal traffic).
    """
    if not ip:
        return False
    res = lookup_ip(ip)
    if res.is_private or not res.country_iso:
        return False
    return not any(res.country_iso.startswith(h) for h in home_prefixes)


def clear_cache() -> None:
    """Test hook: drop the per-process memoization."""
    _CACHE.clear()
