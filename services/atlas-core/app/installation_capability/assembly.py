"""Server-owned, ephemeral Installation Capability Assessment assembly."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.installation_capability.assessment import (
    InstallationCapabilityAssessmentV1,
    assess_installation_capability,
)
from app.installation_capability.provider_facts import (
    adapt_proxmox_qemu_capability_facts,
)
from app.installation_plan.contract import InstallationPlan
from app.installation_targets.contract import InstallationDestinationSelectionV1
from app.installation_targets.resolver import TargetResolver, project_destination


class InstallationCapabilityAssessmentReadDependency:
    """Assemble one capability assessment from bounded read-side observations."""

    def __init__(
        self,
        *,
        target_resolver: TargetResolver,
        clock: Callable[[], datetime],
    ) -> None:
        self._target_resolver = target_resolver
        self._clock = clock

    async def assemble(
        self,
        *,
        plan: InstallationPlan,
        selection: InstallationDestinationSelectionV1,
    ) -> InstallationCapabilityAssessmentV1:
        resolved = await self._target_resolver(
            "proxmox", selection.resource_id, "qemu"
        )
        current_destination = project_destination(resolved)
        evaluated_at = self._clock()
        provider_facts = adapt_proxmox_qemu_capability_facts(
            resolved,
            expected_destination_fingerprint=(
                current_destination.destination_fingerprint
            ),
            observed_at=evaluated_at,
        )
        return assess_installation_capability(
            plan=plan,
            selection=selection,
            current_destination=current_destination,
            provider_facts=provider_facts,
            evaluated_at=evaluated_at,
        )
