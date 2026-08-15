from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from app.actions.history import ProviderActionHistory
from app.config import policies as policy_config
from app.config.settings import (
    ProviderIntentActivation,
    ProviderIntentSettings,
)
from app.main import app
from app.provider_intents.authority import ProxmoxMonitoringIntentAuthority
from app.provider_intents.store import ProviderIntentStore
from app.providers.loader import load_provider_registry
from app.testing import ASGITestClient

client = ASGITestClient(app)


def guest_inventory() -> dict:
    return {
        "node": "vorex469",
        "running": 1,
        "stopped": 1,
        "guests": [
            {
                "vmid": 100,
                "name": "router",
                "type": "vm",
                "status": "running",
            },
            {
                "vmid": 109,
                "name": "kenny",
                "type": "lxc",
                "status": "stopped",
            },
        ],
    }


@pytest.fixture(autouse=True)
def provider_resource_test_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    import app.providers.proxmox as proxmox_provider

    policy_file = tmp_path / "policies.yaml"
    policy_file.write_text(
        """
proxmox:
  guests:
    "109":
      expected: stopped
""".lstrip(),
        encoding="utf-8",
    )
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
    load_provider_registry()
    return policy_file


def test_get_proxmox_resources_returns_generic_collection() -> None:
    response = client.get("/api/v1/providers/proxmox/resources")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "proxmox"
    assert body["provider_name"] == "Proxmox"
    assert body["summary"]["total"] == 2

    resources = {resource["resource_id"]: resource for resource in body["resources"]}
    assert resources["100"]["needs_review"] is True
    assert resources["100"]["expectation"]["value"] is None
    assert [
        option["value"]
        for option in resources["100"]["expectation"]["allowed_values"]
    ] == ["running", "stopped", "ignored"]
    assert resources["109"]["expectation"]["value"] == "stopped"


def test_post_proxmox_discovery_refresh_returns_resources() -> None:
    response = client.post("/api/v1/providers/proxmox/discovery/refresh")

    assert response.status_code == 200
    assert response.json()["provider_id"] == "proxmox"
    assert response.json()["summary"]["total"] == 2


def test_put_expectation_with_confirmation_updates_intent(
    provider_resource_test_setup: Path,
) -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/109/expectation",
        headers={"X-Request-ID": "resource-update-success"},
        json={"expectation": "ignored", "confirmed": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "proxmox"
    assert body["resource_id"] == "109"
    assert body["expectation"]["value"] == "ignored"
    assert "expected: ignored" in provider_resource_test_setup.read_text(
        encoding="utf-8",
    )


def test_put_without_confirmation_returns_409() -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/109/expectation",
        json={"expectation": "ignored", "confirmed": False},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == (
        "Resource expectation updates require confirmed=true."
    )


def test_activated_put_is_rejected_without_yaml_mutation(
    provider_resource_test_setup: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_action_history: ProviderActionHistory,
) -> None:
    import app.services.provider_resources as resource_service

    database = provider_resource_test_setup.parent / "provider_intents.db"
    store = ProviderIntentStore(database)
    authority = ProxmoxMonitoringIntentAuthority(
        ProviderIntentSettings(
            activation=ProviderIntentActivation.ACTIVATED,
            database=str(database),
            expected_legacy_import_id=(
                "provider-intent-legacy-policy-import-v1:" + "a" * 64
            ),
        ),
        store,
    )

    monkeypatch.setattr(
        resource_service,
        "get_monitoring_intent_authority",
        lambda: authority,
    )
    before = provider_resource_test_setup.read_bytes()
    with sqlite3.connect(database) as connection:
        store_counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "provider_intent_records",
                "provider_intent_audit",
                "provider_intent_requests",
            )
        )

    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/109/expectation",
        json={"expectation": "ignored", "confirmed": True},
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "Provider Intent mutation is unavailable until P3."
    )
    assert provider_resource_test_setup.read_bytes() == before
    assert isolated_action_history.list(limit=10) == []
    with sqlite3.connect(database) as connection:
        assert store_counts == tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "provider_intent_records",
                "provider_intent_audit",
                "provider_intent_requests",
            )
        )


def test_invalid_expectation_returns_422() -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/109/expectation",
        json={"expectation": "paused", "confirmed": True},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Invalid provider resource expectation."


def test_unknown_provider_returns_404() -> None:
    response = client.get("/api/v1/providers/not-real/resources")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Unknown provider 'not-real'."


def test_provider_without_resources_returns_stable_501() -> None:
    response = client.get("/api/v1/providers/hermes/resources")

    assert response.status_code == 501
    body = response.json()
    assert body["error"]["status"] == 501
    assert body["error"]["message"] == (
        "Provider 'hermes' does not support resources."
    )


def test_provider_discovery_failure_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.providers.proxmox as proxmox_provider

    def fail_discovery() -> dict:
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(
        proxmox_provider,
        "get_proxmox_guests",
        fail_discovery,
    )

    response = client.post("/api/v1/providers/proxmox/discovery/refresh")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "Provider 'proxmox' discovery refresh failed."
    )


def test_policy_write_failure_returns_503_and_failed_audit(
    monkeypatch: pytest.MonkeyPatch,
    isolated_action_history: ProviderActionHistory,
) -> None:
    import app.providers.proxmox as proxmox_provider

    def fail_write(resource_id: str, expectation: str) -> str:
        raise OSError("disk path /secret/policies.yaml failed")

    monkeypatch.setattr(
        proxmox_provider,
        "update_proxmox_guest_expectation",
        fail_write,
    )

    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/109/expectation",
        json={"expectation": "ignored", "confirmed": True},
    )

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "Provider resource expectation update failed."
    )
    assert "/secret" not in response.text

    entries = isolated_action_history.list(limit=10)
    assert len(entries) == 1
    assert entries[0].action_id == "update-resource-expectation"
    assert entries[0].status == "failed"
    assert "/secret" not in entries[0].message


def test_successful_update_creates_audit_entry(
    isolated_action_history: ProviderActionHistory,
) -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/109/expectation",
        headers={"X-Request-ID": "resource-audit-success"},
        json={"expectation": "ignored", "confirmed": True},
    )

    assert response.status_code == 200
    entries = isolated_action_history.list(limit=10)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.provider_id == "proxmox"
    assert entry.action_id == "update-resource-expectation"
    assert entry.status == "succeeded"
    assert entry.confirmed is True
    assert entry.request_id == "resource-audit-success"
    assert entry.parameter_names == [
        "confirmed",
        "expectation",
        "resource_id",
    ]


def test_resource_id_with_provider_native_characters_is_handled(
    provider_resource_test_setup: Path,
) -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/resources/node-1%3A109/expectation",
        json={"expectation": "stopped", "confirmed": True},
    )

    assert response.status_code == 200
    assert response.json()["resource_id"] == "node-1:109"
    policy = yaml.safe_load(
        provider_resource_test_setup.read_text(encoding="utf-8")
    )
    assert policy["proxmox"]["guests"]["node-1:109"] == {
        "expected": "stopped"
    }


def test_provider_resource_routes_are_in_openapi() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/providers/{provider_id}/resources" in paths
    assert "/api/v1/providers/{provider_id}/discovery/refresh" in paths
    assert (
        "/api/v1/providers/{provider_id}/resources/{resource_id}/expectation"
        in paths
    )
