"""AWS actuators — block/unblock source IP at a security group or NACL."""

from __future__ import annotations

import logging

from actions.actuators.base import ActuationResult, failed, manual, real

logger = logging.getLogger(__name__)

_CIDR_SUFFIX = "/32"


def _client(tenant):
    """Return a boto3 ec2 client for the tenant, or None when not configured."""
    try:
        from connectors.providers import aws

        if not aws.is_configured():
            return None
        session = aws._session()
        region = (aws._regions() or ["ap-south-1"])[0]
        return session.client("ec2", region_name=region)
    except Exception as exc:  # noqa: BLE001
        logger.debug("AWS actuator unavailable: %s", exc)
        return None


def _security_group_id(tenant) -> str:
    from connectors.models import Connector

    c = Connector.objects.filter(tenant=tenant, connector_id="aws").first()
    if not c:
        return ""
    creds = c.credentials if isinstance(c.credentials, dict) else {}
    return creds.get("security_group_id", "")


def block_ip(tenant, action) -> ActuationResult:
    """Add a deny rule for the source IP to the tenant's egress/ingress SG.

    Only meaningful with a real security group id configured on the AWS
    connector; otherwise it is honestly a manual step.
    """
    sg = _security_group_id(tenant)
    ip = (action.target or "").strip()
    if not sg:
        return manual(
            "No AWS security group configured; block the IP at your firewall manually."
        )
    if not ip:
        return manual("No IP on the action target.")
    client = _client(tenant)
    if client is None:
        return manual(
            "AWS credentials unavailable; block the IP at your firewall manually."
        )
    cidr = ip if "/" in ip else ip + _CIDR_SUFFIX
    try:
        client.authorize_security_group_ingress(
            GroupId=sg,
            IpPermissions=[{
                "IpProtocol": "-1",
                "IpRanges": [
                    {"CidrIp": cidr, "Description": f"viltrumx-block-{action.external_id}"}
                ],
            }],
        )
    except Exception as exc:  # noqa: BLE001
        return failed(f"AWS authorize_security_group_ingress failed: {exc}")
    return real(
        {"provider": "aws", "security_group_id": sg, "cidr": cidr},
        f"Blocked {cidr} on {sg}",
    )


def revert_block_ip(tenant, action) -> ActuationResult:
    r = action.execution_receipt or {}
    sg, cidr = r.get("security_group_id"), r.get("cidr")
    if not (sg and cidr):
        return manual("No block receipt to revert; unblock the IP manually.")
    client = _client(tenant)
    if client is None:
        return manual("AWS credentials unavailable; unblock the IP manually.")
    try:
        client.revoke_security_group_ingress(
            GroupId=sg,
            IpPermissions=[{"IpProtocol": "-1", "IpRanges": [{"CidrIp": cidr}]}],
        )
    except Exception as exc:  # noqa: BLE001
        return failed(f"AWS revoke_security_group_ingress failed: {exc}")
    return real({}, f"Unblocked {cidr} on {sg}")
