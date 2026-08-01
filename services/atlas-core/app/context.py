from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

ContextSource = Literal[
    "runtime",
    "atlas_yaml",
    "environment",
    "default",
    "defaults",
    "inventory",
    "settings",
    "computed",
    "missing",
]
DiagnosticSeverity = Literal["info", "warning", "error"]
ConnectionMode = Literal["http", "https", "unix", "local", "custom"]


class AtlasContextModel(BaseModel):
    """Base immutable model for Atlas context contracts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class ConnectionContext(AtlasContextModel):
    """Resolved connection details for an Atlas consumer."""

    mode: ConnectionMode
    configured: bool = True
    source: ContextSource = "computed"
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    base_url: str | None = None
    path: str | None = None
    node: str | None = None
    health_endpoint: str | None = None
    expected_status: int | None = Field(default=None, ge=100, le=599)
    verify_tls: bool = True
    ca_bundle: str | None = None
    timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    metadata: Mapping[str, Any] = Field(default_factory=dict)


class SecretContext(AtlasContextModel):
    """Resolved secret metadata with serialization-safe value handling."""

    name: str = Field(min_length=1)
    source: ContextSource = "missing"
    configured: bool = False
    redacted: str | None = None
    value: SecretStr | None = Field(
        default=None,
        exclude=True,
        repr=False,
    )

    @field_validator("redacted")
    @classmethod
    def reject_secret_like_redaction(cls, value: str | None) -> str | None:
        if value is not None and value.strip() and "secret" in value.lower():
            raise ValueError("redacted secret labels must not expose values.")
        return value

    def reveal(self) -> str | None:
        """Return the secret value for trusted runtime consumers only."""

        if self.value is None:
            return None
        return self.value.get_secret_value()


class RuntimeContext(AtlasContextModel):
    """Resolved runtime paths for an Atlas consumer."""

    data_root: Path = Path("/opt/atlas/data")
    config_root: Path = Path("/opt/atlas/data/config")
    history_root: Path = Path("/opt/atlas/data/history")
    cache_root: Path = Path("/opt/atlas/data/cache")
    knowledge_root: Path = Path("/opt/atlas/data/knowledge")
    consumer_data_root: Path | None = None
    consumer_cache_root: Path | None = None
    intent_reader: Any | None = Field(default=None, exclude=True, repr=False)
    intent_writer: Any | None = Field(default=None, exclude=True, repr=False)
    metadata: Mapping[str, Any] = Field(default_factory=dict)


class MetadataContext(AtlasContextModel):
    """Stable identity and display metadata for an Atlas consumer."""

    consumer_id: str = Field(min_length=1)
    consumer_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    version: str = "1.0.0"
    workspace: str | None = None
    priority: str | None = None
    icon: str | None = None
    capabilities: frozenset[str] = Field(default_factory=frozenset)
    source: ContextSource = "computed"
    metadata: Mapping[str, Any] = Field(default_factory=dict)


class DiagnosticsContextItem(AtlasContextModel):
    """One redacted context diagnostic emitted by a resolver."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: DiagnosticSeverity = "info"
    source: ContextSource = "computed"
    field: str | None = None


class AtlasContextDiagnostics(AtlasContextModel):
    """Redacted diagnostics explaining how an AtlasContext was resolved."""

    items: tuple[DiagnosticsContextItem, ...] = ()

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.items)


DiagnosticsContext = AtlasContextDiagnostics


class AtlasContext(AtlasContextModel):
    """Immutable context passed to Atlas providers and future services."""

    metadata: MetadataContext
    runtime: RuntimeContext
    connection: ConnectionContext | None = None
    secrets: Mapping[str, SecretContext] = Field(default_factory=dict)
    diagnostics: AtlasContextDiagnostics = Field(
        default_factory=AtlasContextDiagnostics,
    )
    generation: str = Field(min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @property
    def consumer_id(self) -> str:
        return self.metadata.consumer_id

    @property
    def consumer_type(self) -> str:
        return self.metadata.consumer_type


@runtime_checkable
class ConnectionResolver(Protocol):
    """Resolve connection state for an Atlas consumer."""

    def resolve_connection(
        self,
        metadata: MetadataContext,
    ) -> ConnectionContext | None:
        """Return the resolved connection context, if any."""


@runtime_checkable
class SecretResolver(Protocol):
    """Resolve secrets for an Atlas consumer without exposing values."""

    def resolve_secrets(
        self,
        metadata: MetadataContext,
    ) -> Mapping[str, SecretContext]:
        """Return resolved secret contexts keyed by logical name."""


@runtime_checkable
class RuntimeResolver(Protocol):
    """Resolve runtime paths and services for an Atlas consumer."""

    def resolve_runtime(
        self,
        metadata: MetadataContext,
    ) -> RuntimeContext:
        """Return resolved runtime context."""


@runtime_checkable
class AtlasContextResolver(Protocol):
    """Build immutable AtlasContext instances for Atlas consumers."""

    def resolve_context(
        self,
        consumer_id: str,
    ) -> AtlasContext:
        """Return one resolved immutable AtlasContext."""

    def resolve_all_contexts(self) -> tuple[AtlasContext, ...]:
        """Return all resolved immutable AtlasContext instances."""
