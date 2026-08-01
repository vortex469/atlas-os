from __future__ import annotations

import stat
from pathlib import Path

import pytest
import yaml

from app.config import provider_secrets
from app.config.provider_secrets import (
    DEFAULT_PROVIDER_SECRET_FILE,
    ProviderSecretDocument,
    ProviderSecretStoreError,
    ProviderSecretValidationError,
    get_configured_secret_names,
    get_provider_secret_file,
    get_provider_secret_value,
    load_provider_secrets,
    remove_provider_secret,
    replace_provider_secret,
    update_provider_secrets,
)


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_default_provider_secret_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_PROVIDER_SECRET_FILE", raising=False)

    assert get_provider_secret_file() == DEFAULT_PROVIDER_SECRET_FILE


def test_provider_secret_path_environment_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_file = tmp_path / "secrets" / "provider-connections.yaml"
    monkeypatch.setenv("ATLAS_PROVIDER_SECRET_FILE", str(secret_file))

    assert get_provider_secret_file() == secret_file


def test_missing_secret_store_initializes_empty_file_with_0600_mode(tmp_path: Path) -> None:
    secret_file = tmp_path / "data" / "secrets" / "provider-connections.yaml"

    provider_secrets.ensure_provider_secret_file(secret_file)

    assert load_provider_secrets(secret_file).model_dump() == {"version": 1, "providers": {}}
    assert file_mode(secret_file) == 0o600


def test_replace_secret_persists_value_and_configured_name(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"

    replace_provider_secret("proxmox", "token_value", "secret-token", secret_file)

    assert get_configured_secret_names("proxmox", secret_file) == ["token_value"]
    assert get_provider_secret_value("proxmox", "token_value", secret_file) == "secret-token"
    assert read_yaml(secret_file)["providers"]["proxmox"]["secrets"]["token_value"] == "secret-token"


def test_existing_secret_is_retained_when_omitted(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    replace_provider_secret("proxmox", "token_value", "first", secret_file)

    update_provider_secrets("proxmox", replacements={"token_name": "atlas"}, secret_file=secret_file)

    assert get_provider_secret_value("proxmox", "token_value", secret_file) == "first"
    assert get_provider_secret_value("proxmox", "token_name", secret_file) == "atlas"


def test_empty_secret_replacement_is_rejected_and_does_not_erase(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    replace_provider_secret("proxmox", "token_value", "first", secret_file)

    with pytest.raises(ProviderSecretValidationError):
        replace_provider_secret("proxmox", "token_value", "", secret_file)

    assert get_provider_secret_value("proxmox", "token_value", secret_file) == "first"


def test_explicit_secret_removal_is_deliberate_only(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    replace_provider_secret("proxmox", "token_value", "first", secret_file)

    update_provider_secrets("proxmox", replacements={}, secret_file=secret_file)
    assert get_configured_secret_names("proxmox", secret_file) == ["token_value"]

    remove_provider_secret("proxmox", "token_value", secret_file)
    assert get_configured_secret_names("proxmox", secret_file) == []
    assert get_provider_secret_value("proxmox", "token_value", secret_file) is None


def test_unrelated_provider_secrets_are_preserved(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    replace_provider_secret("proxmox", "token_value", "first", secret_file)
    replace_provider_secret("opnsense", "api_key", "firewall", secret_file)

    replace_provider_secret("proxmox", "token_name", "atlas", secret_file)

    assert get_provider_secret_value("opnsense", "api_key", secret_file) == "firewall"
    assert sorted(get_configured_secret_names("proxmox", secret_file)) == ["token_name", "token_value"]


def test_secret_values_absent_from_repr_model_dump_and_errors(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    replace_provider_secret("proxmox", "token_value", "do-not-leak", secret_file)
    document = load_provider_secrets(secret_file)

    assert "do-not-leak" not in repr(document)
    assert "do-not-leak" not in str(document.model_dump())

    write_yaml(secret_file, "version: 2\nproviders:\n  proxmox:\n    secrets:\n      token_value: do-not-leak\n")
    with pytest.raises(ProviderSecretStoreError) as error_info:
        load_provider_secrets(secret_file)
    assert "do-not-leak" not in str(error_info.value)


def test_invalid_runtime_secret_file_blocks_loading_safely(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    write_yaml(secret_file, "version: 2\nproviders: {}\n")

    with pytest.raises(ProviderSecretStoreError):
        load_provider_secrets(secret_file)


def test_secret_update_uses_atomic_replace_and_0600_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    provider_secrets.ensure_provider_secret_file(secret_file)
    replacements: list[tuple[Path, Path]] = []
    actual_replace = provider_secrets.os.replace

    def record_replace(source: Path, target: Path) -> None:
        replacements.append((Path(source), Path(target)))
        actual_replace(source, target)

    monkeypatch.setattr(provider_secrets.os, "replace", record_replace)

    replace_provider_secret("proxmox", "token_value", "secret", secret_file)

    assert len(replacements) == 1
    source, target = replacements[0]
    assert target == secret_file
    assert source.parent == secret_file.parent
    assert not source.exists()
    assert file_mode(secret_file) == 0o600


def test_secret_update_uses_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret_file = tmp_path / "provider-connections.yaml"
    provider_secrets.ensure_provider_secret_file(secret_file)
    lock_operations: list[int] = []

    def record_lock(file_descriptor: int, operation: int) -> None:
        lock_operations.append(operation)

    monkeypatch.setattr(provider_secrets.fcntl, "flock", record_lock)

    replace_provider_secret("proxmox", "token_value", "secret", secret_file)

    assert provider_secrets.fcntl.LOCK_EX in lock_operations
    assert provider_secrets.fcntl.LOCK_UN in lock_operations


def test_secret_provider_key_abuse_is_rejected(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-connections.yaml"

    with pytest.raises(ProviderSecretValidationError):
        replace_provider_secret("../proxmox", "token", "secret", secret_file)
    with pytest.raises(ProviderSecretValidationError):
        replace_provider_secret("proxmox", "../token", "secret", secret_file)


def test_secret_document_model_masks_values() -> None:
    document = ProviderSecretDocument.model_validate(
        {
            "version": 1,
            "providers": {
                "proxmox": {
                    "secrets": {"token_value": "raw-secret"},
                },
            },
        },
    )

    assert "raw-secret" not in repr(document)
    assert "raw-secret" not in str(document.model_dump())
    assert document.providers["proxmox"].secrets["token_value"].get_secret_value() == "raw-secret"
