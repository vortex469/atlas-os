from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.context import (
    AtlasContext,
    AtlasContextDiagnostics,
    AtlasContextResolver,
    ConnectionContext,
    ConnectionResolver,
    DiagnosticsContextItem,
    MetadataContext,
    RuntimeContext,
    RuntimeResolver,
    SecretContext,
    SecretResolver,
)
from app.providers.base import Provider
from app.providers.capabilities import ProviderWorkspace
from app.providers.factory import ContextAwareProvider, ProviderFactory
from app.providers.models import ProviderHealth, ProviderMetadata


def metadata_context() -> MetadataContext:
    return MetadataContext(
        consumer_id="proxmox",
        consumer_type="provider",
        name="Proxmox",
        description="Virtualization provider.",
        capabilities=frozenset({"health", "resources"}),
        source="inventory",
    )


def atlas_context() -> AtlasContext:
    return AtlasContext(
        metadata=metadata_context(),
        connection=ConnectionContext(
            mode="https",
            source="settings",
            host="10.10.50.10",
            port=8006,
            node="vorex469",
            verify_tls=False,
        ),
        secrets={
            "token_value": SecretContext(
                name="token_value",
                source="environment",
                configured=True,
                redacted="********",
                value="super-secret-token",
            ),
        },
        runtime=RuntimeContext(
            data_root=Path("/opt/atlas/data"),
            consumer_data_root=Path("/opt/atlas/data/providers/proxmox"),
        ),
        diagnostics=AtlasContextDiagnostics(
            items=(
                DiagnosticsContextItem(
                    code="legacy-source",
                    message="Connection resolved from atlas.yaml.",
                    severity="info",
                    source="settings",
                    field="connection.host",
                ),
            ),
        ),
        generation="test-generation",
    )


def test_atlas_context_models_are_frozen() -> None:
    context = atlas_context()

    with pytest.raises(ValidationError, match="frozen"):
        context.generation = "changed"  # type: ignore[misc]

    with pytest.raises(ValidationError, match="frozen"):
        context.metadata.name = "Changed"  # type: ignore[misc]


def test_atlas_context_exposes_consumer_identity() -> None:
    context = atlas_context()

    assert context.consumer_id == "proxmox"
    assert context.consumer_type == "provider"
    assert context.connection is not None
    assert context.connection.host == "10.10.50.10"
    assert context.runtime.consumer_data_root == Path(
        "/opt/atlas/data/providers/proxmox",
    )


def test_secret_context_redacts_values_from_serialization() -> None:
    secret = SecretContext(
        name="token_value",
        source="environment",
        configured=True,
        redacted="********",
        value="super-secret-token",
    )

    assert secret.reveal() == "super-secret-token"
    dumped = secret.model_dump()
    dumped_json = secret.model_dump_json()

    assert "value" not in dumped
    assert "super-secret-token" not in dumped_json
    assert "super-secret-token" not in repr(secret)
    assert dumped["redacted"] == "********"


def test_atlas_context_serialization_does_not_expose_nested_secrets() -> None:
    context = atlas_context()

    dumped = context.model_dump(mode="json")
    dumped_json = context.model_dump_json()

    assert "super-secret-token" not in dumped_json
    assert "value" not in dumped["secrets"]["token_value"]
    assert dumped["secrets"]["token_value"]["configured"] is True
    assert dumped["secrets"]["token_value"]["source"] == "environment"


def test_secret_redaction_rejects_secret_like_labels() -> None:
    with pytest.raises(ValidationError, match="must not expose"):
        SecretContext(
            name="token_value",
            source="environment",
            configured=True,
            redacted="super-secret-token",
            value="super-secret-token",
        )


def test_diagnostics_context_reports_errors() -> None:
    diagnostics = AtlasContextDiagnostics(
        items=(
            DiagnosticsContextItem(
                code="missing-secret",
                message="A required secret is missing.",
                severity="error",
                source="missing",
                field="secrets.token_value",
            ),
        ),
    )

    assert diagnostics.has_errors is True
    assert diagnostics.items[0].code == "missing-secret"


def test_resolver_protocols_are_runtime_checkable() -> None:
    class Resolver:
        def resolve_context(self, consumer_id: str) -> AtlasContext:
            assert consumer_id == "proxmox"
            return atlas_context()

        def resolve_all_contexts(self) -> tuple[AtlasContext, ...]:
            return (atlas_context(),)

    class ConnectionOnlyResolver:
        def resolve_connection(
            self,
            metadata: MetadataContext,
        ) -> ConnectionContext | None:
            assert metadata.consumer_id == "proxmox"
            return atlas_context().connection

    class SecretOnlyResolver:
        def resolve_secrets(
            self,
            metadata: MetadataContext,
        ) -> dict[str, SecretContext]:
            assert metadata.consumer_id == "proxmox"
            return dict(atlas_context().secrets)

    class RuntimeOnlyResolver:
        def resolve_runtime(self, metadata: MetadataContext) -> RuntimeContext:
            assert metadata.consumer_id == "proxmox"
            return atlas_context().runtime

    assert isinstance(Resolver(), AtlasContextResolver)
    assert isinstance(ConnectionOnlyResolver(), ConnectionResolver)
    assert isinstance(SecretOnlyResolver(), SecretResolver)
    assert isinstance(RuntimeOnlyResolver(), RuntimeResolver)


def test_context_aware_provider_and_factory_protocols_are_runtime_checkable() -> None:
    context = atlas_context()

    class ExampleProvider(Provider):
        def __init__(self, atlas_context: AtlasContext) -> None:
            self._atlas_context = atlas_context

        @property
        def atlas_context(self) -> AtlasContext:
            return self._atlas_context

        @property
        def metadata(self) -> ProviderMetadata:
            return ProviderMetadata(
                id="example",
                name="Example",
                description="Example provider.",
                workspace=ProviderWorkspace.OPERATIONS,
            )

        async def get_health(self) -> ProviderHealth:
            return ProviderHealth(status="online")

    class ExampleFactory:
        provider_type = "example"

        def build(self, atlas_context: AtlasContext) -> Provider:
            return ExampleProvider(atlas_context)

    provider = ExampleProvider(context)
    factory = ExampleFactory()

    assert isinstance(provider, ContextAwareProvider)
    assert isinstance(factory, ProviderFactory)
    assert factory.build(context).metadata.id == "example"


def test_runtime_context_accepts_provider_specific_metadata() -> None:
    runtime = RuntimeContext(
        metadata={"policy_store": "runtime"},
    )

    assert runtime.data_root == Path("/opt/atlas/data")
    assert runtime.metadata["policy_store"] == "runtime"


def test_connection_context_validates_ports_and_status_codes() -> None:
    with pytest.raises(ValidationError):
        ConnectionContext(mode="https", port=70_000)

    with pytest.raises(ValidationError):
        ConnectionContext(mode="https", expected_status=99)
