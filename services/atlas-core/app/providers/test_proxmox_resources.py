from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.config import policies as policy_config
from app.context import (
    AtlasContext,
    ConnectionContext,
    MetadataContext,
    RuntimeContext,
    SecretContext,
)
from app.providers.capabilities import ProviderCapability
from app.providers.proxmox import ProxmoxProvider
from app.providers.resources import ProviderExpectationAdapter, ProviderResourceAdapter


def service() -> dict:
    return {
        "name": "Proxmox",
        "description": "Proxmox VE",
        "critical": True,
    }


def guest_inventory() -> dict:
    return {
        "node": "vorex469",
        "running": 1,
        "stopped": 2,
        "guests": [
            {
                "vmid": 100,
                "name": "router",
                "type": "vm",
                "status": "running",
                "cpu_percent": 1.5,
                "memory_used_gib": 2.0,
                "memory_total_gib": 4.0,
                "uptime_seconds": 3600,
            },
            {
                "vmid": 109,
                "name": "kenny",
                "type": "lxc",
                "status": "stopped",
                "cpu_percent": 0.0,
                "memory_used_gib": 0.0,
                "memory_total_gib": 1.0,
                "uptime_seconds": 0,
            },
            {
                "vmid": 110,
                "name": "batch",
                "type": "vm",
                "status": "stopped",
            },
        ],
    }


def configure_provider_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    policy_text: str = "proxmox:\n  guests: {}\n",
) -> Path:
    import app.providers.proxmox as proxmox_provider

    policy_file = tmp_path / "policies.yaml"
    policy_file.write_text(policy_text, encoding="utf-8")
    monkeypatch.setattr(policy_config, "POLICY_FILE", policy_file)
    monkeypatch.setattr(
        proxmox_provider,
        "get_proxmox_guests",
        guest_inventory,
    )
    monkeypatch.setattr(
        proxmox_provider,
        "get_proxmox_status",
        lambda: {"status": "online", "node": "vorex469"},
    )
    return policy_file


def resources_by_id(provider: ProxmoxProvider) -> dict[str, object]:
    collection = asyncio.run(provider.list_resources())
    return {resource.resource_id: resource for resource in collection.resources}


def test_live_proxmox_guest_maps_to_generic_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_provider_test(monkeypatch, tmp_path)

    resources = resources_by_id(ProxmoxProvider(service()))
    resource = resources["100"]

    assert resource.provider_id == "proxmox"
    assert resource.resource_id == "100"
    assert resource.display_name == "router"
    assert resource.resource_type == "vm"
    assert resource.current_state == "running"


def test_vmid_and_node_remain_stable_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_provider_test(monkeypatch, tmp_path)

    resource = resources_by_id(ProxmoxProvider(service()))["109"]

    assert resource.resource_id == "109"
    assert resource.metadata["vmid"] == 109
    assert resource.metadata["node"] == "vorex469"


def test_unconfigured_guest_is_needs_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_provider_test(monkeypatch, tmp_path)

    resource = resources_by_id(ProxmoxProvider(service()))["109"]

    assert resource.configured is False
    assert resource.needs_review is True
    assert resource.expectation.value is None
    assert resource.expectation.state == "needs_review"


