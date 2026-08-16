from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.provider_intents import (
    ProviderIntentKind,
    ProviderIntentLifecycle,
    ProviderIntentMutationCommand,
    ProviderIntentMutationRequest,
    ProviderIntentProvenance,
    ProviderIntentRecord,
    ProviderIntentValue,
    build_provider_intent_id,
    build_provider_intent_request_digest,
)

FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64


def record_values(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "provider_id": "proxmox",
        "resource_type": "qemu",
        "resource_id": "110",
        "incarnation_fingerprint": FINGERPRINT_A,
        "intent_kind": ProviderIntentKind.MONITORING_EXPECTATION,
        "intent_value": ProviderIntentValue.RUNNING,
        "lifecycle": ProviderIntentLifecycle.ACTIVE,
        "provenance": ProviderIntentProvenance.OPERATOR,
        "record_version": 1,
        "created_at": datetime(2026, 8, 15, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 15, tzinfo=UTC),
    }
    values.update(updates)
    values.setdefault(
        "intent_id",
        build_provider_intent_id(
            provider_id=str(values["provider_id"]),
            resource_type=values["resource_type"],  # type: ignore[arg-type]
            resource_id=str(values["resource_id"]),
            incarnation_fingerprint=values["incarnation_fingerprint"],  # type: ignore[arg-type]
            intent_kind=values["intent_kind"],  # type: ignore[arg-type]
        ),
    )
    return values


def test_record_is_strict_frozen_extra_forbid_and_closed() -> None:
    record = ProviderIntentRecord(**record_values())
    with pytest.raises(ValidationError, match="frozen"):
        record.intent_value = ProviderIntentValue.STOPPED  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProviderIntentRecord.model_validate(
            {**record.model_dump(), "vmgenid": "native-secret"}
        )
    with pytest.raises(ValidationError):
        ProviderIntentRecord.model_validate(
            {**record.model_dump(), "intent_value": "paused"}
        )
    with pytest.raises(ValidationError):
        ProviderIntentRecord.model_validate(
            {**record.model_dump(), "schema_version": 2}
        )


def test_timestamps_are_aware_canonical_and_ordered() -> None:
    local = timezone(timedelta(hours=3))
    record = ProviderIntentRecord(
        **record_values(
            created_at=datetime(2026, 8, 15, 3, tzinfo=local),
            updated_at=datetime(2026, 8, 15, 4, tzinfo=local),
        )
    )
    assert record.created_at == datetime(2026, 8, 15, tzinfo=UTC)
    assert record.updated_at == datetime(2026, 8, 15, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="timezone-aware"):
        ProviderIntentRecord(
            **record_values(
                created_at=datetime(2026, 8, 15, tzinfo=None)  # noqa: DTZ001
            )
        )
    with pytest.raises(ValidationError, match="precedes"):
        ProviderIntentRecord(
            **record_values(
                updated_at=datetime(2026, 8, 14, tzinfo=UTC)
            )
        )


@pytest.mark.parametrize(
    "lifecycle",
    (ProviderIntentLifecycle.ACTIVE, ProviderIntentLifecycle.SUPERSEDED),
)
def test_identity_bound_lifecycle_requires_fingerprint(
    lifecycle: ProviderIntentLifecycle,
) -> None:
    with pytest.raises(ValidationError, match="requires resource type"):
        ProviderIntentRecord(
            **record_values(
                lifecycle=lifecycle,
                incarnation_fingerprint=None,
            )
        )


def test_legacy_unbound_preserves_ambiguous_resource_type() -> None:
    values = record_values(
        resource_type=None,
        incarnation_fingerprint=None,
        lifecycle=ProviderIntentLifecycle.LEGACY_UNBOUND,
        provenance=ProviderIntentProvenance.LEGACY_POLICY_IMPORT,
        source_reference="policies-v1:" + "a" * 64,
    )
    values["intent_id"] = build_provider_intent_id(
        provider_id="proxmox",
        resource_type=None,
        resource_id="110",
        incarnation_fingerprint=None,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
    )
    record = ProviderIntentRecord(**values)
    assert record.resource_type is None
    assert record.incarnation_fingerprint is None
    with pytest.raises(ValidationError, match="cannot claim"):
        ProviderIntentRecord(
            **{
                **values,
                "resource_type": "qemu",
            }
        )


@pytest.mark.parametrize(
    ("provider_id", "resource_type"),
    (("proxmox", "lxc"), ("proxmox", "unknown"), ("docker", "qemu")),
)
def test_unsupported_identity_bound_resource_fails_closed(
    provider_id: str,
    resource_type: str,
) -> None:
    values = record_values(provider_id=provider_id, resource_type=resource_type)
    values["intent_id"] = build_provider_intent_id(
        provider_id=provider_id,
        resource_type=resource_type,
        resource_id="110",
        incarnation_fingerprint=FINGERPRINT_A,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
    )
    with pytest.raises(ValidationError):
        ProviderIntentRecord(**values)


