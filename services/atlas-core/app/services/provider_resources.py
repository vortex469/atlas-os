from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.actions.history import record_provider_action_audit
from app.actions.models import ProviderActionAuditEntry
from app.models.resources import (
    ProviderResource,
    ProviderResourceCollection,
    UpdateResourceExpectationResult,
)
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

RESOURCE_EXPECTATION_ACTION_ID = "update-resource-expectation"
RESOURCE_EXPECTATION_ACTION_LABEL = "Update Resource Expectation"


class ProviderResourceError(RuntimeError):
    """Base error for provider resource API operations."""


class ProviderResourcesNotSupportedError(ProviderResourceError):
    """Raised when a provider does not implement resource management."""


class ProviderResourceConfirmationRequiredError(ProviderResourceError):
    """Raised when a policy-changing resource request is unconfirmed."""


class ProviderResourceInvalidExpectationError(ProviderResourceError):
    """Raised when a provider-specific expectation value is invalid."""


class ProviderResourceOperationError(ProviderResourceError):
    """Raised when a provider resource operation cannot complete."""


class ProviderResourcePolicyWriteError(ProviderResourceOperationError):
    """Raised when a provider resource policy write cannot complete."""


class OperationalTargetResolutionError(ProviderResourceError):
    """Base error for deterministic operational-target resolution failures."""


class OperationalTargetSelectorError(OperationalTargetResolutionError):
    """Raised when a selector does not identify one exact resource."""


class OperationalTargetResourceNotFoundError(OperationalTargetResolutionError):
    """Raised when an exact resource is absent from current provider state."""


class OperationalTargetAmbiguousError(OperationalTargetResolutionError):
    """Raised when current provider state contains a duplicate resource ID."""


class OperationalTargetTypeMismatchError(OperationalTargetResolutionError):
    """Raised when the exact resource has a different resource type."""


class OperationalTargetMarkedMissingError(OperationalTargetResolutionError):
    """Raised when the provider reports a configured resource as missing."""


class OperationalTargetIdentityUnavailableError(OperationalTargetResolutionError):
    """Raised when the exact resource lacks authoritative identity."""


