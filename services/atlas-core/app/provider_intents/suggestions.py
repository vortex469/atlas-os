"""Read-only projection of identity-bound advisory monitoring suggestions."""

from __future__ import annotations

from app.models.provider_intent_suggestions import (
    ProviderMonitoringIntentSuggestionV1,
    observed_running_suggestion,
)
from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptor,
)


def project_provider_monitoring_intent_suggestions(
    descriptor: ProviderManagementDescriptor,
) -> tuple[ProviderMonitoringIntentSuggestionV1, ...]:
    """Apply the sole accepted P5a rule to one coherent management snapshot."""

    if (
        descriptor.provider_id != "proxmox"
        or descriptor.provider_intent_activation != "activated"
        or descriptor.provider_intent_authority_status != "available"
    ):
        return ()

    suggestions: list[ProviderMonitoringIntentSuggestionV1] = []
    for resource in descriptor.resources:
        if not (
            resource.provider_id == descriptor.provider_id
            and resource.resource_type == "qemu"
            and not resource.missing
            and resource.current_state == "running"
            and resource.identity_assurance
            is ManagedResourceIdentityAssurance.AUTHORITATIVE
            and resource.management_fingerprint is not None
            and resource.intent_authority
            is ProviderIntentReadAuthority.PROVIDER_INTENT
            and resource.intent_status is ProviderIntentReadStatus.NEEDS_REVIEW
            and resource.intent_reason
            is ProviderIntentReadReason.NO_ACTIVE_INTENT
            and resource.expectation is None
            and resource.record_version is None
            and not resource.replacement_detected
            and not resource.legacy_review_available
            and resource.legacy_expectation is None
        ):
            continue
        suggestions.append(
            observed_running_suggestion(
                resource_id=resource.resource_id,
                management_fingerprint=resource.management_fingerprint,
            )
        )

    ordered = tuple(
        sorted(
            suggestions,
            key=lambda value: (
                value.provider_id,
                value.resource_type,
                int(value.resource_id),
                value.source_rule,
                value.suggestion_id,
            ),
        )
    )
    identifiers = tuple(value.suggestion_id for value in ordered)
    resource_rules = tuple(
        (
            value.provider_id,
            value.resource_type,
            value.resource_id,
            value.source_rule,
        )
        for value in ordered
    )
    if len(identifiers) != len(set(identifiers)) or len(resource_rules) != len(
        set(resource_rules)
    ):
        raise ValueError("provider monitoring suggestions are not unique")
    return ordered
