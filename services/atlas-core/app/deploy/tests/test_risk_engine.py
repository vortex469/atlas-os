import pytest

from app.deploy import (
    ApplicationComponent,
    DeploymentPlan,
    DeploymentSource,
    StorageMount,
)
from app.deploy.risk import (
    DockerSocketMountRule,
    HostNetworkRule,
    PrivilegedContainerRule,
    RiskEngine,
)


def create_plan(
    component: ApplicationComponent,
) -> DeploymentPlan:
    return DeploymentPlan(
        id="risk-test",
        name="Risk Test",
        source=DeploymentSource.COMPOSE,
        components=[component],
    )


def test_register_risk_rule() -> None:
    engine = RiskEngine()

    engine.register(PrivilegedContainerRule())

    assert engine.registered() == [
        "PRIVILEGED_CONTAINER",
    ]


def test_duplicate_rule_registration_fails() -> None:
    engine = RiskEngine(
        rules=[PrivilegedContainerRule()]
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        engine.register(PrivilegedContainerRule())


def test_unknown_rule_raises() -> None:
    engine = RiskEngine()

    with pytest.raises(
        KeyError,
        match="No risk rule registered",
    ):
        engine.get("UNKNOWN_RULE")


def test_privileged_container_is_detected() -> None:
    plan = create_plan(
        ApplicationComponent(
            id="web",
            name="Web",
            metadata={
                "privileged": True,
            },
        )
    )

    diagnostics = RiskEngine(
        rules=[PrivilegedContainerRule()]
    ).evaluate(plan)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "PRIVILEGED_CONTAINER"
    assert diagnostics[0].component_id == "web"


def test_non_privileged_container_is_ignored() -> None:
    plan = create_plan(
        ApplicationComponent(
            id="web",
            name="Web",
            metadata={
                "privileged": False,
            },
        )
    )

    diagnostics = RiskEngine(
        rules=[PrivilegedContainerRule()]
    ).evaluate(plan)

    assert diagnostics == []


def test_docker_socket_mount_is_detected() -> None:
    plan = create_plan(
        ApplicationComponent(
            id="manager",
            name="Manager",
            storage=[
                StorageMount(
                    source="/var/run/docker.sock",
                    target="/var/run/docker.sock",
                ),
            ],
        )
    )

    diagnostics = RiskEngine(
        rules=[DockerSocketMountRule()]
    ).evaluate(plan)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "DOCKER_SOCKET_MOUNT"


def test_host_network_is_detected() -> None:
    plan = create_plan(
        ApplicationComponent(
            id="network-service",
            name="Network Service",
            metadata={
                "network_mode": "host",
            },
        )
    )

    diagnostics = RiskEngine(
        rules=[HostNetworkRule()]
    ).evaluate(plan)

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "HOST_NETWORK"


def test_engine_evaluates_multiple_rules() -> None:
    plan = create_plan(
        ApplicationComponent(
            id="unsafe-service",
            name="Unsafe Service",
            storage=[
                StorageMount(
                    source="/var/run/docker.sock",
                    target="/var/run/docker.sock",
                ),
            ],
            metadata={
                "privileged": True,
                "network_mode": "host",
            },
        )
    )

    engine = RiskEngine(
        rules=[
            PrivilegedContainerRule(),
            DockerSocketMountRule(),
            HostNetworkRule(),
        ]
    )

    diagnostics = engine.evaluate(plan)

    assert {
        diagnostic.code
        for diagnostic in diagnostics
    } == {
        "DOCKER_SOCKET_MOUNT",
        "HOST_NETWORK",
        "PRIVILEGED_CONTAINER",
    }