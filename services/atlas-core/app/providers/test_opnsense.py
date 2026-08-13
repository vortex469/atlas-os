import asyncio

import httpx

from app.config.policy_models import OPNsensePolicy
from app.providers import loader
from app.providers.opnsense import OPNsenseProvider
from app.providers.registry import ProviderRegistry


def service(**overrides) -> dict:
    return {
        "name": "OPNsense",
        "host": "firewall.example.test",
        "port": 443,
        "protocol": "https",
        "critical": True,
        **overrides,
    }


def test_opnsense_health_uses_basic_auth_and_sanitizes_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/core/firmware/status"
        assert request.headers["Authorization"].startswith("Basic ")
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "product_name": "OPNsense",
                "product_version": "26.1",
                "updates": "2",
                "upgrade_needs_reboot": "0",
            },
        )

    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.http_status == 200
    assert health.details["product_version"] == "26.1"
    assert "api-key" not in str(health.model_dump())
    assert "api-secret" not in str(health.model_dump())


def test_opnsense_status_none_ignores_stale_legacy_fields() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "none",
                    "updates": "2",
                    "upgrade_needs_reboot": "1",
                    "all_packages": {},
                    "all_sets": {},
                },
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings == []


def test_opnsense_package_update_produces_firmware_finding() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "update",
                    "all_packages": {
                        "os-test": {"name": "os-test"},
                    },
                    "all_sets": {},
                    "status_reboot": "0",
                },
            ),
        ),
        policy_getter=lambda: OPNsensePolicy(
            pending_update_warning_threshold=1,
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.id for finding in findings] == [
        "opnsense-firmware-updates",
    ]
    assert findings[0].severity == "warning"
    assert findings[0].affects_health is True
    assert findings[0].score_penalty == 5


def test_opnsense_upgrade_set_produces_firmware_finding() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "upgrade",
                    "all_packages": {},
                    "all_sets": {
                        "kernel": {"name": "kernel"},
                    },
                    "status_reboot": "0",
                },
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.id for finding in findings] == [
        "opnsense-firmware-updates",
    ]
    assert findings[0].metric == {"updates": 1}


def test_opnsense_active_status_reboot_produces_reboot_finding() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "update",
                    "all_packages": {
                        "os-test": {"name": "os-test"},
                    },
                    "all_sets": {},
                    "status_reboot": "1",
                    "upgrade_needs_reboot": "0",
                },
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.id for finding in findings] == [
        "opnsense-firmware-updates",
        "opnsense-reboot-required",
    ]
    assert findings[1].score_penalty == 5


def test_opnsense_status_none_ignores_stale_legacy_reboot() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "none",
                    "all_packages": {},
                    "all_sets": {},
                    "upgrade_needs_reboot": "1",
                },
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.id for finding in findings] == []


def test_opnsense_legacy_fallback_produces_findings() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "ok",
                    "updates": "2",
                    "upgrade_needs_reboot": "1",
                },
            ),
        ),
        policy_getter=lambda: OPNsensePolicy(
            pending_update_warning_threshold=1,
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert [finding.id for finding in findings] == [
        "opnsense-firmware-updates",
        "opnsense-reboot-required",
    ]
    assert findings[0].severity == "warning"
    assert findings[1].score_penalty == 5


def test_opnsense_firmware_severity_follows_policy() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "ok",
                    "updates": "2",
                    "upgrade_needs_reboot": "1",
                },
            ),
        ),
        policy_getter=lambda: OPNsensePolicy(
            pending_update_warning_threshold=5,
            reboot_required_severity="critical",
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].severity == "info"
    assert findings[0].affects_health is False
    assert findings[1].severity == "critical"
    assert findings[1].score_penalty == 15


def test_opnsense_health_requires_credentials() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="",
        api_secret="",
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "degraded"
    assert health.details["credentials_configured"] is False


def test_opnsense_authentication_failure_is_degraded() -> None:
    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401),
        ),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "degraded"
    assert health.http_status == 401
    assert health.message == (
        "OPNsense API authentication failed."
    )


def test_opnsense_connection_failure_is_offline() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    provider = OPNsenseProvider(
        service(),
        api_key="api-key",
        api_secret="api-secret",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "offline"
    assert health.http_status is None
    assert health.message == "OPNsense API is unavailable."


def test_loader_selects_opnsense_provider(
    monkeypatch,
) -> None:
    registry = ProviderRegistry()
    monkeypatch.setattr(loader, "provider_registry", registry)
    monkeypatch.setattr(
        loader,
        "load_inventory",
        lambda: {
            "services": {
                "opnsense": service(),
            },
        },
    )

    loader.load_provider_registry()

    assert isinstance(
        registry.get("opnsense"),
        OPNsenseProvider,
    )
