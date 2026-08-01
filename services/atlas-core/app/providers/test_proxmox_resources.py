from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.config import policies as policy_config
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
