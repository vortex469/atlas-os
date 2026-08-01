from __future__ import annotations

import fcntl
import os
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator

ATLAS_ROOT = Path("/opt/atlas")
DEFAULT_PROVIDER_SECRET_FILE = ATLAS_ROOT / "data" / "secrets" / "provider-connections.yaml"
PROVIDER_SECRET_FILE_ENV = "ATLAS_PROVIDER_SECRET_FILE"
SECRET_FILE_MODE = 0o600


class ProviderSecretStoreError(RuntimeError):
    """Raised when Atlas cannot load or update provider connection secrets."""


class ProviderSecretValidationError(ValueError):
    """Raised when provider secret store input is invalid."""


class ProviderSecretEntry(BaseModel):
    secrets: dict[str, SecretStr] = Field(default_factory=dict)


class ProviderSecretDocument(BaseModel):
    version: int = 1
    providers: dict[str, ProviderSecretEntry] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("provider secret store version must be 1.")
        return value

    @field_validator("providers")
    @classmethod
    def validate_provider_keys(
        cls,
        values: dict[str, ProviderSecretEntry],
    ) -> dict[str, ProviderSecretEntry]:
        for provider_id in values:
            _validate_identifier(provider_id, "provider_id")
        return values


def get_provider_secret_file() -> Path:
    return Path(
        os.environ.get(
            PROVIDER_SECRET_FILE_ENV,
            str(DEFAULT_PROVIDER_SECRET_FILE),
        ),
    )


def ensure_provider_secret_file(secret_file: Path | None = None) -> Path:
    resolved_file = secret_file or get_provider_secret_file()
    if resolved_file.exists():
        os.chmod(resolved_file, SECRET_FILE_MODE)
        return resolved_file

    resolved_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        _atomic_create_file(
            resolved_file,
            _dump_document(ProviderSecretDocument()),
            mode=SECRET_FILE_MODE,
        )
        os.chmod(resolved_file, SECRET_FILE_MODE)
    except FileExistsError:
        return resolved_file
    except OSError as error:
        raise ProviderSecretStoreError(
            f"Atlas provider secret initialization failed for {resolved_file}: {error}",
        ) from error
    return resolved_file


def load_provider_secrets(secret_file: Path | None = None) -> ProviderSecretDocument:
    resolved_file = secret_file or ensure_provider_secret_file()
    if not resolved_file.exists():
        return ProviderSecretDocument()

    try:
        with resolved_file.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        return ProviderSecretDocument.model_validate(data)
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise ProviderSecretStoreError(
            f"Atlas provider secret load failed for {resolved_file}: {type(error).__name__}",
        ) from error


def get_configured_secret_names(
    provider_id: str,
    secret_file: Path | None = None,
) -> list[str]:
    normalized_provider_id = _validate_identifier(provider_id, "provider_id")
    document = load_provider_secrets(secret_file)
    provider = document.providers.get(normalized_provider_id)
    if provider is None:
        return []
    return sorted(provider.secrets)


def get_provider_secret_value(
    provider_id: str,
    secret_name: str,
    secret_file: Path | None = None,
) -> str | None:
    normalized_provider_id = _validate_identifier(provider_id, "provider_id")
    normalized_secret_name = _validate_identifier(secret_name, "secret_name")
    document = load_provider_secrets(secret_file)
    provider = document.providers.get(normalized_provider_id)
    if provider is None:
        return None
    secret = provider.secrets.get(normalized_secret_name)
    if secret is None:
        return None
    return secret.get_secret_value()


def replace_provider_secret(
    provider_id: str,
    secret_name: str,
    secret_value: str,
    secret_file: Path | None = None,
) -> None:
    update_provider_secrets(
        provider_id,
        replacements={secret_name: secret_value},
        secret_file=secret_file,
    )


def remove_provider_secret(
    provider_id: str,
    secret_name: str,
    secret_file: Path | None = None,
) -> None:
    update_provider_secrets(
        provider_id,
        removals={secret_name},
        secret_file=secret_file,
    )


def update_provider_secrets(
    provider_id: str,
    replacements: dict[str, str] | None = None,
    removals: set[str] | None = None,
    secret_file: Path | None = None,
) -> None:
    normalized_provider_id = _validate_identifier(provider_id, "provider_id")
    normalized_replacements = _validate_replacements(replacements or {})
    normalized_removals = {
        _validate_identifier(secret_name, "secret_name")
        for secret_name in (removals or set())
    }
    resolved_file = secret_file or ensure_provider_secret_file()
    if not resolved_file.exists():
        ensure_provider_secret_file(resolved_file)
    resolved_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = resolved_file.with_name(f".{resolved_file.name}.lock")

    with lock_file.open("w", encoding="utf-8") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            document = _load_secret_mapping(resolved_file)
            providers = document.setdefault("providers", {})
            provider_section = providers.setdefault(normalized_provider_id, {})
            if not isinstance(provider_section, dict):
                raise ProviderSecretValidationError("provider secret section must be a mapping.")
            secrets = provider_section.setdefault("secrets", {})
            if not isinstance(secrets, dict):
                raise ProviderSecretValidationError("provider secrets must be a mapping.")

            for secret_name in normalized_removals:
                secrets.pop(secret_name, None)
            for secret_name, secret_value in normalized_replacements.items():
                secrets[secret_name] = secret_value

            ProviderSecretDocument.model_validate(document)
            _atomic_write_secret_document(document, resolved_file)
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def _load_secret_mapping(secret_file: Path) -> dict:
    load_provider_secrets(secret_file)
    with secret_file.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ProviderSecretValidationError("provider secret store must be a mapping.")
    return data


def _validate_identifier(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ProviderSecretValidationError(f"{label} must not be empty.")
    if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
        raise ProviderSecretValidationError(f"{label} must not contain path separators.")
    return normalized


def _validate_replacements(replacements: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for secret_name, secret_value in replacements.items():
        normalized_name = _validate_identifier(secret_name, "secret_name")
        if not isinstance(secret_value, str) or not secret_value:
            raise ProviderSecretValidationError(
                "secret replacement values must be non-empty strings.",
            )
        normalized[normalized_name] = secret_value
    return normalized


def _atomic_write_secret_document(document: dict, secret_file: Path) -> None:
    ProviderSecretDocument.model_validate(document)
    _atomic_write_text(_dump_mapping(document), secret_file, mode=SECRET_FILE_MODE)
    load_provider_secrets(secret_file)


def _dump_document(document: ProviderSecretDocument) -> str:
    return _dump_mapping(_plain_secret_mapping(document))


def _dump_mapping(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def _plain_secret_mapping(document: ProviderSecretDocument) -> dict:
    providers: dict[str, dict[str, dict[str, str]]] = {}
    for provider_id, provider in document.providers.items():
        providers[provider_id] = {
            "secrets": {
                secret_name: secret.get_secret_value()
                for secret_name, secret in provider.secrets.items()
            },
        }
    return {"version": document.version, "providers": providers}


def _atomic_create_file(target: Path, content: str, *, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    file_descriptor = os.open(target, flags, mode)
    try:
        os.fchmod(file_descriptor, mode)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        raise
    _fsync_directory(target.parent)


def _atomic_write_text(content: str, target: Path, *, mode: int) -> None:
    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temp_path = Path(temp_name)
        os.fchmod(file_descriptor, mode)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, target)
        os.chmod(target, mode)
        _fsync_directory(target.parent)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _fsync_directory(directory: Path) -> None:
    directory_fd = os.open(directory, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
