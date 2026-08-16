from __future__ import annotations

import pytest

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
    ProviderMonitoringExpectation,
)
from app.provider_intents.suggestions import (
    project_provider_monitoring_intent_suggestions,
)
from app.providers.management import provider_resource_management_registry

FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64


def _resource(**overrides: object) -> ManagedResourceProjection:
    values: dict[str, object] = {
        "provider_id": "proxmox",
        "resource_id": "110",
        "resource_type": "qemu",
        "display_name": "Frigate",
        "current_state": "running",
        "missing": False,
        "identity_assurance": ManagedResourceIdentityAssurance.AUTHORITATIVE,
        "management_fingerprint": FINGERPRINT_A,
        "intent_authority": ProviderIntentReadAuthority.PROVIDER_INTENT,
        "intent_status": ProviderIntentReadStatus.NEEDS_REVIEW,
        "intent_reason": ProviderIntentReadReason.NO_ACTIVE_INTENT,
        "expectation": None,
        "record_version": None,
        "legacy_review_available": False,
        "legacy_expectation": None,
        "replacement_detected": False,
    }
    values.update(overrides)
    return ManagedResourceProjection(**values)


def _descriptor(
    *resources: ManagedResourceProjection,
    provider_id: str = "proxmox",
    activation: str = "activated",
    authority: str = "available",
) -> ProviderManagementDescriptor:
    return ProviderManagementDescriptor(
        provider_id=provider_id,
        provider_name=provider_id.title(),
        sections=tuple(
            ProviderManagementSectionDescriptor(
                section=section,
                availability=ProviderManagementSectionAvailability.AVAILABLE,
            )
            for section in ProviderManagementSection
        ),
        resource_types=provider_resource_management_registry.for_provider(
            provider_id
        ),
        resources=resources,
        provider_intent_activation=activation,  # type: ignore[arg-type]
        provider_intent_authority_status=authority,  # type: ignore[arg-type]
    )


def test_exact_eligible_qemu_projects_one_deterministic_running_suggestion() -> None:
    descriptor = _descriptor(_resource())
    first = project_provider_monitoring_intent_suggestions(descriptor)
    second = project_provider_monitoring_intent_suggestions(descriptor)
    assert first == second
    assert len(first) == 1
    assert first[0].suggested_expectation is ProviderMonitoringExpectation.RUNNING
    assert first[0].base_record_version == 0
    assert first[0].management_fingerprint == FINGERPRINT_A


def test_changed_incarnation_fingerprint_changes_suggestion_identity() -> None:
    first = project_provider_monitoring_intent_suggestions(
        _descriptor(_resource())
    )[0]
    second = project_provider_monitoring_intent_suggestions(
        _descriptor(_resource(management_fingerprint=FINGERPRINT_B))
    )[0]
    assert first.suggestion_id != second.suggestion_id


@pytest.mark.parametrize(
    "expectation",
    tuple(ProviderMonitoringExpectation),
)
def test_configured_resources_emit_nothing(
    expectation: ProviderMonitoringExpectation,
) -> None:
    configured = _resource(
        intent_status=ProviderIntentReadStatus.CONFIGURED,
        intent_reason=ProviderIntentReadReason.MATCHING_ACTIVE_INTENT,
        expectation=expectation,
        record_version=1,
    )
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(configured)
    ) == ()


def test_stopped_resource_without_active_intent_emits_nothing() -> None:
    stopped = _resource(current_state="stopped")
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(stopped)
    ) == ()


def test_replacement_emits_nothing() -> None:
    replacement = _resource(
        intent_reason=ProviderIntentReadReason.INCARNATION_MISMATCH,
        replacement_detected=True,
    )
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(replacement)
    ) == ()


@pytest.mark.parametrize(
    "legacy_expectation",
    tuple(ProviderMonitoringExpectation),
)
def test_every_legacy_review_value_emits_nothing(
    legacy_expectation: ProviderMonitoringExpectation,
) -> None:
    legacy = _resource(
        intent_reason=ProviderIntentReadReason.LEGACY_UNBOUND_EVIDENCE,
        legacy_review_available=True,
        legacy_expectation=legacy_expectation,
    )
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(legacy)
    ) == ()


def test_missing_identity_unavailable_and_authority_degradation_emit_nothing() -> None:
    missing = _resource(
        missing=True,
        identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
        management_fingerprint=None,
        intent_status=ProviderIntentReadStatus.MISSING,
        intent_reason=ProviderIntentReadReason.RESOURCE_MISSING,
        expectation=ProviderMonitoringExpectation.RUNNING,
        record_version=1,
    )
    unavailable = _resource(
        identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
        management_fingerprint=None,
        intent_reason=ProviderIntentReadReason.IDENTITY_UNAVAILABLE,
    )
    eligible = _resource()
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(missing, unavailable)
    ) == ()
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(eligible, authority="unavailable")
    ) == ()
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(eligible, activation="not_activated")
    ) == ()


def test_lxc_and_same_numeric_qemu_are_isolated() -> None:
    lxc = _resource(
        resource_type="lxc",
        display_name="Legacy container",
        identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
        management_fingerprint=None,
        intent_status=ProviderIntentReadStatus.UNSUPPORTED,
        intent_reason=ProviderIntentReadReason.RESOURCE_TYPE_UNSUPPORTED,
    )
    suggestions = project_provider_monitoring_intent_suggestions(
        _descriptor(lxc, _resource())
    )
    assert [(item.resource_type, item.resource_id) for item in suggestions] == [
        ("qemu", "110")
    ]


def test_multiple_qemus_are_sorted_by_canonical_numeric_coordinate() -> None:
    suggestions = project_provider_monitoring_intent_suggestions(
        _descriptor(
            _resource(resource_id="200", management_fingerprint=FINGERPRINT_B),
            _resource(resource_id="110"),
        )
    )
    assert [item.resource_id for item in suggestions] == ["110", "200"]


def test_non_proxmox_provider_emits_nothing() -> None:
    assert project_provider_monitoring_intent_suggestions(
        _descriptor(provider_id="docker")
    ) == ()
