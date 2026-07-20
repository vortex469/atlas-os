from __future__ import annotations

from app.deploy.analysis import Diagnostic
from app.deploy.enums import RecommendationSeverity
from app.deploy.plan import DeploymentPlan
from app.deploy.risk.base import RiskRule


class HostNetworkRule(RiskRule):
    """Detect components using the host network namespace."""

    rule_id = "HOST_NETWORK"

    def evaluate(
        self,
        plan: DeploymentPlan,
    ) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []

        for component in plan.components:
            network_mode = component.metadata.get(
                "network_mode"
            )

            if network_mode != "host":
                continue

            diagnostics.append(
                Diagnostic(
                    code=self.rule_id,
                    severity=RecommendationSeverity.WARNING,
                    message=(
                        f"Component '{component.name}' uses host "
                        "networking."
                    ),
                    component_id=component.id,
                    recommendation=(
                        "Use an isolated application network and "
                        "publish only the ports that are required."
                    ),
                )
            )

        return diagnostics