class OperationalTargetStateUnavailableError(ProviderResourceOperationError):
    """Raised when live provider state is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ResolvedOperationalTarget:
    """An exact live resource and its provider-authoritative fingerprint."""

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


async def list_provider_resources(
    provider_id: str,
) -> ProviderResourceCollection:
    adapter = get_resource_adapter(provider_id)

    try:
        return await adapter.list_resources()
    except ProviderResourceError:
        raise
    except Exception as error:
        raise ProviderResourceOperationError(
            f"Provider '{provider_id}' resources are unavailable."
        ) from error


async def resolve_operational_target(
    provider_id: str,
    resource_id: str,
    resource_type: str,
) -> ResolvedOperationalTarget:
    """Resolve one exact live resource with authoritative identity."""

    for field_name, value in (
        ("provider_id", provider_id),
        ("resource_id", resource_id),
        ("resource_type", resource_type),
    ):
        if not value or value != value.strip():
            raise OperationalTargetSelectorError(
                f"{field_name} must be an exact nonblank identifier."
            )
        if value.casefold() in {"*", "all", "ambiguous", "unknown"}:
            raise OperationalTargetSelectorError(
                f"{field_name} must identify exactly one resource."
            )

    provider = get_provider(provider_id)
    collection = await list_provider_resources(provider_id)
    if collection.provider_id != provider_id:
        raise OperationalTargetStateUnavailableError(
            "Provider resource collection does not match the requested provider."
        )

    matches = [
        resource
        for resource in collection.resources
        if resource.resource_id == resource_id
    ]
    if not matches:
        raise OperationalTargetResourceNotFoundError(
            f"Resource '{resource_id}' was not found for provider '{provider_id}'."
        )
    if len(matches) > 1:
        raise OperationalTargetAmbiguousError(
            f"Resource '{resource_id}' is ambiguous for provider '{provider_id}'."
        )

    resource = matches[0]
    if resource.provider_id != provider_id:
        raise OperationalTargetStateUnavailableError(
            "Resolved resource does not match the requested provider."
        )
    if resource.resource_type != resource_type:
        raise OperationalTargetTypeMismatchError(
            f"Resource '{resource_id}' has type '{resource.resource_type}', "
            f"not '{resource_type}'."
        )
    if resource.missing:
        raise OperationalTargetMarkedMissingError(
            f"Resource '{resource_id}' is marked missing by provider '{provider_id}'."
        )

    try:
        fingerprint = build_operational_target_fingerprint(
            provider.metadata,
            resource,
        )
    except FingerprintIdentityUnavailableError as error:
        raise OperationalTargetIdentityUnavailableError(
            f"Resource '{resource_id}' has no authoritative identity."
        ) from error

    return ResolvedOperationalTarget(
        provider=provider.metadata.model_copy(deep=True),
        resource=resource.model_copy(deep=True),
        resource_fingerprint=fingerprint,
    )


async def refresh_provider_resources(
    provider_id: str,
) -> ProviderResourceCollection:
    adapter = get_resource_adapter(provider_id)

    try:
        return await adapter.refresh_resources()
    except ProviderResourceError:
        raise
    except Exception as error:
        raise ProviderResourceOperationError(
            f"Provider '{provider_id}' discovery refresh failed."
        ) from error


async def update_provider_resource_expectation(
    provider_id: str,
    resource_id: str,
    expectation: str,
    *,
    confirmed: bool,
    request_id: str | None = None,
) -> UpdateResourceExpectationResult:
    provider = get_provider(provider_id)
    started_at = datetime.now(UTC)
    started_timer = perf_counter()

    try:
        if not isinstance(provider, ProviderResourceAdapter):
            raise ProviderResourcesNotSupportedError(
                f"Provider '{provider_id}' does not support resources."
            )

        if not resource_id.strip():
            raise ProviderResourceInvalidExpectationError(
                "resource_id must not be empty."
            )

        if not confirmed:
            raise ProviderResourceConfirmationRequiredError(
                "Resource expectation updates require confirmed=true."
            )

        provider.normalize_expectation("unknown", expectation)
        result = await provider.update_resource_expectation(
            resource_id,
            expectation,
        )
    except ProviderResourceInvalidExpectationError as error:
        _record_expectation_audit(
            provider=provider,
            success=False,
            message=str(error),
            confirmed=confirmed,
            request_id=request_id,
            started_at=started_at,
            started_timer=started_timer,
        )
        raise
    except ProviderResourceConfirmationRequiredError as error:
        _record_expectation_audit(
            provider=provider,
            success=False,
            message=str(error),
            confirmed=confirmed,
            request_id=request_id,
            started_at=started_at,
            started_timer=started_timer,
        )
        raise
    except ValueError as error:
        wrapped = ProviderResourceInvalidExpectationError(
            "Invalid provider resource expectation."
        )
        _record_expectation_audit(
            provider=provider,
            success=False,
            message=str(wrapped),
            confirmed=confirmed,
            request_id=request_id,
            started_at=started_at,
            started_timer=started_timer,
        )
        raise wrapped from error
    except ProviderResourcesNotSupportedError as error:
        _record_expectation_audit(
            provider=provider,
            success=False,
            message=str(error),
            confirmed=confirmed,
            request_id=request_id,
            started_at=started_at,
            started_timer=started_timer,
        )
        raise
    except Exception as error:
        wrapped = ProviderResourcePolicyWriteError(
            "Provider resource expectation update failed."
        )
        _record_expectation_audit(
            provider=provider,
            success=False,
            message=str(wrapped),
            confirmed=confirmed,
            request_id=request_id,
            started_at=started_at,
            started_timer=started_timer,
        )
        raise wrapped from error

    _record_expectation_audit(
        provider=provider,
        success=True,
        message="Resource expectation updated.",
        confirmed=confirmed,
        request_id=request_id,
        started_at=started_at,
        started_timer=started_timer,
    )

    return result


def _record_expectation_audit(
    *,
    provider: Provider,
    success: bool,
    message: str,
    confirmed: bool,
    request_id: str | None,
    started_at: datetime,
    started_timer: float,
) -> None:
    completed_at = datetime.now(UTC)
    record_provider_action_audit(
        ProviderActionAuditEntry(
            id=uuid4().hex,
            provider_id=provider.metadata.id,
            provider_name=provider.metadata.name,
            action_id=RESOURCE_EXPECTATION_ACTION_ID,
            action_label=RESOURCE_EXPECTATION_ACTION_LABEL,
            status="succeeded" if success else "failed",
            success=success,
            message=message,
            confirmed=confirmed,
            destructive=False,
            parameter_names=["confirmed", "expectation", "resource_id"],
            request_id=request_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round((perf_counter() - started_timer) * 1000, 2),
        ),
    )