def test_configured_running_and_stopped_expectations_are_represented(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_provider_test(
        monkeypatch,
        tmp_path,
        """
proxmox:
  guests:
    "100":
      expected: running
    "109":
      expected: stopped
""".lstrip(),
    )

    resources = resources_by_id(ProxmoxProvider(service()))

    assert resources["100"].configured is True
    assert resources["100"].expectation.value == "running"
    assert resources["100"].expectation.label == "Expected Running"
    assert resources["109"].configured is True
    assert resources["109"].expectation.value == "stopped"
    assert resources["109"].expectation.label == "Expected Stopped"


def test_ignored_expectation_is_represented(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_provider_test(
        monkeypatch,
        tmp_path,
        """
proxmox:
  guests:
    "109":
      expected: ignored
""".lstrip(),
    )

    resource = resources_by_id(ProxmoxProvider(service()))["109"]

    assert resource.configured is True
    assert resource.needs_review is False
    assert resource.expectation.value == "ignored"
    assert resource.expectation.state == "ignored"
    assert resource.expectation.label == "Ignore"


def test_invalid_expectation_is_rejected() -> None:
    provider = ProxmoxProvider(service())

    with pytest.raises(ValueError):
        provider.normalize_expectation("vm", "paused")


def test_configured_missing_guest_appears_as_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_provider_test(
        monkeypatch,
        tmp_path,
        """
proxmox:
  guests:
    "999":
      expected: stopped
""".lstrip(),
    )

    resource = resources_by_id(ProxmoxProvider(service()))["999"]

    assert resource.missing is True
    assert resource.current_state == "missing"
    assert resource.resource_type == "unknown"
    assert resource.metadata["vmid"] == 999
    assert resource.expectation.value == "stopped"


def test_provider_advertises_expected_capabilities() -> None:
    provider = ProxmoxProvider(service())

    assert {
        ProviderCapability.HEALTH,
        ProviderCapability.DISCOVERY,
        ProviderCapability.RESOURCES,
        ProviderCapability.MONITORING,
        ProviderCapability.DIAGNOSTICS,
        ProviderCapability.ACTIONS,
    }.issubset(provider.metadata.capabilities)


def test_provider_satisfies_optional_resource_protocols() -> None:
    provider = ProxmoxProvider(service())

    assert isinstance(provider, ProviderExpectationAdapter)
    assert isinstance(provider, ProviderResourceAdapter)


def test_provider_advertises_expectation_options() -> None:
    provider = ProxmoxProvider(service())

    options = provider.expectation_options("vm")

    assert [option.value for option in options] == [
        "running",
        "stopped",
        "ignored",
    ]


def test_update_resource_expectation_persists_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = configure_provider_test(monkeypatch, tmp_path)

    result = asyncio.run(
        ProxmoxProvider(service()).update_resource_expectation("109", "ignored")
    )

    assert result.resource_id == "109"
    assert result.expectation.value == "ignored"
    assert "expected: ignored" in policy_file.read_text(encoding="utf-8")


class RecordingIntentService:
    def __init__(self, expectations: dict[str, str] | None = None) -> None:
        self.expectations = expectations or {}
        self.updated: list[tuple[str, str]] = []

    def list_guest_expectations(self) -> dict[str, str]:
        return dict(self.expectations)

    def update_guest_expectation(
        self,
        resource_id: str,
        expectation: str,
    ) -> str:
        self.updated.append((resource_id, expectation))
        self.expectations[resource_id] = expectation
        return expectation


def proxmox_context(
    *,
    host: str = "context-proxmox.local",
    port: int = 8006,
    node: str = "context-node",
    verify_tls: bool = False,
    token_value: str | None = "context-token-value",
    intent_service: RecordingIntentService | None = None,
    name: str = "Context Proxmox",
) -> AtlasContext:
    secrets = {
        "user": SecretContext(
            name="user",
            source="environment",
            configured=True,
            redacted="********",
            value="context-user",
        ),
        "token_name": SecretContext(
            name="token_name",
            source="environment",
            configured=True,
            redacted="********",
            value="context-token-name",
        ),
    }
    if token_value is not None:
        secrets["token_value"] = SecretContext(
            name="token_value",
            source="environment",
            configured=True,
            redacted="********",
            value=token_value,
        )
    else:
        secrets["token_value"] = SecretContext(
            name="token_value",
            source="missing",
            configured=False,
        )

    return AtlasContext(
        metadata=MetadataContext(
            consumer_id="proxmox",
            consumer_type="provider",
            name=name,
            description="Context description.",
            workspace="operations",
            priority="critical",
            icon="server",
            capabilities=frozenset(
                {
                    "health",
                    "discovery",
                    "resources",
                    "monitoring",
                    "diagnostics",
                    "actions",
                }
            ),
        ),
        connection=ConnectionContext(
            mode="https",
            host=host,
            port=port,
            node=node,
            verify_tls=verify_tls,
            source="settings",
        ),
        secrets=secrets,
        runtime=RuntimeContext(
            intent_reader=intent_service,
            intent_writer=intent_service,
        ),
        generation=f"test-{host}-{port}-{node}",
    )


def test_proxmox_client_uses_connection_and_secrets_from_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.clients import proxmox_client

    captured: dict[str, object] = {}

    class FakeProxmoxAPI:
        def __init__(self, host: str, **kwargs: object) -> None:
            captured["host"] = host
            captured.update(kwargs)

    monkeypatch.setattr(proxmox_client, "ProxmoxAPI", FakeProxmoxAPI)

    proxmox_client.get_proxmox_client(
        proxmox_context(
            host="ctx-a.local",
            port=9443,
            node="node-a",
            verify_tls=True,
        )
    )

    assert captured == {
        "host": "ctx-a.local",
        "user": "context-user",
        "token_name": "context-token-name",
        "token_value": "context-token-value",
        "port": 9443,
        "verify_ssl": True,
    }


def test_changing_context_changes_proxmox_client_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.clients import proxmox_client

    hosts: list[str] = []

    class FakeProxmoxAPI:
        def __init__(self, host: str, **kwargs: object) -> None:
            hosts.append(host)

    monkeypatch.setattr(proxmox_client, "ProxmoxAPI", FakeProxmoxAPI)

    proxmox_client.get_proxmox_client(proxmox_context(host="first.local"))
    proxmox_client.get_proxmox_client(proxmox_context(host="second.local"))

    assert hosts == ["first.local", "second.local"]


def test_missing_proxmox_secret_degrades_health_without_exposing_value() -> None:
    provider = ProxmoxProvider(proxmox_context(token_value=None))

    health = asyncio.run(provider.get_health())

    assert health.status == "offline"
    assert "token_value" in health.details["error"]
    assert "context-token" not in repr(health.model_dump())


def test_provider_metadata_comes_from_context_and_is_context_aware() -> None:
    provider = ProxmoxProvider(proxmox_context(name="Context Named Proxmox"))

    assert provider.metadata.name == "Context Named Proxmox"
    assert provider.metadata.description == "Context description."
    assert provider.atlas_context.consumer_id == "proxmox"
    assert {
        ProviderCapability.HEALTH,
        ProviderCapability.DISCOVERY,
        ProviderCapability.RESOURCES,
        ProviderCapability.MONITORING,
        ProviderCapability.DIAGNOSTICS,
        ProviderCapability.ACTIONS,
    }.issubset(provider.metadata.capabilities)


def test_resource_listing_reads_expectations_through_context_runtime_intent_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.providers.proxmox as proxmox_provider

    intent_service = RecordingIntentService({"109": "stopped"})
    monkeypatch.setattr(proxmox_provider, "get_proxmox_guests", guest_inventory)

    resources = resources_by_id(
        ProxmoxProvider(proxmox_context(intent_service=intent_service))
    )

    assert resources["109"].expectation.value == "stopped"
    assert resources["109"].configured is True
    assert resources["100"].needs_review is True


def test_expectation_update_uses_context_runtime_intent_writer() -> None:
    intent_service = RecordingIntentService()
    provider = ProxmoxProvider(proxmox_context(intent_service=intent_service))

    result = asyncio.run(provider.update_resource_expectation("109", "ignored"))

    assert result.expectation.value == "ignored"
    assert intent_service.updated == [("109", "ignored")]
