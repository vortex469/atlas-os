from app.intelligence.findings import Finding, Severity
from app.intelligence.proxmox_rules import evaluate_proxmox
from app.services.proxmox_service import (
    get_proxmox_guests,
    get_proxmox_status,
)


def collect_proxmox_findings() -> list[Finding]:
    try:
        status = get_proxmox_status()
        guests = get_proxmox_guests()

        return evaluate_proxmox(
            status=status,
            guests=guests,
        )
    except Exception as error:
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
