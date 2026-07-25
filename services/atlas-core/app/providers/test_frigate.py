import asyncio

import httpx

from app.config.policy_models import (
    FrigateCameraPolicy,
    FrigatePolicy,
)
from app.providers import loader
from app.providers.frigate import FrigateProvider
from app.providers.registry import ProviderRegistry


def service(**overrides) -> dict:
    return {
        "name": "Frigate",
        "host": "frigate.example.test",
        "port": 8971,
        "protocol": "https",
        "critical": False,
        **overrides,
    }


def stats_response() -> dict:
    return {
        "cameras": {
            "front": {
                "camera_fps": 5,
                "process_fps": 5,
                "skipped_fps": 0,
                "detection_fps": 1,
            },
        },
        "detection_fps": 1,
        "service": {
            "uptime": 3600,
            "version": "0.16.0",
            "latest_version": "0.16.1",
        },
    }


def test_frigate_health_uses_bearer_auth_and_sanitizes_stats() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/stats"
        assert request.headers["Authorization"] == (
            "Bearer test-token"
        )
        return httpx.Response(200, json=stats_response())

    provider = FrigateProvider(
        service(),
        api_token="test-token",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.http_status == 200
    assert health.details["camera_count"] == 1
    assert health.details["version"] == "0.16.0"
    assert "test-token" not in str(health.model_dump())


def test_frigate_internal_api_does_not_require_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json=stats_response())

    provider = FrigateProvider(
        service(
            protocol="http",
            port=5000,
            verify_tls=False,
        ),
        api_token="",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.details["authenticated"] is False


def test_frigate_camera_and_version_findings() -> None:
    payload = stats_response()
    payload["cameras"]["front"]["process_fps"] = 0
    provider = FrigateProvider(
        service(),
        api_token="test-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.id for finding in findings] == [
        "frigate-cameras-stalled",
        "frigate-update-available",
    ]
    assert findings[0].details["cameras"] == ["front"]
    assert "process_fps=0" in findings[0].details[
        "violations"
    ]["front"][0]
    assert findings[1].affects_health is False


def test_frigate_camera_findings_follow_policy() -> None:
    payload = stats_response()
    payload["cameras"]["front"]["camera_fps"] = 3
    provider = FrigateProvider(
        service(),
        api_token="test-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload),
        ),
        policy_getter=lambda: FrigatePolicy(
            stalled_camera_severity="critical",
            cameras={
                "front": FrigateCameraPolicy(
                    minimum_camera_fps=4,
                ),
                "missing": FrigateCameraPolicy(),
                "retired": FrigateCameraPolicy(
                    expected="inactive",
                ),
            },
        ),
    )

    findings = asyncio.run(provider.get_findings())

    camera_finding = findings[0]
    assert camera_finding.id == "frigate-cameras-stalled"
    assert camera_finding.severity == "critical"
    assert camera_finding.score_penalty == 20
    assert camera_finding.details["cameras"] == [
        "front",
        "missing",
    ]
    assert camera_finding.details["violations"]["missing"] == [
        "missing",
    ]


def test_inactive_camera_is_ignored_and_info_is_advisory() -> None:
    payload = stats_response()
    payload["cameras"]["front"]["process_fps"] = 0
    payload["cameras"]["retired"] = {
        "camera_fps": 0,
        "process_fps": 0,
    }
    provider = FrigateProvider(
        service(),
        api_token="test-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload),
        ),
        policy_getter=lambda: FrigatePolicy(
            stalled_camera_severity="info",
            cameras={
                "retired": FrigateCameraPolicy(
                    expected="inactive",
                ),
            },
        ),
    )

    findings = asyncio.run(provider.get_findings())

    camera_finding = findings[0]
    assert camera_finding.severity == "info"
    assert camera_finding.affects_health is False
    assert camera_finding.score_penalty == 0
    assert camera_finding.details["cameras"] == ["front"]


def test_frigate_authentication_failure_is_degraded() -> None:
    provider = FrigateProvider(
        service(),
        api_token="expired-token",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401),
        ),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "degraded"
    assert health.http_status == 401
    assert health.message == (
        "Frigate API authentication failed."
    )


def test_critical_frigate_connection_failure_is_critical() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    provider = FrigateProvider(
        service(critical=True),
        api_token="test-token",
        transport=httpx.MockTransport(handler),
    )

    findings = asyncio.run(provider.get_findings())

    assert len(findings) == 1
    assert findings[0].id == "frigate-api-offline"
    assert findings[0].severity == "critical"


def test_loader_selects_frigate_provider(
    monkeypatch,
) -> None:
    registry = ProviderRegistry()
    monkeypatch.setattr(loader, "provider_registry", registry)
    monkeypatch.setattr(
        loader,
        "load_inventory",
        lambda: {
            "services": {
                "frigate": service(),
            },
        },
    )

    loader.load_provider_registry()

    assert isinstance(
        registry.get("frigate"),
        FrigateProvider,
    )
