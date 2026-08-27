"""Read-only provider resource identity and exact-resolution facade.

This module deliberately has no monitoring-intent, audit, or mutation authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.resources import ProviderResource, ProviderResourceCollection
from app.providers import Provider, ProviderNotFoundError
from app.providers.models import ProviderMetadata
from app.providers.registry import provider_registry
from app.providers.resources import ProviderResourceAdapter
from app.services.operational_target_fingerprint import (
    OperationalTargetIdentityUnavailableError as FingerprintIdentityUnavailableError,
)
from app.services.operational_target_fingerprint import (
    build_operational_target_fingerprint,
)


class ProviderResourceError(RuntimeError):
    pass


class ProviderResourcesNotSupportedError(ProviderResourceError):
    pass


class ProviderResourceOperationError(ProviderResourceError):
    pass


class OperationalTargetResolutionError(ProviderResourceError):
    pass


class OperationalTargetSelectorError(OperationalTargetResolutionError):
    pass


class OperationalTargetResourceNotFoundError(OperationalTargetResolutionError):
    pass


class OperationalTargetAmbiguousError(OperationalTargetResolutionError):
    pass


class OperationalTargetTypeMismatchError(OperationalTargetResolutionError):
    pass


class OperationalTargetMarkedMissingError(OperationalTargetResolutionError):
    pass


class OperationalTargetIdentityUnavailableError(OperationalTargetResolutionError):
    pass


class OperationalTargetStateUnavailableError(ProviderResourceOperationError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedOperationalTarget:
    provider: ProviderMetadata
    resource: ProviderResource
    resource_fingerprint: str


def get_provider(provider_id: str) -> Provider:
    try:
        return provider_registry.get(provider_id)
    except ProviderNotFoundError as error:
        raise ProviderNotFoundError(
            f"Provider '{provider_id}' is not registered."
        ) from error


def get_resource_adapter(provider_id: str) -> ProviderResourceAdapter:
    provider = get_provider(provider_id)
    if not isinstance(provider, ProviderResourceAdapter):
        raise ProviderResourcesNotSupportedError(
            f"Provider '{provider_id}' does not support resources."
        )
    return provider


async def list_provider_resource_identities(
    provider_id: str,
) -> ProviderResourceCollection:
    """Return a detached current read model directly from the provider adapter."""
    try:
        collection = await get_resource_adapter(provider_id).list_resources()
        return collection.model_copy(deep=True)
    except ProviderResourceError:
        raise
    except Exception as error:
        raise ProviderResourceOperationError(
            f"Provider '{provider_id}' resources are unavailable."
        ) from error


async def resolve_operational_target(
    provider_id: str, resource_id: str, resource_type: str
) -> ResolvedOperationalTarget:
    for field_name, value in (
        ("provider_id", provider_id),
        ("resource_id", resource_id),
        ("resource_type", resource_type),
    ):
        if (
            not value
            or value != value.strip()
            or value.casefold() in {"*", "all", "ambiguous", "unknown"}
        ):
            raise OperationalTargetSelectorError(
                f"{field_name} must identify exactly one resource."
            )
    provider = get_provider(provider_id)
    collection = await list_provider_resource_identities(provider_id)
    if collection.provider_id != provider_id:
        raise OperationalTargetStateUnavailableError(
            "Provider resource collection does not match the requested provider."
        )
    matches = [r for r in collection.resources if r.resource_id == resource_id]
    if not matches:
        raise OperationalTargetResourceNotFoundError(
            f"Resource '{resource_id}' was not found for provider '{provider_id}'."
        )
    if len(matches) != 1:
        raise OperationalTargetAmbiguousError(
            f"Resource '{resource_id}' is ambiguous for provider '{provider_id}'."
        )
    resource = matches[0]
    if resource.provider_id != provider_id:
        raise OperationalTargetStateUnavailableError(
            "Resolved resource provider mismatch."
        )
    if resource.resource_type != resource_type:
        raise OperationalTargetTypeMismatchError(
            f"Resource '{resource_id}' has type '{resource.resource_type}', not '{resource_type}'."
        )
    if resource.missing:
        raise OperationalTargetMarkedMissingError(
            f"Resource '{resource_id}' is marked missing."
        )
    try:
        fingerprint = build_operational_target_fingerprint(provider.metadata, resource)
    except FingerprintIdentityUnavailableError as error:
        raise OperationalTargetIdentityUnavailableError(
            f"Resource '{resource_id}' has no authoritative identity."
        ) from error
    return ResolvedOperationalTarget(
        provider=provider.metadata.model_copy(deep=True),
        resource=resource.model_copy(deep=True),
        resource_fingerprint=fingerprint,
    )
