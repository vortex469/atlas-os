from __future__ import annotations

import copy
import fcntl
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

ATLAS_ROOT = Path("/opt/atlas")
DEFAULT_PROVIDER_CONNECTION_FILE = ATLAS_ROOT / "data" / "config" / "provider-connections.yaml"
DEFAULT_PROVIDER_CONNECTION_TEMPLATE_FILE = ATLAS_ROOT / "config" / "provider-connections.yaml"
PROVIDER_CONNECTION_FILE_ENV = "ATLAS_PROVIDER_CONNECTION_FILE"
PROVIDER_CONNECTION_TEMPLATE_FILE_ENV = "ATLAS_PROVIDER_CONNECTION_TEMPLATE_FILE"


class ProviderConnectionStoreError(RuntimeError):
    """Raised when Atlas cannot load or update provider connection values."""


class ProviderConnectionValidationError(ValueError):
    """Raised when provider connection store input is invalid."""


class ProviderConnectionEntry(BaseModel):
    connection: dict[str, Any] = Field(default_factory=dict)


class ProviderConnectionDocument(BaseModel):
    version: int = 1
    providers: dict[str, ProviderConnectionEntry] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("provider connection store version must be 1.")
        return value

    @field_validator("providers")
    @classmethod
    def validate_provider_keys(
        cls,
        values: dict[str, ProviderConnectionEntry],
    ) -> dict[str, ProviderConnectionEntry]:
        for provider_id in values:
            _validate_provider_id(provider_id)
        return values


def get_provider_connection_file() -> Path:
    return Path(
        os.environ.get(
            PROVIDER_CONNECTION_FILE_ENV,
            str(DEFAULT_PROVIDER_CONNECTION_FILE),
        ),
    )


def get_provider_connection_template_file() -> Path:
    return Path(
        os.environ.get(
            PROVIDER_CONNECTION_TEMPLATE_FILE_ENV,
            str(DEFAULT_PROVIDER_CONNECTION_TEMPLATE_FILE),
        ),
    )


def ensure_provider_connection_file(
    connection_file: Path | None = None,
    template_file: Path | None = None,
) -> Path:
    resolved_file = connection_file or get_provider_connection_file()
    resolved_template = template_file or get_provider_connection_template_file()

    if resolved_file.exists():
        return resolved_file

    resolved_file.parent.mkdir(parents=True, exist_ok=True)

    if resolved_template.exists():
        try:
            template_text = resolved_template.read_text(encoding="utf-8")
            _validate_connection_text(template_text)
            _atomic_create_file(resolved_file, template_text, mode=0o600)
            load_provider_connections(resolved_file)
        except FileExistsError:
            return resolved_file
        except (OSError, ValidationError, yaml.YAMLError) as error:
            raise ProviderConnectionStoreError(
                "Atlas provider connection initialization failed for "
                f"{resolved_file} from template {resolved_template}: {error}",
            ) from error
    else:
        try:
            _atomic_create_file(resolved_file, _dump_document(ProviderConnectionDocument()), mode=0o600)
        except FileExistsError:
            return resolved_file
        except OSError as error:
            raise ProviderConnectionStoreError(
                f"Atlas provider connection initialization failed for {resolved_file}: {error}",
            ) from error

    return resolved_file


def load_provider_connections(
    connection_file: Path | None = None,
) -> ProviderConnectionDocument:
    resolved_file = connection_file or ensure_provider_connection_file()
    if not resolved_file.exists():
        return ProviderConnectionDocument()

    try:
        with resolved_file.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        return ProviderConnectionDocument.model_validate(data)
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise ProviderConnectionStoreError(
            f"Atlas provider connection load failed for {resolved_file}: {error}",
        ) from error


def get_provider_connection_values(
    provider_id: str,
    connection_file: Path | None = None,
) -> dict[str, Any]:
    normalized_provider_id = _validate_provider_id(provider_id)
    document = load_provider_connections(connection_file)
    provider = document.providers.get(normalized_provider_id)
    if provider is None:
        return {}
    return copy.deepcopy(provider.connection)


def update_provider_connection_values(
    provider_id: str,
    values: dict[str, Any],
    connection_file: Path | None = None,
) -> dict[str, Any]:
    normalized_provider_id = _validate_provider_id(provider_id)
    _validate_connection_values(values)
    resolved_file = connection_file or ensure_provider_connection_file()
    resolved_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = resolved_file.with_name(f".{resolved_file.name}.lock")

    with lock_file.open("w", encoding="utf-8") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            document = _load_connection_mapping(resolved_file)
            providers = document.setdefault("providers", {})
            provider_section = providers.setdefault(normalized_provider_id, {})
            if not isinstance(provider_section, dict):
                raise ProviderConnectionValidationError(
                    "provider connection section must be a mapping.",
                )
            connection = provider_section.setdefault("connection", {})
            if not isinstance(connection, dict):
                raise ProviderConnectionValidationError(
                    "provider connection values must be a mapping.",
                )
            connection.update(copy.deepcopy(values))
            ProviderConnectionDocument.model_validate(document)
            _atomic_write_connection_document(document, resolved_file)
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)

    return get_provider_connection_values(normalized_provider_id, resolved_file)


def _load_connection_mapping(connection_file: Path) -> dict[str, Any]:
    load_provider_connections(connection_file)
    with connection_file.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ProviderConnectionValidationError("provider connection store must be a mapping.")
    return data


def _validate_connection_text(connection_text: str) -> ProviderConnectionDocument:
    data = yaml.safe_load(connection_text) or {}
    return ProviderConnectionDocument.model_validate(data)


def _validate_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip()
    if not normalized:
        raise ProviderConnectionValidationError("provider_id must not be empty.")
    if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
        raise ProviderConnectionValidationError("provider_id must not contain path separators.")
    return normalized


def _validate_connection_values(values: dict[str, Any]) -> None:
    if not isinstance(values, dict):
        raise ProviderConnectionValidationError("connection values must be a mapping.")
    for key in values:
        if not isinstance(key, str) or not key.strip():
            raise ProviderConnectionValidationError("connection value keys must be non-empty strings.")
        if key in {".", ".."} or "/" in key or "\\" in key:
            raise ProviderConnectionValidationError("connection value keys must not contain path separators.")


def _atomic_write_connection_document(document: dict[str, Any], connection_file: Path) -> None:
    ProviderConnectionDocument.model_validate(document)
    _atomic_write_text(_dump_mapping(document), connection_file, mode=0o600)
    load_provider_connections(connection_file)


def _dump_document(document: ProviderConnectionDocument) -> str:
    return _dump_mapping(document.model_dump())


def _dump_mapping(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def _atomic_create_file(target: Path, content: str, *, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    file_descriptor = os.open(target, flags, mode)
    try:
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
