import pytest
from pydantic import ValidationError

from app.deploy import (
    ApplicationComponent,
    DeploymentPlan,
    DeploymentSource,
    ExecutionStep,
    PortBinding,
    ResourceEstimate,
)


def test_component_ids_must_be_unique() -> None:
    with pytest.raises(
        ValidationError,
        match="component IDs must be unique",
    ):
        DeploymentPlan(
            id="duplicate-components",
            name="Duplicate Components",
            source=DeploymentSource.COMPOSE,
            components=[
                ApplicationComponent(
                    id="web",
                    name="Web One",
                ),
                ApplicationComponent(
                    id="web",
                    name="Web Two",
                ),
            ],
        )


def test_execution_step_ids_must_be_unique() -> None:
    with pytest.raises(
        ValidationError,
        match="execution step IDs must be unique",
    ):
        DeploymentPlan(
            id="duplicate-steps",
            name="Duplicate Steps",
            source=DeploymentSource.RECIPE,
            execution_steps=[
                ExecutionStep(
                    id="deploy",
                    order=1,
                    title="Deploy One",
                    provider_id="docker",
                    action_id="deploy-compose",
                ),
                ExecutionStep(
                    id="deploy",
                    order=2,
                    title="Deploy Two",
                    provider_id="docker",
                    action_id="deploy-compose",
                ),
            ],
        )


def test_execution_step_order_must_be_unique() -> None:
    with pytest.raises(
        ValidationError,
        match="execution step order values must be unique",
    ):
        DeploymentPlan(
            id="duplicate-order",
            name="Duplicate Order",
            source=DeploymentSource.RECIPE,
            execution_steps=[
                ExecutionStep(
                    id="create-vm",
                    order=1,
                    title="Create VM",
                    provider_id="proxmox",
                    action_id="create-vm",
                ),
                ExecutionStep(
                    id="deploy",
                    order=1,
                    title="Deploy",
                    provider_id="docker",
                    action_id="deploy-compose",
                ),
            ],
        )


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PortBinding(
            container_port=70000,
        )


def test_invalid_protocol_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="protocol must be either",
    ):
        PortBinding(
            container_port=8080,
            protocol="sctp",
        )


def test_negative_resource_estimate_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ResourceEstimate(
            memory_gb=-1,
        )
