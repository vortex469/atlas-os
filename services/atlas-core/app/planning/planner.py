from __future__ import annotations

import re
from time import perf_counter

from app.deploy.enums import DeploymentRisk
from app.planning.exceptions import InvalidPlanningRequestError
from app.planning.models import (
    PlanningRequest,
    PlanningResult,
    PlanningStep,
    PlanningStepKind,
    ProposedPlan,
)


class PlanningEngine:
    """Create provider-independent proposals from deployment plans."""

    planner_id = "default"

    def plan(
        self,
        request: PlanningRequest,
    ) -> PlanningResult:
        """Create a proposed plan for a deployment."""

        started_at = perf_counter()
        deployment = request.deployment

        if not deployment.components:
            raise InvalidPlanningRequestError(
                "Deployment plan must contain at least one component."
            )

        steps: list[PlanningStep] = []
        order = 1

        if self._requires_storage_step(request):
            steps.append(
                PlanningStep(
                    id="prepare-storage",
                    order=order,
                    kind=PlanningStepKind.CREATE_STORAGE,
                    title="Prepare persistent storage",
                    description=(
                        "Create or validate persistent storage "
                        "required by the deployment."
                    ),
                    requires_confirmation=True,
                    estimated_duration_minutes=1,
                )
            )
            order += 1

        for component in deployment.components:
            steps.append(
                PlanningStep(
                    id=f"deploy-{self._normalize_id(component.id)}",
                    order=order,
                    kind=PlanningStepKind.DEPLOY_COMPONENT,
                    title=f"Deploy {component.name}",
                    description=(
                        f"Deploy application component "
                        f"'{component.name}'."
                    ),
                    component_id=component.id,
                    estimated_duration_minutes=1,
                )
            )
            order += 1

        steps.append(
            PlanningStep(
                id="validate-deployment",
                order=order,
                kind=PlanningStepKind.VALIDATE,
                title="Validate deployment",
                description=(
                    "Verify that all planned components are healthy "
                    "and reachable."
                ),
                estimated_duration_minutes=1,
            )
        )

        risk = request.risk or deployment.risk

        proposal = ProposedPlan(
            id=f"{deployment.id}-proposal",
            deployment_id=deployment.id,
            summary=(
                f"Deploy {deployment.name} with "
                f"{len(deployment.components)} component"
                f"{'' if len(deployment.components) == 1 else 's'}."
            ),
            steps=steps,
            risk=risk,
            approval_required=(
                deployment.requires_approval
                or risk != DeploymentRisk.LOW
            ),
            rollback_supported=False,
            estimated_duration_minutes=sum(
                step.estimated_duration_minutes or 0
                for step in steps
            ),
        )

        elapsed_ms = (
            perf_counter() - started_at
        ) * 1000

        return PlanningResult(
            planner=self.planner_id,
            proposal=proposal,
            elapsed_ms=elapsed_ms,
        )

    def _requires_storage_step(
        self,
        request: PlanningRequest,
    ) -> bool:
        return any(
            mount.persistent
            for component in request.deployment.components
            for mount in component.storage
        )

    def _normalize_id(
        self,
        value: str,
    ) -> str:
        normalized = re.sub(
            r"[^a-z0-9]+",
            "-",
            value.lower(),
        ).strip("-")

        return normalized or "component"