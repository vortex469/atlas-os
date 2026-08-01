from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config.inventory import load_inventory
from app.config.provider_connections import (
    get_provider_connection_values,
    replace_provider_connection_values,
    update_provider_connection_values,
)
from app.config.provider_secrets import (
    get_configured_secret_names,
    get_provider_secret_value,
    replace_provider_secret_values,
    update_provider_secrets,
)
from app.context import AtlasContext
from app.models.connections import (
    ProviderConnectionSchema,
    TestProviderConnectionRequest,
    TestProviderConnectionResult,
    UpdateProviderConnectionRequest,
    UpdateProviderConnectionResult,
)
from app.providers.base import Provider
from app.providers.connections import ProviderConnectionAdapter
from app.providers.factory import (
    ProviderFactoryRegistry,
    default_provider_factory_registry,
    provider_type_from_context,
)
from app.providers.registry import ProviderRegistry, provider_registry
from app.services.atlas_contexts import LegacyAtlasContextResolver


class ProviderConnectionServiceError(RuntimeError):
    """Stable sanitized internal connection orchestration failure."""


_CONTEXT_RESOLVER_FACTORY = Callable[[Path | None, Path | None], LegacyAtlasContextResolver]
_SECRET_FIELDS = frozenset({"user", "token_name", "token_value", "api_key", "token"})


