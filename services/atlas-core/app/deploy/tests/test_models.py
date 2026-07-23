from app.deploy import (
    ApplicationComponent,
    ComponentKind,
    DeploymentPlan,
    DeploymentRisk,
    DeploymentSource,
    DeploymentWarning,
    ExecutionStep,
    PortBinding,
    RecommendationSeverity,
    ResourceEstimate,
    StorageMount,
)


def test_create_minimal_deployment_plan() -> None:
    plan = DeploymentPlan(
        id="immich",
        name="Immich",
        source=DeploymentSource.COMPOSE,
    )

    assert plan.id == "immich"
    assert plan.name == "Immich"
    assert plan.risk == DeploymentRisk.LOW
    assert plan.components == []
    assert plan.execution_steps == []
    assert plan.requires_approval is True
    assert plan.executable is True


def test_create_complete_component() -> None:
    component = ApplicationComponent(
        id="immich-server",
        name="Immich Server",
        kind=ComponentKind.SERVICE,
        image="ghcr.io/immich-app/immich-server:release",
        ports=[
            PortBinding(
                container_port=2283,
                host_port=2283,
                public=True,
            ),
        ],
        storage=[
            StorageMount(
                source="/srv/immich",
                target="/usr/src/app/upload",
            ),
        ],
        environment={
            "DB_HOSTNAME": "database",
        },
        dependencies=[
            "database",
            "redis",
        ],
    )

    assert component.id == "immich-server"
    assert component.ports[0].host_port == 2283
    assert component.storage[0].persistent is True
    assert component.dependencies == [
        "database",
        "redis",
    ]


def test_resource_estimate_defaults() -> None:
    resources = ResourceEstimate()

    assert resources.cpu_cores is None
    assert resources.memory_gb is None
    assert resources.storage_gb is None
    assert resources.gpu_required is False


def test_blocking_warning_makes_plan_non_executable() -> None:
    plan = DeploymentPlan(
        id="unsafe-app",
        name="Unsafe App",
        source=DeploymentSource.COMPOSE,
        warnings=[
            DeploymentWarning(
                id="root-mount",
                severity=RecommendationSeverity.CRITICAL,
                title="Root filesystem mount",
                message="The application mounts the host root filesystem.",
                blocking=True,
            ),
        ],
    )

    assert len(plan.blocking_warnings) == 1
    assert plan.executable is False


def test_execution_steps_preserve_order() -> None:
    plan = DeploymentPlan(
        id="example",
        name="Example",
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
                id="deploy-compose",
                order=2,
                title="Deploy application",
                provider_id="docker",
                action_id="deploy-compose",
            ),
        ],
    )

    assert [
        step.order
        for step in plan.execution_steps
    ] == [1, 2]
