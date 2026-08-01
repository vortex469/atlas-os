from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.actions.history import ProviderActionHistory
from app.main import app
from app.providers import Provider, ProviderHealth, ProviderMetadata, ProviderWorkspace
from app.providers.docker import DockerProvider
from app.providers.proxmox import ProxmoxProvider
from app.providers.registry import ProviderRegistry
from app.routes import provider_connections as route_module
from app.services.atlas_contexts import LegacyAtlasContextResolver
from app.services.provider_connections import ProviderConnectionService
from app.testing import ASGITestClient

client = ASGITestClient(app)


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class UnsupportedProvider(Provider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            id="unsupported",
            name="Unsupported",
            workspace=ProviderWorkspace.OPERATIONS,
        )

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(status="unknown", message="unsupported")


def empty_connection_file(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "provider-connections.yaml"
    write_yaml(path, "version: 1\nproviders: {}\n")
    return path


def empty_secret_file(tmp_path: Path) -> Path:
    path = tmp_path / "secrets" / "provider-connections.yaml"
    write_yaml(path, "version: 1\nproviders: {}\n")
    path.chmod(0o600)
    return path


@pytest.fixture(autouse=True)
def provider_connection_route_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[ProviderConnectionService, ProviderRegistry, Path, Path]:
    import app.providers.proxmox as proxmox_provider

    connection_file = empty_connection_file(tmp_path)
    secret_file = empty_secret_file(tmp_path)
    resolver = LegacyAtlasContextResolver(
        runtime_connection_file=connection_file,
        runtime_secret_file=secret_file,
    )
    registry = ProviderRegistry()
    registry.register(ProxmoxProvider(resolver.resolve_context("proxmox")))
    registry.register(DockerProvider(resolver.resolve_context("docker")))
    registry.register(UnsupportedProvider())

    service = ProviderConnectionService(
        registry=registry,
        context_resolver_factory=lambda conn, sec: LegacyAtlasContextResolver(
            runtime_connection_file=connection_file,
            runtime_secret_file=secret_file,
        ),
        connection_file=connection_file,
        secret_file=secret_file,
    )

    monkeypatch.setattr(route_module, "ProviderConnectionService", lambda: service)
    monkeypatch.setattr(
        proxmox_provider,
        "get_proxmox_status",
        lambda context: {"status": "online", "node": "vorex469"},
    )
    return service, registry, connection_file, secret_file


def fields_by_key(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field["key"]: field for field in schema["fields"]}


def test_get_proxmox_connection_schema_returns_secret_safe_fields() -> None:
    response = client.get("/api/v1/providers/proxmox/connection")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "proxmox"
    fields = fields_by_key(body)
    assert fields["host"]["current_value"] == "10.10.50.10"
    assert fields["token_value"]["current_value"] is None
    assert fields["token_value"]["secret_state"] in {"configured", "missing"}
    assert "compat-value" not in response.text


def test_get_docker_connection_schema_is_read_only() -> None:
    response = client.get("/api/v1/providers/docker/connection")

    assert response.status_code == 200
    body = response.json()
    assert body["editable"] is False
    assert body["metadata"]["update_supported"] is False
    assert fields_by_key(body)["path"]["editable"] is False


def test_get_unknown_provider_returns_404() -> None:
    response = client.get("/api/v1/providers/missing/connection")

    assert response.status_code == 404


def test_get_unsupported_provider_returns_501() -> None:
    response = client.get("/api/v1/providers/unsupported/connection")

    assert response.status_code == 501


def test_post_test_valid_proxmox_candidate_returns_success_and_persists_nothing(
    provider_connection_route_setup: tuple[ProviderConnectionService, ProviderRegistry, Path, Path],
) -> None:
    _, registry, connection_file, secret_file = provider_connection_route_setup
    original = registry.get("proxmox")

    response = client.post(
        "/api/v1/providers/proxmox/connection/test",
        json={
            "confirmed": True,
            "values": {"host": "candidate.invalid", "token_value": "candidate-secret"},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "candidate-secret" not in response.text
    assert "candidate.invalid" not in connection_file.read_text(encoding="utf-8")
    assert "candidate-secret" not in secret_file.read_text(encoding="utf-8")
    assert registry.get("proxmox") is original


def test_post_test_failed_candidate_returns_sanitized_result_and_failed_audit(
    monkeypatch: pytest.MonkeyPatch,
    isolated_action_history: ProviderActionHistory,
) -> None:
    import app.providers.proxmox as proxmox_provider

    monkeypatch.setattr(
        proxmox_provider,
        "get_proxmox_status",
        lambda context: (_ for _ in ()).throw(RuntimeError("bad candidate-secret")),
    )

    response = client.post(
        "/api/v1/providers/proxmox/connection/test",
        headers={"X-Request-ID": "connection-test-fail"},
        json={"confirmed": True, "values": {"token_value": "candidate-secret"}},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failure"
    assert "candidate-secret" not in response.text
    entries = isolated_action_history.list(limit=10)
    assert entries[0].action_id == "test-provider-connection"
    assert entries[0].status == "failed"
    assert entries[0].request_id == "connection-test-fail"
    assert "secret:token_value" in entries[0].parameter_names
    assert "candidate-secret" not in entries[0].message


def test_post_test_missing_confirmation_returns_409() -> None:
    response = client.post(
        "/api/v1/providers/proxmox/connection/test",
        json={"confirmed": False, "values": {"host": "candidate.invalid"}},
    )

    assert response.status_code == 409


def test_post_test_success_creates_audit_without_values(
    isolated_action_history: ProviderActionHistory,
) -> None:
    response = client.post(
        "/api/v1/providers/proxmox/connection/test",
        headers={"X-Request-ID": "connection-test-success"},
        json={"confirmed": True, "values": {"host": "candidate.invalid"}},
    )

    assert response.status_code == 200
    entries = isolated_action_history.list(limit=10)
    assert entries[0].action_id == "test-provider-connection"
    assert entries[0].status == "succeeded"
    assert entries[0].request_id == "connection-test-success"
    assert entries[0].parameter_names == ["confirmed", "field:host"]
    assert "candidate.invalid" not in entries[0].message


def test_put_confirmed_proxmox_update_replaces_provider_and_reflects_saved_values(
    provider_connection_route_setup: tuple[ProviderConnectionService, ProviderRegistry, Path, Path],
    isolated_action_history: ProviderActionHistory,
) -> None:
    _, registry, _, _ = provider_connection_route_setup
    original = registry.get("proxmox")

    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/connection",
        headers={"X-Request-ID": "connection-update-success"},
        json={
            "confirmed": True,
            "values": {"host": "runtime-proxmox.invalid", "token_value": "new-secret"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider_id"] == "proxmox"
    assert fields_by_key(body["connection_schema"])["host"]["current_value"] == "runtime-proxmox.invalid"
    replacement = registry.get("proxmox")
    assert replacement is not original
    assert replacement.atlas_context.generation != original.atlas_context.generation
    assert "new-secret" not in response.text
    entries = isolated_action_history.list(limit=10)
    assert entries[0].action_id == "update-provider-connection"
    assert entries[0].status == "succeeded"
    assert entries[0].request_id == "connection-update-success"
    assert "secret:token_value" in entries[0].parameter_names


def test_put_omitted_secret_retains_old_value(
    provider_connection_route_setup: tuple[ProviderConnectionService, ProviderRegistry, Path, Path],
) -> None:
    _, _, _, secret_file = provider_connection_route_setup
    secret_file.write_text(
        "version: 1\nproviders:\n  proxmox:\n    secrets:\n      token_value: old-secret\n",
        encoding="utf-8",
    )

    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/connection",
        json={"confirmed": True, "values": {"host": "runtime-proxmox.invalid"}},
    )

    assert response.status_code == 200
    assert "old-secret" in secret_file.read_text(encoding="utf-8")


def test_put_empty_secret_replacement_returns_422() -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/connection",
        json={"confirmed": True, "values": {"token_value": ""}},
    )

    assert response.status_code == 422


def test_put_missing_confirmation_returns_409() -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/connection",
        json={"confirmed": False, "values": {"host": "runtime-proxmox.invalid"}},
    )

    assert response.status_code == 409


def test_put_docker_update_is_rejected_as_read_only() -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/docker/connection",
        json={"confirmed": True, "values": {"path": "/var/run/docker.sock"}},
    )

    assert response.status_code == 409


def test_put_unsupported_provider_returns_501() -> None:
    response = client.request(
        "PUT",
        "/api/v1/providers/unsupported/connection",
        json={"confirmed": True, "values": {"host": "example.invalid"}},
    )

    assert response.status_code == 501


def test_put_operation_failure_returns_503_and_failed_audit(
    monkeypatch: pytest.MonkeyPatch,
    isolated_action_history: ProviderActionHistory,
) -> None:
    import app.providers.proxmox as proxmox_provider

    monkeypatch.setattr(
        proxmox_provider,
        "get_proxmox_status",
        lambda context: (_ for _ in ()).throw(RuntimeError("bad hidden-secret")),
    )

    response = client.request(
        "PUT",
        "/api/v1/providers/proxmox/connection",
        headers={"X-Request-ID": "connection-update-fail"},
        json={"confirmed": True, "values": {"token_value": "hidden-secret"}},
    )

    assert response.status_code == 503
    assert "hidden-secret" not in response.text
    entries = isolated_action_history.list(limit=10)
    assert entries[0].action_id == "update-provider-connection"
    assert entries[0].status == "failed"
    assert entries[0].request_id == "connection-update-fail"
    assert "hidden-secret" not in entries[0].message


def test_provider_connection_routes_are_in_openapi() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/providers/{provider_id}/connection" in paths
    assert "/api/v1/providers/{provider_id}/connection/test" in paths


def test_existing_resource_route_remains_available() -> None:
    response = client.get("/openapi.json")

    assert "/api/v1/providers/{provider_id}/resources" in response.json()["paths"]
