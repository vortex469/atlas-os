"""Read-only Installation Capability Assessment building blocks."""

from app.installation_capability.assembly import (
    InstallationCapabilityAssessmentReadDependency,
)
from app.installation_capability.assessment import (
    InstallationCapabilityAssessmentV1,
    RequirementComparisonV1,
    assess_installation_capability,
)
from app.installation_capability.provider_facts import (
    ProviderInstallationCapabilityFactsV1,
    adapt_proxmox_qemu_capability_facts,
)

__all__ = [
    "InstallationCapabilityAssessmentReadDependency",
    "InstallationCapabilityAssessmentV1",
    "ProviderInstallationCapabilityFactsV1",
    "RequirementComparisonV1",
    "adapt_proxmox_qemu_capability_facts",
    "assess_installation_capability",
]
