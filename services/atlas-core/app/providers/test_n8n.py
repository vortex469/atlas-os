import asyncio

import httpx
import pytest

from app.config.policy_models import N8nPolicy
from app.providers import loader
from app.providers.n8n import N8nProvider
from app.providers.registry import ProviderRegistry


def service(**overrides) -> dict:
    return {
        "name": "n8n",
        "host": "n8n.example.test",
        "port": 5678,
        "protocol": "https",
        "critical": False,
        **overrides,
    }


def workflow(name: str, active: bool) -> dict:
    return {
        "id": name,
        "name": name,
        "active": active,
    }


def test_n8n_health_uses_api_key_and_sanitizes_workflows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/workflows"
        assert request.headers["X-N8N-API-KEY"] == "test-key"
        assert request.url.params["limit"] == "100"
        return httpx.Response(
            200,
            json={
                "data": [
                    workflow("Daily backup", True),
                    workflow("Old import", False),
                ],
                "nextCursor": None,
            },
        )

    provider = N8nProvider(
        service(),
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        policy_getter=lambda: N8nPolicy(
            expected_active_workflows=["Daily backup"],
        ),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.details["workflow_count"] == 2
    assert health.details["active_workflow_count"] == 1
    assert health.details["inactive_workflow_count"] == 1
    assert health.details["missing_expected_workflows"] == []
    assert "test-key" not in str(health.model_dump())


def test_n8n_workflow_inventory_is_paginated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        if cursor is None:
            return httpx.Response(
                200,
                json={
                    "data": [workflow("First", True)],
                    "nextCursor": "next-page",
                },
            )
        assert cursor == "next-page"
        return httpx.Response(
            200,
            json={
                "data": [workflow("Second", False)],
                "nextCursor": None,
            },
        )

    provider = N8nProvider(
        service(),
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.details["workflow_count"] == 2
    assert health.details["active_workflows"] == ["First"]
    assert health.details["inactive_workflows"] == ["Second"]
    assert health.details["scan_truncated"] is False


def test_expected_missing_and_inactive_workflows_are_findings() -> None:
    provider = N8nProvider(
        service(),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [workflow("Disabled", False)],
                    "nextCursor": None,
                },
            ),
        ),
        policy_getter=lambda: N8nPolicy(
            expected_active_workflows=[
                "Required",
                "Disabled",
            ],
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].id == "n8n-expected-workflows-inactive"
    assert findings[0].details == {
        "missing": ["Required"],
        "inactive": ["Disabled"],
    }


def test_workflow_limit_produces_truncation_finding() -> None:
    provider = N8nProvider(
        service(max_workflows=1),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [workflow("First", True)],
                    "nextCursor": "more",
                },
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].id == "n8n-workflow-scan-truncated"
    assert findings[0].details["max_workflows"] == 1


def test_empty_n8n_finding_is_advisory() -> None:
    provider = N8nProvider(
        service(),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"data": [], "nextCursor": None},
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].id == "n8n-no-workflows"
    assert findings[0].severity == "info"
    assert findings[0].affects_health is False


def test_n8n_finding_severity_follows_policy() -> None:
    provider = N8nProvider(
        service(max_workflows=1),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [workflow("Disabled", False)],
                    "nextCursor": "more",
                },
            ),
        ),
        policy_getter=lambda: N8nPolicy(
            expected_active_workflows=["Disabled"],
            inactive_workflow_severity="critical",
            scan_truncated_severity="info",
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.severity for finding in findings] == [
        "critical",
        "info",
    ]
    assert findings[0].score_penalty == 20
    assert findings[1].affects_health is False


def test_n8n_authentication_failure_is_degraded() -> None:
    provider = N8nProvider(
        service(),
        api_key="expired",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401),
        ),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "degraded"
    assert health.http_status == 401
    assert health.message == "n8n API authentication failed."


def test_critical_n8n_connection_failure_is_critical() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    provider = N8nProvider(
        service(critical=True),
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].id == "n8n-api-offline"
    assert findings[0].severity == "critical"


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_workflows": 0},
    ],
)
def test_invalid_n8n_configuration_is_rejected(
    overrides: dict,
) -> None:
    with pytest.raises(ValueError):
        N8nProvider(service(**overrides))


def test_loader_selects_n8n_provider(monkeypatch) -> None:
    registry = ProviderRegistry()
    monkeypatch.setattr(loader, "provider_registry", registry)
    monkeypatch.setattr(
        loader,
        "load_inventory",
        lambda: {
            "services": {
                "n8n": service(),
            },
        },
    )

    loader.load_provider_registry()

    assert isinstance(registry.get("n8n"), N8nProvider)
