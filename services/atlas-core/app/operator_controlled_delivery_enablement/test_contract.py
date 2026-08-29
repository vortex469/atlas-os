from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.delivery_activation_preflight.test_contract import OPERATOR, _result
from app.operator_controlled_delivery_enablement.contract import (
    CONFIRMATION,
    OperatorControlledDeliveryEnablementAuditEvidenceV1,
    OperatorControlledDeliveryEnablementConfigurationV1,
    OperatorControlledDeliveryEnablementCreateV1,
    OperatorControlledDeliveryEnablementEvidenceV1,
    OperatorControlledDeliveryEnablementIdempotencyV1,
    OperatorControlledDeliveryEnablementLinkageV1,
    OperatorControlledDeliveryEnablementOperationResultV1,
    OperatorControlledDeliveryEnablementRedactedErrorV1,
    OperatorControlledDeliveryEnablementStatusV1,
    StrictContractError,
    audit_evidence_fingerprint,
    create_delivery_enablement_record,
    enablement_fingerprint,
    enablement_lifecycle,
    parse_create_json,
    validate_enablement_record,
)

ENABLEMENT_ID = "00000000-0000-4000-8000-000000000a01"
ENABLED_AT = "2026-08-27T12:00:13Z"


def _linkage(preflight):
    return OperatorControlledDeliveryEnablementLinkageV1(
        **preflight.linkage.model_dump(mode="python"),
        delivery_preparation_id=preflight.delivery_preparation_id,
        preparation_fingerprint=preflight.preparation_fingerprint,
        preflight_id=preflight.preflight_id,
        preflight_fingerprint=preflight.preflight_fingerprint,
    )


def _evidence(tmp_path: Path, *, owner: str = OPERATOR, at: str = ENABLED_AT):
    preflight = _result(tmp_path)
    return OperatorControlledDeliveryEnablementEvidenceV1(
        operator_id=owner,
        authenticated_operator_id=owner,
        resolved_at=at,
        preflight=preflight,
        linkage=_linkage(preflight),
    )


def _create(evidence):
    return OperatorControlledDeliveryEnablementCreateV1(
        preflight_id=evidence.preflight.preflight_id,
        preflight_fingerprint=evidence.preflight.preflight_fingerprint,
        confirmation=CONFIRMATION,
    )


def _record(tmp_path: Path, *, at: str = ENABLED_AT):
    evidence = _evidence(tmp_path, at=at)
    return create_delivery_enablement_record(
        _create(evidence), evidence=evidence,
        configuration=OperatorControlledDeliveryEnablementConfigurationV1(enabled=True),
        enablement_id=ENABLEMENT_ID, enabled_at=at,
    )


def test_closed_request_duplicate_unknown_and_body_bounds(tmp_path: Path) -> None:
    create = _create(_evidence(tmp_path))
    payload = json.dumps(create.model_dump(mode="json"))
    assert parse_create_json(payload) == create
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"schema":"duplicate"}')
    with pytest.raises(StrictContractError):
        parse_create_json(payload[:-1] + ',"send":true}')
    with pytest.raises(StrictContractError):
        parse_create_json(b" " * 1025)


