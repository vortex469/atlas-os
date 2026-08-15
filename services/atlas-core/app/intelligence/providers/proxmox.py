from app.intelligence.findings import Finding, Severity
from app.intelligence.proxmox_rules import evaluate_proxmox
from app.models.resources import ProviderResource, ProviderResourceExpectation
from app.provider_intents.authority import get_monitoring_intent_authority
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_management import project_managed_resource
from app.services.proxmox_service import (
    get_proxmox_guests,
    get_proxmox_status,
)


def collect_proxmox_findings() -> list[Finding]:
    try:
        status = get_proxmox_status()
        guests = get_proxmox_guests()
        authority = get_monitoring_intent_authority()
        node = str(guests.get("node", status.get("node", "unknown")))
        projections = tuple(
            project_managed_resource(_resource(guest, node))
            for guest in guests.get("guests", [])
        )
        monitoring_intent = authority.resolve_intelligence(projections)

        return evaluate_proxmox(
            status=status,
            guests=guests,
            monitoring_intent=monitoring_intent,
        )
    except Exception as error:  # noqa: BLE001 - preserve provider failure isolation
        return [
            Finding(
                id="proxmox-provider-failure",
                severity=Severity.CRITICAL,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Proxmox monitoring failed",
                message=(
                    "ACE could not collect Proxmox status: "
                    f"{error}"
                ),
                recommendation=(
                    "Verify Proxmox connectivity, API credentials, "
                    "token permissions, and node configuration."
                ),
                details={
                    "error": str(error),
                },
                score_penalty=20,
            )
        ]


def _resource(guest: dict, node: str) -> ProviderResource:
    resource_type = str(guest.get("type", "unknown"))
    identity = None
    if resource_type == "qemu" and guest.get("vmgenid"):
        identity = build_proxmox_qemu_identity(
            node=node,
            vmid=guest.get("vmid"),
            vmgenid=str(guest["vmgenid"]),
        )
    return ProviderResource(
        provider_id="proxmox",
        resource_id=str(guest.get("vmid")),
        display_name=str(guest.get("name") or f"Proxmox guest {guest.get('vmid')}"),
        resource_type=resource_type,
        current_state=str(guest.get("status", "unknown")),
        identity=identity,
        expectation=ProviderResourceExpectation(),
        configured=False,
    )
