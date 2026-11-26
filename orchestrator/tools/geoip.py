"""
Geo-IP enrichment tool (CLAUDE.md §4 Agent 1 + §5 L1).

Resolves an IP → (country_code, region, city, isp, is_anonymous_proxy).

Provider chain (first hit wins, all degrade silently):
  1. RFC-1918 / private ranges → treated as on-prem, known but never foreign.
  2. MaxMind GeoLite2 — used when ``GEOIP_DB_PATH`` points at a real ``.mmdb``
     and the ``geoip2`` package is installed. This is the production path.
  3. A SMALL documented offline table covering only the ranges the synthetic
     generator produces (so the demo/tests run with zero network). No real
     customer's IP is hardcoded here.

Unknown public IPs resolve to ``known=False`` — callers must NOT treat that as
"safe"; the Detection agent treats off-hours foreign/unknown as suspicious.

An optional reputation provider (AbuseIPDB) can set ``ABUSEIPDB_API_KEY`` in a
future rollout; it is intentionally not called here to keep enrichment offline.
"""

from __future__ import annotations

import ipaddress
import logging
import os

logger = logging.getLogger(__name__)

# Optional MaxMind reader (production path). Import-guarded.
try:  # pragma: no cover - depends on optional dep + DB file
    import geoip2.database  # type: ignore

    _GEOIP2_AVAILABLE = True
except Exception:  # noqa: BLE001
    _GEOIP2_AVAILABLE = False

_READER = None
_READER_TRIED = False

# Offline floor: only the synthetic generator's documented ranges, plus
# well-known example/Tor egress. This is DEMO data, not customer data.
_OFFLINE = {
    "49.207.184.12": ("IN", "KA", "Bengaluru", "Airtel Broadband", False),
    "106.51.72.89": ("IN", "KA", "Bengaluru", "Airtel Broadband", False),
    "122.171.20.44": ("IN", "KA", "Bengaluru", "Tata Communications", False),
    "14.142.110.7": ("IN", "MH", "Mumbai", "Tata Communications", False),
    "203.0.113.55": ("IN", "DL", "New Delhi", "Jio Fiber", False),  # TEST-NET-3 (RFC 5737)
    "198.51.100.7": ("SG", "01", "Singapore", "DigitalOcean", False),  # TEST-NET-2
}


def _get_reader():
    """Lazy-load the MaxMind reader once when GEOIP_DB_PATH is configured."""
    global _READER, _READER_TRIED
    if _READER_TRIED:
        return _READER
    _READER_TRIED = True
    path = os.environ.get("GEOIP_DB_PATH", "")
    if not path or not _GEOIP2_AVAILABLE:
        return None
    try:  # pragma: no cover
        _READER = geoip2.database.Reader(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GeoIP DB failed to open (%s): %s", path, exc)
        _READER = None
    return _READER


def _is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def resolve(ip: str | None) -> dict:
    """Enrich an IP. Always returns the same keys so callers can destructure.

    ``is_anonymous_proxy=True`` means 'treat as hostile origin regardless of
    authentication success'. ``known=False`` means we have no location — the
    caller decides; it is NOT evidence of safety.
    """
    empty = {"ip": None, "country": None, "region": None, "city": None,
             "isp": None, "is_anonymous_proxy": False, "known": False}
    if not ip:
        return empty

    if _is_private(ip):
        return {"ip": ip, "country": None, "region": None, "city": "on-prem",
                "isp": "on-prem", "is_anonymous_proxy": False, "known": True}

    reader = _get_reader()
    if reader is not None:  # pragma: no cover - needs mmdb file
        try:
            city = reader.city(ip)
            return {
                "ip": ip,
                "country": city.country.iso_code,
                "region": city.subdivisions.most_specific.iso_code if city.subdivisions else None,
                "city": city.city.name,
                "isp": None,
                "is_anonymous_proxy": bool(
                    getattr(city.traits, "is_anonymous_proxy", False)
                    or getattr(city.traits, "is_anonymous_vpn", False)
                ),
                "known": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("GeoIP lookup failed for %s: %s", ip, exc)

    row = _OFFLINE.get(ip)
    if row is not None:
        country, region, city, isp, anon = row
        return {"ip": ip, "country": country, "region": region, "city": city,
                "isp": isp, "is_anonymous_proxy": anon, "known": True}

    # Unknown public IP — do not pretend it is safe.
    return {"ip": ip, "country": None, "region": None, "city": None,
            "isp": None, "is_anonymous_proxy": None, "known": False}


def is_office_geo(country: str | None, region: str | None, home_country: str = "IN") -> bool:
    """True for a tenant's home-country corporate network. Cheap check the
    Investigation agent uses to fail impossible-travel fast (legitimate
    same-country logins can't trigger international impossible-travel)."""
    return bool(country) and country == home_country
