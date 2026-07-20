import pytest
from pydantic import ValidationError

from app.deploy import (
    ApplicationComponent,
    DeploymentPlan,
    DeploymentRisk,
    DeploymentSource,
    StorageMount,
)
from app.planning import (
    InvalidPlanningRequestError,
    PlanningEngine,
    PlanningRequest,
    PlanningStep,
    PlanningStepKind,
    ProposedPlan,
)


def create_deployment(
    *,
    persistent_storage: bool = False,
) -> DeploymentPlan:
    storage = []

    if persistent_storage:
        storage = [
            StorageMount(
                source="./data",
                target="/data",
                persistent=True,
            ),
        ]

    return DeploymentPlan(
        id="immich",
        name="Immich",
        source=DeploymentSource.COMPOSE,
        components=[
            ApplicationComponent(
                id="server",
                name="Server",
                storage=storage,
            ),
            ApplicationComponent(
                id="database",
                name="Database",
            ),
        ],
    )


def test_create_basic_proposal() -> None:
    result = PlanningEngine().plan(
        PlanningRequest(
            deployment=create_deployment(),
        )
    )

    assert result.planner == "default"
    assert result.proposal.id == "immich-proposal"
    assert result.proposal.deployment_id == "immich"
    assert len(result.proposal.steps) == 3
    assert result.proposal.steps[0].id == "deploy-server"
    assert result.proposal.steps[-1].id == (
        "validate-deployment"
    )
    assert result.proposal.estimated_duration_minutes == 3
    assert result.elapsed_ms >= 0


def test_persistent_storage_adds_preparation_step() -> None:
    result = PlanningEngine().plan(
        PlanningRequest(
            deployment=create_deployment(
                persistent_storage=True,
            ),
        )
    )

    assert result.proposal.steps[0].kind == (
        PlanningStepKind.CREATE_STORAGE
    )
    assert result.proposal.steps[0].requires_confirmation is True
    assert len(result.proposal.steps) == 4


def test_explicit_risk_is_used() -> None:
    result = PlanningEngine().plan(
        PlanningRequest(
            deployment=create_deployment(),
            risk=DeploymentRisk.HIGH,
        )
    )

    assert result.proposal.risk == DeploymentRisk.HIGH
    assert result.proposal.approval_required is True


def test_empty_deployment_is_rejected() -> None:
    deployment = DeploymentPlan(
        id="empty",
        name="Empty",
        source=DeploymentSource.COMPOSE,
    )

    with pytest.raises(
        InvalidPlanningRequestError,
        match="at least one component",
    ):
        PlanningEngine().plan(
            PlanningRequest(
                deployment=deployment,
            )
        )


def test_duplicate_planning_step_ids_are_rejected() -> None:
    duplicate_step = PlanningStep(
        id="deploy",
        order=1,
        kind=PlanningStepKind.DEPLOY_COMPONENT,
        title="Deploy",
    )

    with pytest.raises(
        ValidationError,
        match="planning step IDs must be unique",
    ):
        ProposedPlan(
            id="duplicate-proposal",
            deployment_id="duplicate",
            summary="Duplicate proposal",
            steps=[
                duplicate_step,
                duplicate_step.model_copy(
                    update={
                        "order": 2,
                    }
                ),
            ],
        )


def test_duplicate_planning_step_orders_are_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="planning step order values must be unique",
    ):
        ProposedPlan(
            id="duplicate-order-proposal",
            deployment_id="duplicate-order",
            summary="Duplicate order proposal",
            steps=[
                PlanningStep(
                    id="first",
                    order=1,
                    kind=PlanningStepKind.PREPARE,
                    title="First",
                ),
                PlanningStep(
                    id="second",
                    order=1,
                    kind=PlanningStepKind.VALIDATE,
                    title="Second",
                ),
            ],
        )