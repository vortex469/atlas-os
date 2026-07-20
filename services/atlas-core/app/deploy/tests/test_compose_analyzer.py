import pytest

from app.deploy.analysis import AnalysisRequest
from app.deploy.analyzers import ComposeAnalyzer
from app.deploy.enums import DeploymentSource


def test_analyze_compose_document() -> None:
    request = AnalysisRequest(
        source=DeploymentSource.COMPOSE,
        reference="/tmp/immich-compose.yml",
        document={
            "name": "Immich",
            "services": {
                "immich-server": {
                    "image": (
                        "ghcr.io/immich-app/"
                        "immich-server:release"
                    ),
                    "ports": [
                        "2283:2283",
                    ],
                    "volumes": [
                        "./photos:/usr/src/app/upload",
                    ],
                    "environment": {
                        "DB_HOSTNAME": "database",
                    },
                    "depends_on": {
                        "database": {
                            "condition": (
                                "service_healthy"
                            ),
                        },
                    },
                },
                "database": {
                    "image": "postgres:16",
                },
            },
        },
    )

    result = ComposeAnalyzer().analyze(request)

    assert result.analyzer == "compose"
    assert result.plan.name == "Immich"
    assert result.plan.id == "immich-compose"
    assert len(result.plan.components) == 2

    server = result.plan.components[0]

    assert server.id == "immich-server"
    assert server.ports[0].host_port == 2283
    assert server.ports[0].container_port == 2283
    assert server.storage[0].source == "./photos"
    assert server.environment == {
        "DB_HOSTNAME": "database",
    }
    assert server.dependencies == ["database"]
    assert result.elapsed_ms >= 0


def test_parse_environment_list() -> None:
    request = AnalysisRequest(
        source=DeploymentSource.COMPOSE,
        document={
            "services": {
                "web": {
                    "environment": [
                        "MODE=production",
                        "OPTIONAL_VALUE",
                    ],
                },
            },
        },
    )

    result = ComposeAnalyzer().analyze(request)

    assert result.plan.components[0].environment == {
        "MODE": "production",
        "OPTIONAL_VALUE": "",
    }


def test_parse_long_form_port_and_volume() -> None:
    request = AnalysisRequest(
        source=DeploymentSource.COMPOSE,
        document={
            "services": {
                "web": {
                    "ports": [
                        {
                            "target": 8080,
                            "published": 80,
                            "host_ip": "127.0.0.1",
                            "protocol": "tcp",
                        },
                    ],
                    "volumes": [
                        {
                            "type": "tmpfs",
                            "target": "/tmp",
                            "read_only": True,
                        },
                    ],
                },
            },
        },
    )

    result = ComposeAnalyzer().analyze(request)

    component = result.plan.components[0]

    assert component.ports[0].public is False
    assert component.storage[0].persistent is False
    assert component.storage[0].read_only is True


def test_reject_non_mapping_services() -> None:
    request = AnalysisRequest(
        source=DeploymentSource.COMPOSE,
        document={
            "services": [],
        },
    )

    with pytest.raises(
        ValueError,
        match="services.*mapping",
    ):
        ComposeAnalyzer().analyze(request)


def test_reject_wrong_analysis_source() -> None:
    request = AnalysisRequest(
        source=DeploymentSource.GITHUB,
        document={
            "services": {},
        },
    )

    with pytest.raises(
        ValueError,
        match="only supports Compose",
    ):
        ComposeAnalyzer().analyze(request)