def test_series_identity_excludes_value_and_version_but_binds_incarnation() -> None:
    base = ProviderIntentRecord(**record_values())
    changed_value = ProviderIntentRecord(
        **record_values(intent_value=ProviderIntentValue.STOPPED)
    )
    version_two = ProviderIntentRecord(
        **record_values(
            record_version=2,
            previous_record_version=1,
            intent_value=ProviderIntentValue.IGNORED,
        )
    )
    replacement_values = record_values(incarnation_fingerprint=FINGERPRINT_B)
    replacement_values["intent_id"] = build_provider_intent_id(
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=FINGERPRINT_B,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
    )
    replacement = ProviderIntentRecord(**replacement_values)

    assert base.intent_id == changed_value.intent_id == version_two.intent_id
    assert replacement.intent_id != base.intent_id


def test_mutation_command_is_strict_and_digest_bound() -> None:
    request_id = "intent-request-1"
    digest = build_provider_intent_request_digest(
        request_id=request_id,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=FINGERPRINT_A,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=ProviderIntentValue.RUNNING,
        expected_record_version=0,
    )
    command = ProviderIntentMutationCommand(
        request_id=request_id,
        request_digest=digest,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=FINGERPRINT_A,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=ProviderIntentValue.RUNNING,
        expected_record_version=0,
    )
    assert command.intent_id == ProviderIntentRecord(**record_values()).intent_id
    with pytest.raises(ValidationError, match="digest"):
        ProviderIntentMutationCommand.model_validate(
            {
                **command.model_dump(),
                "request_digest": "provider-intent-request-v1:" + "0" * 64,
            }
        )


@pytest.mark.parametrize(
    ("field", "changed_value"),
    (
        ("request_id", "intent-request-2"),
        ("resource_id", "111"),
        ("incarnation_fingerprint", FINGERPRINT_B),
        ("desired_value", ProviderIntentValue.STOPPED),
        ("expected_record_version", 1),
    ),
)
def test_request_digest_covers_every_variable_mutation_input(
    field: str,
    changed_value: object,
) -> None:
    request = ProviderIntentMutationCommand(
        request_id="intent-request-1",
        request_digest=build_provider_intent_request_digest(
            request_id="intent-request-1",
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            incarnation_fingerprint=FINGERPRINT_A,
            intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
            desired_value=ProviderIntentValue.RUNNING,
            expected_record_version=0,
        ),
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=FINGERPRINT_A,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=ProviderIntentValue.RUNNING,
        expected_record_version=0,
    )
    with pytest.raises(ValidationError, match="digest"):
        ProviderIntentMutationCommand.model_validate(
            {**request.model_dump(), field: changed_value}
        )


@pytest.mark.parametrize(
    "fingerprint",
    (
        "vmgenid",
        "proxmox-qemu-identity-v1:" + "a" * 64,
        "provider-management-fingerprint-v1:" + "A" * 64,
        "provider-management-fingerprint-v1:" + "a" * 63,
        "unrelated-fingerprint-v1:" + "a" * 64,
    ),
)
def test_noncanonical_management_fingerprints_are_rejected(
    fingerprint: str,
) -> None:
    with pytest.raises(ValidationError):
        ProviderIntentMutationCommand(
            request_id="intent-request-1",
            request_digest="provider-intent-request-v1:" + "0" * 64,
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            incarnation_fingerprint=fingerprint,
            intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
            desired_value=ProviderIntentValue.RUNNING,
            expected_record_version=0,
        )


def test_http_mutation_request_is_strict_and_acknowledgement_bound() -> None:
    values = {
        "request_id": "provider-intent-mutation-" + "a" * 32,
        "expected_management_fingerprint": FINGERPRINT_A,
        "expectation": ProviderIntentValue.RUNNING,
        "expected_record_version": 0,
        "acknowledge_monitoring_suppression": False,
    }
    ProviderIntentMutationRequest.model_validate(values)
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProviderIntentMutationRequest.model_validate(
            {**values, "operator_id": "forged"}
        )
    with pytest.raises(ValidationError, match="acknowledgement"):
        ProviderIntentMutationRequest.model_validate(
            {**values, "expectation": ProviderIntentValue.IGNORED}
        )
    with pytest.raises(ValidationError, match="acknowledgement"):
        ProviderIntentMutationRequest.model_validate(
            {**values, "acknowledge_monitoring_suppression": True}
        )
