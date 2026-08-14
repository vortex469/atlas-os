from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.resources import (
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
    ProviderResourceSummary,
    UpdateResourceExpectationResult,
)
from app.providers import (
    Provider,
    ProviderHealth,
    ProviderMetadata,
    ProviderNotFoundError,
    ProviderWorkspace,
    provider_registry,
)
from app.services.operational_target_fingerprint import (
    OperationalTargetIdentityUnavailableError as FingerprintIdentityUnavailableError,
)
from app.services.operational_target_fingerprint import (
    build_operational_target_fingerprint,
)
from app.services.provider_resources import (
    OperationalTargetAmbiguousError,
    OperationalTargetIdentityUnavailableError,
    OperationalTargetMarkedMissingError,
    OperationalTargetResourceNotFoundError,
    OperationalTargetSelectorError,
    OperationalTargetStateUnavailableError,
    OperationalTargetTypeMismatchError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    resolve_operational_target,
)


def make_resource(**changes: object) -> ProviderResource:
    values: dict[str, object] = {
        "provider_id": "resource-provider",
        "resource_id": "service-1",
        "display_name": "Service One",
        "resource_type": "service",
        "current_state": "running",
        "identity": ProviderResourceIdentity(
            token="native-uid-1",
            token_version="uid-v1",
        ),
        "expectation": ProviderResourceExpectation(),
        "configured": False,
    }
    values.update(changes)
    return ProviderResource.model_validate(values)


def make_collection(
    resources: list[ProviderResource],
    *,
    provider_id: str = "resource-provider",
) -> ProviderResourceCollection:
    return ProviderResourceCollection(
        provider_id=provider_id,
        provider_name="Resource Provider",
        refreshed_at=datetime.now(UTC),
        resources=resources,
        summary=ProviderResourceSummary(
            total=len(resources),
            configured=0,
            needs_review=len(resources),
            missing=sum(resource.missing for resource in resources),
            ignored=0,
        ),
    )


class ResourceProvider(Provider):
    def __init__(
        self,
        resources: list[ProviderResource] | None = None,
        *,
        collection_provider_id: str = "resource-provider",
        failure: Exception | None = None,
    ) -> None:
        self._metadata = ProviderMetadata(
            id="resource-provider",
            name="Resource Provider",
            version="2.1.0",
            workspace=ProviderWorkspace.OPERATIONS,
        )
        self.resources = resources if resources is not None else [make_resource()]
        self.collection_provider_id = collection_provider_id
        self.failure = failure

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(status="online")

    def expectation_options(self, resource_type: str) -> list[object]:
        return []

    def normalize_expectation(self, resource_type: str, expectation: str) -> str:
        return expectation

    def expectation_label(self, resource_type: str, expectation: str | None) -> str:
        return expectation or "Needs Review"

    async def list_resources(self) -> ProviderResourceCollection:
        if self.failure is not None:
            raise self.failure
        return make_collection(
            self.resources,
            provider_id=self.collection_provider_id,
        )

    async def refresh_resources(self) -> ProviderResourceCollection:
        return await self.list_resources()

    async def update_resource_expectation(
        self,
        resource_id: str,
        expectation: str,
    ) -> UpdateResourceExpectationResult:
        raise NotImplementedError


class HealthOnlyProvider(Provider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            id="health-only",
            name="Health Only",
            workspace=ProviderWorkspace.OPERATIONS,
        )

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(status="online")


@pytest.fixture(autouse=True)
def isolated_provider_registry():
    previous = provider_registry.all()
    provider_registry.clear()
    try:
        yield
    finally:
        provider_registry.replace_all(previous)


def test_target_fingerprint_is_deterministic_and_ignores_presentation_state() -> None:
    provider = ResourceProvider().metadata
    resource = make_resource()
    changed = make_resource(display_name="Renamed", current_state="degraded")

    first = build_operational_target_fingerprint(provider, resource)
    second = build_operational_target_fingerprint(provider, resource.model_copy(deep=True))

    assert first == second
    assert first == build_operational_target_fingerprint(provider, changed)
    assert first.startswith("operational-target-fingerprint-v1:")


