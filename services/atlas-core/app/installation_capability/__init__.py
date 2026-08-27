"""Read-only Installation Capability Assessment building blocks."""

from app.installation_capability.provider_facts import (
    ProviderInstallationCapabilityFactsV1,
    adapt_proxmox_qemu_capability_facts,
)

__all__ = [
    "ProviderInstallationCapabilityFactsV1",
    "adapt_proxmox_qemu_capability_facts",
]
