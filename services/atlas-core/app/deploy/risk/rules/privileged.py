from __future__ import annotations

from app.deploy.analysis import Diagnostic
from app.deploy.enums import RecommendationSeverity
from app.deploy.plan import DeploymentPlan
from app.deploy.risk.base import RiskRule


class PrivilegedContainerRule(RiskRule):
    """Detect components configured to run in privileged mode."""

    rule_id = "PRIVILEGED_CONTAINER"

    def evaluate(
        self,
        plan: DeploymentPlan,
    ) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []

        for component in plan.components:
            if component.metadata.get("privileged") is not True:
                continue

            diagnostics.append(
                Diagnostic(
                    code=self.rule_id,
                    severity=RecommendationSeverity.CRITICAL,
                    message=(
                        f"Component '{component.name}' runs in "
                        "privileged mode."
                    ),
                    component_id=component.id,
                    recommendation=(
                        "Disable privileged mode and grant only the "
                        "specific capabilities the application needs."
                    ),
                )
            )

        return diagnostics