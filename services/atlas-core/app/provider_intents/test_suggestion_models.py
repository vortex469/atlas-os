from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.provider_intent_suggestions import (
    OBSERVED_RUNNING_REASON,
    OBSERVED_RUNNING_RULE,
    ProviderMonitoringIntentSuggestionV1,
    build_provider_monitoring_intent_suggestion_id,
    observed_running_suggestion,
)
from app.models.provider_management import ProviderMonitoringExpectation

FINGERPRINT = "provider-management-fingerprint-v1:" + "a" * 64


def _payload() -> dict[str, object]:
    return observed_running_suggestion(
        resource_id="110", management_fingerprint=FINGERPRINT
    ).model_dump()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", "provider-monitoring-intent-suggestion-v2"),
        ("provider_id", "docker"),
        ("resource_type", "lxc"),
        ("management_fingerprint", "provider-native-secret"),
        ("base_record_version", -1),
        ("base_record_version", 1),
        ("source", "ace_recommendation"),
        ("source_rule", "other-rule-v1"),
        ("reason", "other_reason"),
        ("advisory_only", False),
        ("grants_permission", True),
        ("grants_execution", True),
        ("suggested_expectation", ProviderMonitoringExpectation.STOPPED),
        ("suggested_expectation", ProviderMonitoringExpectation.IGNORED),
    ),
)
def test_contract_rejects_contradictory_values(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        ProviderMonitoringIntentSuggestionV1.model_validate(
            {**_payload(), field: value}
        )


def test_contract_is_frozen_extra_forbid_and_sanitized() -> None:
    suggestion = observed_running_suggestion(
        resource_id="110", management_fingerprint=FINGERPRINT
    )
    with pytest.raises(ValidationError):
        ProviderMonitoringIntentSuggestionV1.model_validate(
            {**suggestion.model_dump(), "metadata": {}}
        )
    with pytest.raises(ValidationError):
        suggestion.base_record_version = 1  # type: ignore[misc]
    assert set(ProviderMonitoringIntentSuggestionV1.model_fields).isdisjoint(
        {
            "operator_id",
            "vmgenid",
            "native_identity",
            "command",
            "url",
            "payload",
            "metadata",
            "audit_id",
            "request_id",
            "created_at",
        }
    )


def test_suggestion_id_is_deterministic_and_binds_complete_source_state() -> None:
    values = {
        "provider_id": "proxmox",
        "resource_type": "qemu",
        "resource_id": "110",
        "management_fingerprint": FINGERPRINT,
        "suggested_expectation": ProviderMonitoringExpectation.RUNNING,
        "base_record_version": 0,
        "source_rule": OBSERVED_RUNNING_RULE,
        "reason": OBSERVED_RUNNING_REASON,
    }
    identifier = build_provider_monitoring_intent_suggestion_id(**values)
    assert identifier == build_provider_monitoring_intent_suggestion_id(
        **values
    )
    changed = (
        {**values, "management_fingerprint": "provider-management-fingerprint-v1:" + "b" * 64},
        {**values, "suggested_expectation": ProviderMonitoringExpectation.STOPPED},
        {**values, "base_record_version": 1},
        {**values, "source_rule": "another-closed-rule-v1"},
        {**values, "reason": "another_reason"},
    )
    assert all(
        build_provider_monitoring_intent_suggestion_id(**item) != identifier
        for item in changed
    )


def test_contract_rejects_identifier_for_different_source_state() -> None:
    payload = _payload()
    payload["resource_id"] = "200"
    with pytest.raises(ValidationError, match="suggestion ID"):
        ProviderMonitoringIntentSuggestionV1.model_validate(payload)


@pytest.mark.parametrize("resource_id", ("0", "01", "-1", "qemu-110"))
def test_contract_rejects_noncanonical_resource_identifiers(
    resource_id: str,
) -> None:
    with pytest.raises(ValidationError):
        observed_running_suggestion(
            resource_id=resource_id, management_fingerprint=FINGERPRINT
        )
