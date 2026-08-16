"""Read-only live identity verification for Provider Intent mutation."""

from __future__ import annotations

from enum import StrEnum

from app.models.provider_intents import VerifiedProviderIntentMutationTarget
from app.models.provider_management import ManagedResourceIdentityAssurance
from app.providers import ProviderNotFoundError
from app.providers.resources import ProviderResourceAdapter
from app.services.provider_management import project_managed_resource
from app.services.provider_resources import get_provider


class ProviderIntentTargetFailureReason(StrEnum):
    PROVIDER_NOT_FOUND = "provider_not_found"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    UNSUPPORTED_RESOURCE_TYPE = "unsupported_resource_type"
    INVALID_COORDINATE = "invalid_coordinate"
    COORDINATE_NOT_FOUND = "coordinate_not_found"
    COORDINATE_AMBIGUOUS = "coordinate_ambiguous"
    RESOURCE_MISSING = "resource_missing"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    PROVIDER_READ_UNAVAILABLE = "provider_read_unavailable"


class ProviderIntentTargetResolutionError(RuntimeError):
    def __init__(self, reason: ProviderIntentTargetFailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


async def resolve_provider_intent_mutation_target(
    *,
    provider_id: str,
    resource_type: str,
    resource_id: str,
    expected_management_fingerprint: str,
) -> VerifiedProviderIntentMutationTarget:
    """Verify one current resource without refresh, mutation, or execution."""

    for value in (provider_id, resource_type, resource_id):
        if not value or value != value.strip():
            raise ProviderIntentTargetResolutionError(
                ProviderIntentTargetFailureReason.INVALID_COORDINATE
            )
    try:
        provider = get_provider(provider_id)
    except ProviderNotFoundError as error:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.PROVIDER_NOT_FOUND
        ) from error
    if provider_id != "proxmox":
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.UNSUPPORTED_PROVIDER
        )
    if resource_type != "qemu":
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.UNSUPPORTED_RESOURCE_TYPE
        )
    if not resource_id.isascii() or not resource_id.isdigit():
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.INVALID_COORDINATE
        )
    if not isinstance(provider, ProviderResourceAdapter):
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.PROVIDER_READ_UNAVAILABLE
        )
    try:
        collection = await provider.list_resources()
    except Exception as error:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.PROVIDER_READ_UNAVAILABLE
        ) from error
    if collection.provider_id != provider_id:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.PROVIDER_READ_UNAVAILABLE
        )
    matches = tuple(
        resource
        for resource in collection.resources
        if resource.provider_id == provider_id
        and resource.resource_type == resource_type
        and resource.resource_id == resource_id
    )
    if not matches:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.COORDINATE_NOT_FOUND
        )
    if len(matches) != 1:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.COORDINATE_AMBIGUOUS
        )
    resource = matches[0]
    if resource.missing:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.RESOURCE_MISSING
        )
    projection = project_managed_resource(resource)
    if (
        projection.identity_assurance
        is not ManagedResourceIdentityAssurance.AUTHORITATIVE
        or projection.management_fingerprint is None
    ):
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.IDENTITY_UNAVAILABLE
        )
    if projection.management_fingerprint != expected_management_fingerprint:
        raise ProviderIntentTargetResolutionError(
            ProviderIntentTargetFailureReason.FINGERPRINT_MISMATCH
        )
    return VerifiedProviderIntentMutationTarget(
        provider_id="proxmox",
        resource_type="qemu",
        resource_id=resource_id,
        management_fingerprint=projection.management_fingerprint,
    )
