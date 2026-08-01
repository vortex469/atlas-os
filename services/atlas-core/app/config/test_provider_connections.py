from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import provider_connections
from app.config.provider_connections import (
    DEFAULT_PROVIDER_CONNECTION_FILE,
    DEFAULT_PROVIDER_CONNECTION_TEMPLATE_FILE,
    ProviderConnectionStoreError,
    ProviderConnectionValidationError,
    get_provider_connection_file,
    get_provider_connection_template_file,
    get_provider_connection_values,
    load_provider_connections,
    update_provider_connection_values,
)


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def test_default_provider_connection_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_PROVIDER_CONNECTION_FILE", raising=False)
    monkeypatch.delenv("ATLAS_PROVIDER_CONNECTION_TEMPLATE_FILE", raising=False)

    assert get_provider_connection_file() == DEFAULT_PROVIDER_CONNECTION_FILE
    assert get_provider_connection_template_file() == DEFAULT_PROVIDER_CONNECTION_TEMPLATE_FILE


def test_provider_connection_path_environment_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime.yaml"
    template = tmp_path / "template.yaml"
    monkeypatch.setenv("ATLAS_PROVIDER_CONNECTION_FILE", str(runtime))
    monkeypatch.setenv("ATLAS_PROVIDER_CONNECTION_TEMPLATE_FILE", str(template))

    assert get_provider_connection_file() == runtime
    assert get_provider_connection_template_file() == template


def test_valid_template_initializes_runtime_connection_file(tmp_path: Path) -> None:
    runtime = tmp_path / "data" / "config" / "provider-connections.yaml"
    template = tmp_path / "config" / "provider-connections.yaml"
    write_yaml(
        template,
        """
version: 1
providers:
  proxmox:
    connection:
      host: 10.10.50.10
      port: 8006
""".lstrip(),
    )

    provider_connections.ensure_provider_connection_file(runtime, template)

    assert get_provider_connection_values("proxmox", runtime) == {
        "host": "10.10.50.10",
        "port": 8006,
    }


def test_existing_runtime_connection_file_is_not_overwritten(tmp_path: Path) -> None:
    runtime = tmp_path / "data" / "config" / "provider-connections.yaml"
    template = tmp_path / "config" / "provider-connections.yaml"
    write_yaml(runtime, "version: 1\nproviders:\n  proxmox:\n    connection:\n      host: runtime\n")
    write_yaml(template, "version: 1\nproviders:\n  proxmox:\n    connection:\n      host: template\n")

    provider_connections.ensure_provider_connection_file(runtime, template)

    assert get_provider_connection_values("proxmox", runtime)["host"] == "runtime"


def test_missing_template_creates_valid_empty_connection_store(tmp_path: Path) -> None:
    runtime = tmp_path / "data" / "config" / "provider-connections.yaml"
    template = tmp_path / "missing" / "provider-connections.yaml"

    provider_connections.ensure_provider_connection_file(runtime, template)

    assert load_provider_connections(runtime).model_dump() == {"version": 1, "providers": {}}


def test_invalid_template_blocks_connection_initialization(tmp_path: Path) -> None:
    runtime = tmp_path / "data" / "config" / "provider-connections.yaml"
    template = tmp_path / "config" / "provider-connections.yaml"
    write_yaml(template, "version: 2\nproviders: {}\n")

    with pytest.raises(ProviderConnectionStoreError):
        provider_connections.ensure_provider_connection_file(runtime, template)

    assert not runtime.exists()


def test_invalid_runtime_connection_file_blocks_loading(tmp_path: Path) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(runtime, "version: 2\nproviders: {}\n")

    with pytest.raises(ProviderConnectionStoreError):
        load_provider_connections(runtime)


def test_connection_update_preserves_unrelated_providers_and_fields(tmp_path: Path) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(
        runtime,
        """
version: 1
providers:
  proxmox:
    connection:
      host: old
      port: 8006
  opnsense:
    connection:
      host: firewall.local
""".lstrip(),
    )

    result = update_provider_connection_values("proxmox", {"host": "new"}, runtime)

    assert result == {"host": "new", "port": 8006}
    data = read_yaml(runtime)
    assert data["providers"]["opnsense"]["connection"]["host"] == "firewall.local"


def test_connection_update_uses_atomic_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(runtime, "version: 1\nproviders: {}\n")
    replacements: list[tuple[Path, Path]] = []
    actual_replace = provider_connections.os.replace

    def record_replace(source: Path, target: Path) -> None:
        replacements.append((Path(source), Path(target)))
        actual_replace(source, target)

    monkeypatch.setattr(provider_connections.os, "replace", record_replace)

    update_provider_connection_values("proxmox", {"host": "10.10.50.10"}, runtime)

    assert len(replacements) == 1
    source, target = replacements[0]
    assert target == runtime
    assert source.parent == runtime.parent
    assert not source.exists()


def test_connection_update_uses_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(runtime, "version: 1\nproviders: {}\n")
    lock_operations: list[int] = []

    def record_lock(file_descriptor: int, operation: int) -> None:
        lock_operations.append(operation)

    monkeypatch.setattr(provider_connections.fcntl, "flock", record_lock)

    update_provider_connection_values("proxmox", {"host": "10.10.50.10"}, runtime)

    assert provider_connections.fcntl.LOCK_EX in lock_operations
    assert provider_connections.fcntl.LOCK_UN in lock_operations


def test_connection_update_is_immediately_visible(tmp_path: Path) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(runtime, "version: 1\nproviders: {}\n")

    update_provider_connection_values("new-provider", {"url": "http://example.local"}, runtime)

    assert load_provider_connections(runtime).providers["new-provider"].connection == {
        "url": "http://example.local",
    }


def test_unknown_provider_can_be_added_safely(tmp_path: Path) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(runtime, "version: 1\nproviders: {}\n")

    assert update_provider_connection_values("custom-provider", {"enabled": True}, runtime) == {"enabled": True}


def test_provider_key_abuse_is_rejected(tmp_path: Path) -> None:
    runtime = tmp_path / "provider-connections.yaml"
    write_yaml(runtime, "version: 1\nproviders: {}\n")

    with pytest.raises(ProviderConnectionValidationError):
        update_provider_connection_values("../proxmox", {"host": "bad"}, runtime)
    with pytest.raises(ProviderConnectionValidationError):
        update_provider_connection_values("proxmox", {"../host": "bad"}, runtime)
