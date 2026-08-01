from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.config.provider_connections import get_provider_connection_values
from app.config.provider_secrets import get_provider_secret_value
from app.models.connections import (
    TestProviderConnectionRequest as ConnectionTestRequest,
)
from app.models.connections import (
    UpdateProviderConnectionRequest as ConnectionUpdateRequest,
)
from app.providers.docker import DockerProvider
from app.providers.proxmox import ProxmoxProvider
from app.providers.registry import ProviderRegistry
from app.services.atlas_contexts import LegacyAtlasContextResolver
from app.services.provider_connections import (
    ProviderConnectionService,
    ProviderConnectionServiceError,
)


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def empty_connection_file(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "provider-connections.yaml"
    write_yaml(path, "version: 1\nproviders: {}\n")
    return path


def empty_secret_file(tmp_path: Path) -> Path:
    path = tmp_path / "secrets" / "provider-connections.yaml"
    write_yaml(path, "version: 1\nproviders: {}\n")
    path.chmod(0o600)
    return path


def resolver_factory(connection_file: Path, secret_file: Path):
    return lambda conn, sec: LegacyAtlasContextResolver(
        runtime_connection_file=connection_file,
        runtime_secret_file=secret_file,
    )


def build_registry(connection_file: Path, secret_file: Path) -> ProviderRegistry:
    resolver = LegacyAtlasContextResolver(
        runtime_connection_file=connection_file,
        runtime_secret_file=secret_file,
    )
    registry = ProviderRegistry()
    registry.register(ProxmoxProvider(resolver.resolve_context("proxmox")))
    registry.register(DockerProvider(resolver.resolve_context("docker")))
    return registry


def service(tmp_path: Path) -> tuple[ProviderConnectionService, ProviderRegistry, Path, Path]:
    connection_file = empty_connection_file(tmp_path)
    secret_file = empty_secret_file(tmp_path)
    registry = build_registry(connection_file, secret_file)
    return (
        ProviderConnectionService(
            registry=registry,
            context_resolver_factory=resolver_factory(connection_file, secret_file),
            connection_file=connection_file,
            secret_file=secret_file,
        ),
        registry,
        connection_file,
        secret_file,
    )


def field(schema, key: str):
    return next(item for item in schema.fields if item.key == key)


def test_proxmox_schema_exposes_editable_fields_and_secret_states(tmp_path: Path) -> None:
    provider_service, _, _, _ = service(tmp_path)

    schema = provider_service.connection_schema("proxmox")

    assert schema.editable is True
    assert field(schema, "host").editable is True
    assert field(schema, "host").current_value == "10.10.50.10"
    assert field(schema, "port").validation == {"min": 1, "max": 65535}
    assert field(schema, "token_value").secret is True
    assert field(schema, "token_value").current_value is None
    assert field(schema, "token_value").secret_state in {"configured", "missing"}
    assert "compat-value" not in schema.model_dump_json()


def test_docker_schema_is_read_only_and_update_unsupported(tmp_path: Path) -> None:
    provider_service, _, _, _ = service(tmp_path)

    schema = provider_service.connection_schema("docker")

    assert schema.editable is False
    assert schema.metadata["update_supported"] is False
    assert field(schema, "path").editable is False


def test_unsupported_provider_is_stable(tmp_path: Path) -> None:
    provider_service, registry, _, _ = service(tmp_path)

    with pytest.raises(ProviderConnectionServiceError, match="provider is not registered"):
        asyncio.run(provider_service.test_connection("missing", ConnectionTestRequest()))

    assert registry.ids() == ("proxmox", "docker")


def test_proxmox_candidate_test_uses_values_without_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_service, registry, connection_file, secret_file = service(tmp_path)
    seen: dict[str, Any] = {}

    def fake_status(context):
        seen["host"] = context.connection.host
        seen["token"] = context.secrets["token_value"].reveal()
        return {"status": "online"}

    monkeypatch.setattr("app.providers.proxmox.get_proxmox_status", fake_status)

    result = asyncio.run(provider_service.test_connection(
        "proxmox",
        ConnectionTestRequest(
            values={"host": "candidate.invalid", "token_value": "candidate-secret"},
            confirmed=True,
        ),
    ))

    assert result.status == "success"
    assert result.latency_ms == 0.0
    assert seen == {"host": "candidate.invalid", "token": "candidate-secret"}
    assert get_provider_connection_values("proxmox", connection_file) == {}
    assert get_provider_secret_value("proxmox", "token_value", secret_file) is None
    assert registry.get("proxmox").atlas_context.connection.host == "10.10.50.10"


def test_proxmox_candidate_test_failure_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_service, registry, _, _ = service(tmp_path)

    def fake_status(context):
        raise RuntimeError("failed with super-secret-token")

    monkeypatch.setattr("app.providers.proxmox.get_proxmox_status", fake_status)

    result = asyncio.run(provider_service.test_connection(
        "proxmox",
        ConnectionTestRequest(values={"token_value": "super-secret-token"}, confirmed=True),
    ))

    assert result.status == "failure"
    assert "super-secret-token" not in result.model_dump_json()
    assert registry.get("proxmox").atlas_context.connection.host == "10.10.50.10"


def test_docker_test_reports_socket_diagnostics(tmp_path: Path) -> None:
    provider_service, _, _, _ = service(tmp_path)

    result = asyncio.run(provider_service.test_connection(
        "docker",
        ConnectionTestRequest(confirmed=True),
    ))

    assert result.provider_id == "docker"
    assert "socket_path" in result.diagnostics
    assert "warning" in result.diagnostics


def test_successful_proxmox_update_persists_re_resolves_and_replaces_only_proxmox(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_service, registry, connection_file, secret_file = service(tmp_path)
    original_proxmox = registry.get("proxmox")
    original_docker = registry.get("docker")

    monkeypatch.setattr(
        "app.providers.proxmox.get_proxmox_status",
        lambda context: {"status": "online"},
    )

    result = asyncio.run(provider_service.update_connection(
        "proxmox",
        ConnectionUpdateRequest(
            confirmed=True,
            values={
                "host": "runtime-proxmox.invalid",
                "port": 9443,
                "token_value": "new-token-value",
            },
        ),
    ))

    replacement = registry.get("proxmox")
    assert result.provider_id == "proxmox"
    assert get_provider_connection_values("proxmox", connection_file)["host"] == "runtime-proxmox.invalid"
    assert get_provider_secret_value("proxmox", "token_value", secret_file) == "new-token-value"
    assert replacement is not original_proxmox
    assert replacement.atlas_context.generation != original_proxmox.atlas_context.generation
    assert replacement.atlas_context.connection.host == "runtime-proxmox.invalid"
    assert registry.get("docker") is original_docker
    assert field(result.connection_schema, "host").current_value == "runtime-proxmox.invalid"
    assert "new-token-value" not in result.model_dump_json()


def test_invalid_candidate_persists_nothing(tmp_path: Path) -> None:
    provider_service, registry, connection_file, secret_file = service(tmp_path)
    original = registry.get("proxmox")

    with pytest.raises(ProviderConnectionServiceError, match="unsupported fields"):
        asyncio.run(provider_service.update_connection(
            "proxmox",
            ConnectionUpdateRequest(confirmed=True, values={"unknown": "value"}),
        ))

    assert get_provider_connection_values("proxmox", connection_file) == {}
    assert get_provider_secret_value("proxmox", "token_value", secret_file) is None
    assert registry.get("proxmox") is original


def test_failed_connection_test_persists_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_service, registry, connection_file, secret_file = service(tmp_path)
    original = registry.get("proxmox")
    monkeypatch.setattr(
        "app.providers.proxmox.get_proxmox_status",
        lambda context: (_ for _ in ()).throw(RuntimeError("nope")),
    )

    with pytest.raises(ProviderConnectionServiceError, match="connection test failed"):
        asyncio.run(provider_service.update_connection(
            "proxmox",
            ConnectionUpdateRequest(confirmed=True, values={"host": "bad.invalid"}),
        ))

    assert get_provider_connection_values("proxmox", connection_file) == {}
    assert get_provider_secret_value("proxmox", "token_value", secret_file) is None
    assert registry.get("proxmox") is original


def test_context_resolution_failure_restores_prior_stores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection_file = empty_connection_file(tmp_path)
    secret_file = empty_secret_file(tmp_path)
    registry = build_registry(connection_file, secret_file)
    original = registry.get("proxmox")
    calls = 0

    def failing_factory(conn, sec):
        nonlocal calls
        calls += 1
        if calls > 0:
            raise RuntimeError("/opt/atlas/data/config/provider-connections.yaml contains rollback-secret")
        return LegacyAtlasContextResolver(runtime_connection_file=connection_file, runtime_secret_file=secret_file)

    provider_service = ProviderConnectionService(
        registry=registry,
        context_resolver_factory=failing_factory,
        connection_file=connection_file,
        secret_file=secret_file,
    )
    monkeypatch.setattr("app.providers.proxmox.get_proxmox_status", lambda context: {"status": "online"})

    with pytest.raises(ProviderConnectionServiceError) as error_info:
        asyncio.run(provider_service.update_connection(
            "proxmox",
            ConnectionUpdateRequest(
                confirmed=True,
                values={"host": "new.invalid", "token_value": "rollback-secret"},
            ),
        ))

    assert "rollback-secret" not in str(error_info.value)
    assert "/opt/atlas/data" not in str(error_info.value)
    assert get_provider_connection_values("proxmox", connection_file) == {}
    assert get_provider_secret_value("proxmox", "token_value", secret_file) is None
    assert registry.get("proxmox") is original


def test_registry_replacement_failure_restores_prior_stores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_service, registry, connection_file, secret_file = service(tmp_path)
    original = registry.get("proxmox")
    real_replace = registry.replace

    def failing_replace(provider):
        if provider.metadata.id == "proxmox" and provider is not original:
            raise RuntimeError("replace failed with hidden-token")
        real_replace(provider)

    monkeypatch.setattr(registry, "replace", failing_replace)
    monkeypatch.setattr("app.providers.proxmox.get_proxmox_status", lambda context: {"status": "online"})

    with pytest.raises(ProviderConnectionServiceError) as error_info:
        asyncio.run(provider_service.update_connection(
            "proxmox",
            ConnectionUpdateRequest(
                confirmed=True,
                values={"host": "new.invalid", "token_value": "hidden-token"},
            ),
        ))

    assert "hidden-token" not in str(error_info.value)
    assert get_provider_connection_values("proxmox", connection_file) == {}
    assert get_provider_secret_value("proxmox", "token_value", secret_file) is None
    assert registry.get("proxmox") is original