def test_valid_immutable_record_lifecycle_and_authority(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert record.operator_enabled
    assert record.expires_at == "2026-08-27T12:00:42Z"
    assert enablement_lifecycle(record, now=record.enabled_at) == "enabled"
    assert enablement_lifecycle(record, now=record.expires_at) == "expired"
    false_flags = (
        record.default_enabled, record.agent_contacted, record.credentials_loaded,
        record.production_transport_registered, record.delivery_activated,
        record.delivery_sent, record.delivery_authorized,
        record.execution_admission_granted, record.execution_authorized,
        record.dispatch_allowed, record.worker_allowed, record.workflow_allowed,
        record.installation_allowed, record.deployment_allowed,
        record.mutation_allowed, record.replay_allowed,
    )
    assert not any(false_flags)
    with pytest.raises(ValidationError):
        record.delivery_sent = True  # type: ignore[misc]


def test_fingerprints_owner_linkage_and_confirmation_are_exact(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert record.enablement_fingerprint == enablement_fingerprint(record, operator_id=OPERATOR)
    assert record.enablement_fingerprint != enablement_fingerprint(record, operator_id="operator-b")
    raw = record.model_dump(mode="json")
    del raw["enablement_fingerprint"]
    with pytest.raises(ValidationError):
        type(record).model_validate(raw)
    raw = record.model_dump(mode="json")
    raw["enablement_fingerprint"]["value"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        validate_enablement_record(type(record).model_validate(raw), operator_id=OPERATOR)
    evidence = _evidence(tmp_path)
    changed = evidence.model_dump(mode="json")
    changed["linkage"]["preflight_id"] = "00000000-0000-4000-8000-000000000a99"
    with pytest.raises(ValueError, match="linkage"):
        OperatorControlledDeliveryEnablementEvidenceV1.model_validate(changed)
    changed = evidence.model_dump(mode="json")
    changed["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValueError, match="ownership"):
        OperatorControlledDeliveryEnablementEvidenceV1.model_validate(changed)
    bad = _create(evidence).model_dump(mode="json")
    bad["confirmation"] += " "
    with pytest.raises(ValidationError):
        OperatorControlledDeliveryEnablementCreateV1.model_validate(bad)


def test_default_disabled_stale_and_expired_fail_closed(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    with pytest.raises(ValueError, match="default-disabled"):
        create_delivery_enablement_record(
            _create(evidence), evidence=evidence,
            configuration=OperatorControlledDeliveryEnablementConfigurationV1(),
            enablement_id=ENABLEMENT_ID, enabled_at=ENABLED_AT,
        )
    for at in ("2026-08-27T12:00:42Z", "2026-08-27T12:00:43Z"):
        stale = _evidence(tmp_path, at=at)
        with pytest.raises(ValueError, match="stale|expired"):
            create_delivery_enablement_record(
                _create(stale), evidence=stale,
                configuration=OperatorControlledDeliveryEnablementConfigurationV1(enabled=True),
                enablement_id=ENABLEMENT_ID, enabled_at=at,
            )


def test_idempotency_audit_status_result_and_redaction(tmp_path: Path) -> None:
    record = _record(tmp_path)
    reservation = OperatorControlledDeliveryEnablementIdempotencyV1(
        operator_id=OPERATOR, key="enable-one", preflight_id=record.preflight_id,
        preflight_fingerprint=record.preflight_fingerprint,
        delivery_preparation_id=record.delivery_preparation_id,
        preparation_fingerprint=record.preparation_fingerprint,
        enablement_id=record.enablement_id,
        enablement_fingerprint=record.enablement_fingerprint,
    )
    assert reservation.reservation_permanent and not reservation.expiry_releases_reservation
    status = OperatorControlledDeliveryEnablementStatusV1(
        enablement_id=record.enablement_id,
        enablement_fingerprint=record.enablement_fingerprint,
        observed_at=record.enabled_at, lifecycle="enabled",
    )
    audit_raw = {
        "schema": "operator-controlled-delivery-enablement-audit-evidence-v1",
        "enablement_id": record.enablement_id,
        "enablement_fingerprint": record.enablement_fingerprint.model_dump(mode="json"),
        "preflight_id": record.preflight_id,
        "preflight_fingerprint": record.preflight_fingerprint.model_dump(mode="json"),
        "delivery_preparation_id": record.delivery_preparation_id,
        "preparation_fingerprint": record.preparation_fingerprint.model_dump(mode="json"),
        "enabled_at": record.enabled_at, "expires_at": record.expires_at,
        "lifecycle": "enabled", "status": record.status_at_creation,
        "confirmation": CONFIRMATION,
        "provenance": "core_operator_controlled_delivery_enablement_v1",
        "delivery_activated": False, "delivery_sent": False,
        "delivery_authorized": False, "execution_authorized": False,
        "mutation_allowed": False, "replay_allowed": False,
    }
    audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(audit_raw).model_dump(mode="json")
    audit = OperatorControlledDeliveryEnablementAuditEvidenceV1.model_validate(audit_raw)
    result = OperatorControlledDeliveryEnablementOperationResultV1(
        disposition="created", record=record, status=status,
        audit_evidence=audit, error=None,
    )
    assert not result.delivery_sent
    error = OperatorControlledDeliveryEnablementRedactedErrorV1(
        error_code="unavailable", correlation_id="enablement-1"
    )
    assert error.redacted and set(error.model_dump()) == {
        "schema", "error_code", "correlation_id", "preflight_id",
        "preflight_fingerprint", "redacted",
    }


def test_contract_has_no_forbidden_imports_or_calls() -> None:
    tree = ast.parse(Path(__file__).with_name("contract.py").read_text())
    forbidden = {"httpx", "requests", "socket", "subprocess", "docker", "podman"}
    imports = {alias.name.split(".")[0] for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    calls = {getattr(node.func, "id", "") for node in ast.walk(tree)
             if isinstance(node, ast.Call)}
    assert imports.isdisjoint(forbidden)
    assert calls.isdisjoint({"open", "exec", "eval", "system", "run", "Popen"})
