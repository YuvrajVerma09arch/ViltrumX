"""
Geo-IP enrichment tool (CLAUDE.md §4 Agent 1 + §5 L1).

Resolves an IP → (country_code, region, city, isp) without external services
so the orchestrator container never has to call out to a paid GeoIP API at
demo time. The bundled map covers every IP the synthetic generator produces
plus a small blocklist of known TOR/anonymous exit nodes (the demo Russia IP
plus a few TOR exits). Anything missing resolves to a deferred 'unknown' and
the Investigation agent treats unknown as suspicious-by-default for off-hours
international traffic per the Detection agent's geo-mismatch feature.

In a production rollout this module would answer to a MaxMind GeoLite2 reader
behind a Redis cache, but the call signature is stable.
"""

from __future__ import annotations

# in-memory table — (country_iso, region_code, city, isp, is_anonymous_proxy)
_DB = {
    # Bengaluru office
    "49.207.184.12": ("IN", "KA", "Bengaluru", "Airtel Broadband", False),
    "106.51.72.89": ("IN", "KA", "Bengaluru", "Airtel Broadband", False),
    "122.171.20.44": ("IN", "KA", "Bengaluru", "Tata Communications", False),
    "14.142.110.7": ("IN", "MH", "Mumbai", "Tata Communications", False),
    # on-prem private RFC1918 (the backup-svc scheduler IP)
    "10.0.3.21": ("IN", "KA", "Bengaluru", "PayKraft internal", False),
    # Moscow TOR/anonymous exit
    "185.220.101.34": ("RU", "MOW", "Moscow", "anonymous proxy registrar", True),
    # synthetic unknown CloudTrail events before any geo enrichment
    "203.0.113.55": ("IN", "DL", "New Delhi", "Jio Fiber", False),
    "198.51.100.7": ("SG", "01", "Singapore", "DigitalOcean", False),
}


def resolve(ip: str | None) -> dict:
    """Enrich an IP. Always returns a dict with the same keys so callers can
    safely destructure — `is_anonymous_proxy=True` means 'treat as hostile
    origin regardless of authentication success'.
    """
    if not ip:
        return {"ip": None, "country": None, "region": None, "city": None,
                "isp": None, "is_anonymous_proxy": False, "known": False}
    row = _DB.get(ip)
    if row is None:
        return {"ip": ip, "country": None, "region": None, "city": None,
                "isp": None, "is_anonymous_proxy": None, "known": False}
    country, region, city, isp, anon = row
    return {"ip": ip, "country": country, "region": region, "city": city,
            "isp": isp, "is_anonymous_proxy": anon, "known": True}


def is_office_geo(country: str | None, region: str | None) -> bool:
    """True for our Bengaluru office. Cheap check the Investigation agent uses
    to fail impossible-travel fast (legitimate home-office logins can't trigger
    international impossible-travel)."""
    return country == "IN" and region == "KA"
