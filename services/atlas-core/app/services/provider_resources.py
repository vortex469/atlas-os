from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.actions.history import record_provider_action_audit
from app.actions.models import ProviderActionAuditEntry
from app.models.resources import (
    ProviderResourceCollection,
    UpdateResourceExpectationResult,
)
from app.provider_intents.authority import (
    ProviderIntentMutationUnavailableError,
    get_monitoring_intent_authority,
)
from app.providers import Provider
from app.providers.resources import ProviderResourceAdapter
from app.services.provider_resource_identity import (
    OperationalTargetAmbiguousError,  # noqa: F401 - compatibility reexport
    OperationalTargetIdentityUnavailableError,  # noqa: F401 - compatibility reexport
    OperationalTargetMarkedMissingError,  # noqa: F401 - compatibility reexport
    OperationalTargetResolutionError,  # noqa: F401 - compatibility reexport
    OperationalTargetResourceNotFoundError,  # noqa: F401 - compatibility reexport
    OperationalTargetSelectorError,  # noqa: F401 - compatibility reexport
    OperationalTargetStateUnavailableError,  # noqa: F401 - compatibility reexport
    OperationalTargetTypeMismatchError,  # noqa: F401 - compatibility reexport
    ProviderResourceError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    ResolvedOperationalTarget,  # noqa: F401 - compatibility reexport
    get_provider,
    get_resource_adapter,
    resolve_operational_target,  # noqa: F401 - compatibility reexport
)

RESOURCE_EXPECTATION_ACTION_ID = "update-resource-expectation"
RESOURCE_EXPECTATION_ACTION_LABEL = "Update Resource Expectation"


class ProviderResourceConfirmationRequiredError(ProviderResourceError):
    """Raised when a policy-changing resource request is unconfirmed."""


class ProviderResourceInvalidExpectationError(ProviderResourceError):
    """Raised when a provider-specific expectation value is invalid."""


class ProviderResourcePolicyWriteError(ProviderResourceOperationError):
    """Raised when a provider resource policy write cannot complete."""


async def list_provider_resources(
    provider_id: str,
) -> ProviderResourceCollection:
    adapter = get_resource_adapter(provider_id)

    try:
        collection = await adapter.list_resources()
        return get_monitoring_intent_authority().resolve_collection(collection)
    except ProviderResourceError:
        raise
    except Exception as error:
        raise ProviderResourceOperationError(
            f"Provider '{provider_id}' resources are unavailable."
        ) from error


async def refresh_provider_resources(
    provider_id: str,
) -> ProviderResourceCollection:
    adapter = get_resource_adapter(provider_id)

    try:
        collection = await adapter.refresh_resources()
        return get_monitoring_intent_authority().resolve_collection(collection)
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

        if provider_id == "proxmox":
            get_monitoring_intent_authority().require_legacy_mutation_available()

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
    except ProviderIntentMutationUnavailableError:
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
