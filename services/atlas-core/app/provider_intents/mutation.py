"""Authenticated actor composition for live-verified Provider Intent mutation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from app.config.settings import ProviderIntentActivation
from app.models.provider_intents import (
    ProviderIntentCoordinateMutationCommand,
    ProviderIntentCoordinateMutationResult,
    ProviderIntentKind,
    ProviderIntentMutationRequest,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreConflictError,
    ProviderIntentStoreError,
    ProviderIntentStoreSchemaError,
)
from app.provider_intents.target_resolver import (
    resolve_provider_intent_mutation_target,
)


class ProviderIntentMutationFailureReason(StrEnum):
    MUTATION_NOT_ACTIVATED = "mutation_not_activated"
    STORE_MIGRATION_REQUIRED = "store_migration_required"
    STORE_UNAVAILABLE = "store_unavailable"
    CAS_CONFLICT = "cas_conflict"
    REQUEST_CONFLICT = "request_conflict"
    INVALID_REQUEST = "invalid_request"


class ProviderIntentMutationServiceError(RuntimeError):
    def __init__(self, reason: ProviderIntentMutationFailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


async def mutate_provider_monitoring_intent(
    *,
    operator_id: str,
    provider_id: str,
    resource_type: str,
    resource_id: str,
    request: ProviderIntentMutationRequest,
    activation: ProviderIntentActivation,
    store_path: Path,
) -> ProviderIntentCoordinateMutationResult:
    """Verify live F1, then commit F1-bound intent without provider locking.

    Identity can change after verification and before SQLite commit. The record
    remains bound to verified F1, never transfers to F2, and the next authority
    read reports incarnation mismatch. There is no automatic retry or binding.
    """

    if activation is not ProviderIntentActivation.ACTIVATED:
        raise ProviderIntentMutationServiceError(
            ProviderIntentMutationFailureReason.MUTATION_NOT_ACTIVATED
        )
    target = await resolve_provider_intent_mutation_target(
        provider_id=provider_id,
        resource_type=resource_type,
        resource_id=resource_id,
        expected_management_fingerprint=(
            request.expected_management_fingerprint
        ),
    )
    try:
        store = ProviderIntentStore.open_existing(store_path)
    except ProviderIntentStoreSchemaError as error:
        reason = (
            ProviderIntentMutationFailureReason.STORE_MIGRATION_REQUIRED
            if "migration is required" in str(error)
            else ProviderIntentMutationFailureReason.STORE_UNAVAILABLE
        )
        raise ProviderIntentMutationServiceError(reason) from error
    except (OSError, ProviderIntentStoreError, ValueError) as error:
        raise ProviderIntentMutationServiceError(
            ProviderIntentMutationFailureReason.STORE_UNAVAILABLE
        ) from error
    try:
        command = ProviderIntentCoordinateMutationCommand(
            operator_id=operator_id,
            request_id=request.request_id,
            provider_id=target.provider_id,
            resource_type=target.resource_type,
            resource_id=target.resource_id,
            management_fingerprint=target.management_fingerprint,
            intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
            desired_value=request.expectation,
            expected_record_version=request.expected_record_version,
            acknowledge_monitoring_suppression=(
                request.acknowledge_monitoring_suppression
            ),
        )
        return store.mutate_coordinate(command)
    except ProviderIntentStoreConflictError as error:
        reason = (
            ProviderIntentMutationFailureReason.REQUEST_CONFLICT
            if "request ID" in str(error)
            else ProviderIntentMutationFailureReason.CAS_CONFLICT
        )
        raise ProviderIntentMutationServiceError(reason) from error
    except ValidationError as error:
        raise ProviderIntentMutationServiceError(
            ProviderIntentMutationFailureReason.INVALID_REQUEST
        ) from error
    except ProviderIntentStoreError as error:
        raise ProviderIntentMutationServiceError(
            ProviderIntentMutationFailureReason.STORE_UNAVAILABLE
        ) from error