def test_target_fingerprint_changes_with_authoritative_identity() -> None:
    provider = ResourceProvider().metadata
    baseline = build_operational_target_fingerprint(provider, make_resource())

    changed_token = build_operational_target_fingerprint(
        provider,
        make_resource(
            identity=ProviderResourceIdentity(token="native-uid-2", token_version="uid-v1")
        ),
    )
    changed_version = build_operational_target_fingerprint(
        provider,
        make_resource(
            identity=ProviderResourceIdentity(token="native-uid-1", token_version="uid-v2")
        ),
    )

    assert changed_token != baseline
    assert changed_version != baseline


def test_target_fingerprint_requires_authoritative_identity() -> None:
    with pytest.raises(FingerprintIdentityUnavailableError):
        build_operational_target_fingerprint(
            ResourceProvider().metadata,
            make_resource(identity=None),
        )


@pytest.mark.anyio
async def test_resolver_returns_one_exact_live_target() -> None:
    provider_registry.register(ResourceProvider())

    resolved = await resolve_operational_target(
        "resource-provider",
        "service-1",
        "service",
    )

    assert resolved.provider.id == "resource-provider"
    assert resolved.resource.resource_id == "service-1"
    assert resolved.resource_fingerprint.startswith("operational-target-fingerprint-v1:")


@pytest.mark.anyio
async def test_resolver_distinguishes_provider_and_adapter_failures() -> None:
    with pytest.raises(ProviderNotFoundError):
        await resolve_operational_target("missing-provider", "service-1", "service")

    provider_registry.register(HealthOnlyProvider())
    with pytest.raises(ProviderResourcesNotSupportedError):
        await resolve_operational_target("health-only", "service-1", "service")


@pytest.mark.anyio
async def test_resolver_rejects_missing_duplicate_and_display_name_fallback() -> None:
    provider_registry.register(ResourceProvider(resources=[]))
    with pytest.raises(OperationalTargetResourceNotFoundError):
        await resolve_operational_target("resource-provider", "Service One", "service")

    provider_registry.replace(ResourceProvider(resources=[make_resource(), make_resource()]))
    with pytest.raises(OperationalTargetAmbiguousError):
        await resolve_operational_target("resource-provider", "service-1", "service")


@pytest.mark.anyio
async def test_resolver_rejects_type_missing_and_unidentified_resources() -> None:
    provider_registry.register(ResourceProvider())
    with pytest.raises(OperationalTargetTypeMismatchError):
        await resolve_operational_target("resource-provider", "service-1", "container")

    provider_registry.replace(ResourceProvider(resources=[make_resource(missing=True)]))
    with pytest.raises(OperationalTargetMarkedMissingError):
        await resolve_operational_target("resource-provider", "service-1", "service")

    provider_registry.replace(ResourceProvider(resources=[make_resource(identity=None)]))
    with pytest.raises(OperationalTargetIdentityUnavailableError):
        await resolve_operational_target("resource-provider", "service-1", "service")


@pytest.mark.anyio
async def test_resolver_rejects_wildcards_without_querying_provider() -> None:
    provider_registry.register(ResourceProvider())
    with pytest.raises(OperationalTargetSelectorError):
        await resolve_operational_target("resource-provider", "*", "service")


@pytest.mark.anyio
async def test_resolver_distinguishes_unavailable_and_inconsistent_live_state() -> None:
    provider_registry.register(ResourceProvider(failure=TimeoutError("offline")))
    with pytest.raises(ProviderResourceOperationError) as error:
        await resolve_operational_target("resource-provider", "service-1", "service")
    assert isinstance(error.value.__cause__, TimeoutError)

    provider_registry.replace(ResourceProvider(collection_provider_id="different-provider"))
    with pytest.raises(OperationalTargetStateUnavailableError):
        await resolve_operational_target("resource-provider", "service-1", "service")