class ProviderConnectionService:
    """Coordinate provider-neutral connection schema, tests, and updates."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry | None = None,
        factory_registry: ProviderFactoryRegistry | None = None,
        context_resolver_factory: _CONTEXT_RESOLVER_FACTORY | None = None,
        connection_file: Path | None = None,
        secret_file: Path | None = None,
    ) -> None:
        self._registry = registry or provider_registry
        self._factory_registry = factory_registry or default_provider_factory_registry()
        self._context_resolver_factory = context_resolver_factory or _default_context_resolver_factory
        self._connection_file = connection_file
        self._secret_file = secret_file

    def connection_schema(self, provider_id: str) -> ProviderConnectionSchema:
        provider = self._provider(provider_id)
        adapter = self._adapter(provider)
        return adapter.connection_schema()

    async def test_connection(
        self,
        provider_id: str,
        request: TestProviderConnectionRequest,
    ) -> TestProviderConnectionResult:
        provider = self._provider(provider_id)
        adapter = self._adapter(provider)
        self._validate_candidate(adapter.connection_schema(), request.values)
        return await adapter.test_connection(request)

    async def update_connection(
        self,
        provider_id: str,
        request: UpdateProviderConnectionRequest,
        *,
        require_test: bool = True,
    ) -> UpdateProviderConnectionResult:
        if not request.confirmed:
            raise ProviderConnectionServiceError("connection update requires confirmation.")

        old_provider = self._provider(provider_id)
        adapter = self._adapter(old_provider)
        schema = adapter.connection_schema()
        if not schema.editable or schema.metadata.get("update_supported") is False:
            raise ProviderConnectionServiceError("provider connection updates are not supported.")
        self._validate_candidate(schema, request.values)

        if require_test:
            test_result = await adapter.test_connection(
                TestProviderConnectionRequest(values=request.values, confirmed=True),
            )
            if test_result.status == "failure":
                raise ProviderConnectionServiceError("candidate provider connection test failed.")

        connection_values, secret_values = _split_values(schema, request.values)
        previous_connection = get_provider_connection_values(provider_id, self._connection_file)
        previous_secrets = _read_provider_secrets(provider_id, self._secret_file)
        old_registered = self._registry.get(provider_id)

        try:
            if connection_values:
                update_provider_connection_values(
                    provider_id,
                    connection_values,
                    self._connection_file,
                )
            if secret_values:
                update_provider_secrets(
                    provider_id,
                    replacements=secret_values,
                    secret_file=self._secret_file,
                )
            atlas_context = self._resolve_context(provider_id)
            replacement = self._build_provider(atlas_context)
            if replacement.metadata.id != provider_id:
                raise ProviderConnectionServiceError("replacement provider identity mismatch.")
            self._registry.replace(replacement)
        except Exception as error:
            self._rollback(provider_id, previous_connection, previous_secrets, old_registered)
            raise ProviderConnectionServiceError(_sanitize_error(error)) from error

        return UpdateProviderConnectionResult(
            provider_id=provider_id,
            connection_schema=self.connection_schema(provider_id),
            updated_at=datetime.now(UTC),
            message="Provider connection updated.",
        )

    def _provider(self, provider_id: str) -> Provider:
        try:
            return self._registry.get(provider_id)
        except Exception as error:
            raise ProviderConnectionServiceError("provider is not registered.") from error

    def _adapter(self, provider: Provider) -> ProviderConnectionAdapter:
        if not isinstance(provider, ProviderConnectionAdapter):
            raise ProviderConnectionServiceError("provider does not support connection management.")
        return provider

    def _resolve_context(self, provider_id: str) -> AtlasContext:
        resolver = self._context_resolver_factory(self._connection_file, self._secret_file)
        return resolver.resolve_context(provider_id)

    def _build_provider(self, atlas_context: AtlasContext) -> Provider:
        provider_type = provider_type_from_context(atlas_context)
        factory = self._factory_registry.get(provider_type)
        provider = factory.build(atlas_context)
        provider.atlas_context = atlas_context  # type: ignore[attr-defined]
        return provider

    def _rollback(
        self,
        provider_id: str,
        previous_connection: dict[str, Any],
        previous_secrets: dict[str, str],
        old_provider: Provider,
    ) -> None:
        try:
            replace_provider_connection_values(
                provider_id,
                previous_connection,
                self._connection_file,
            )
            replace_provider_secret_values(provider_id, previous_secrets, self._secret_file)
            self._registry.replace(old_provider)
        except Exception as rollback_error:
            raise ProviderConnectionServiceError("connection update rollback failed.") from rollback_error

    def _validate_candidate(
        self,
        schema: ProviderConnectionSchema,
        values: Mapping[str, Any],
    ) -> None:
        fields = {field.key: field for field in schema.fields}
        unknown = set(values) - set(fields)
        if unknown:
            raise ProviderConnectionServiceError("candidate connection contains unsupported fields.")
        for key, value in values.items():
            field = fields[key]
            if not field.editable:
                raise ProviderConnectionServiceError("candidate connection contains read-only fields.")
            if field.kind == "port" and value is not None:
                try:
                    port = int(value)
                except (TypeError, ValueError) as error:
                    raise ProviderConnectionServiceError("candidate port is invalid.") from error
                if port < 1 or port > 65535:
                    raise ProviderConnectionServiceError("candidate port is invalid.")
            if field.secret and value == "":
                raise ProviderConnectionServiceError("empty secret values are not valid updates.")


def _default_context_resolver_factory(
    connection_file: Path | None,
    secret_file: Path | None,
) -> LegacyAtlasContextResolver:
    return LegacyAtlasContextResolver(
        inventory=load_inventory(),
        runtime_connection_file=connection_file,
        runtime_secret_file=secret_file,
    )


def _split_values(
    schema: ProviderConnectionSchema,
    values: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    fields = {field.key: field for field in schema.fields}
    connection_values: dict[str, Any] = {}
    secret_values: dict[str, str] = {}
    for key, value in values.items():
        field = fields[key]
        if field.secret or field.kind == "secret" or key in _SECRET_FIELDS:
            if value not in {None, ""}:
                secret_values[key] = str(value)
        else:
            connection_values[key] = value
    return connection_values, secret_values


def _read_provider_secrets(provider_id: str, secret_file: Path | None) -> dict[str, str]:
    secrets: dict[str, str] = {}
    for name in get_configured_secret_names(provider_id, secret_file):
        value = get_provider_secret_value(provider_id, name, secret_file)
        if value is not None:
            secrets[name] = value
    return secrets


def _sanitize_error(error: Exception) -> str:
    if isinstance(error, ProviderConnectionServiceError):
        message = str(error)
    else:
        message = "provider connection update failed."
    return message.replace("/opt/atlas/data", "[runtime]")[:240]
