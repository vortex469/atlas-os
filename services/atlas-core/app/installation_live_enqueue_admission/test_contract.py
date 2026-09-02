from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_live_enqueue_admission import contract
from app.installation_live_enqueue_admission.contract import (
    ADMISSION_BLOCKERS,
    PERMISSION,
    LiveEnqueueAdmissionAuthorityContextV1,
    LiveEnqueueAdmissionCollectionV1,
    LiveEnqueueAdmissionCreateV1,
    LiveEnqueueAdmissionRedactedErrorV1,
    LiveEnqueueAdmissionResultV1,
    LiveEnqueueAdmissionValidationInputV1,
    LiveEnqueueWorkerIntakeEvidenceV1,
    build_admission,
    build_collection,
    build_worker_intake_evidence,
    derived_admission_id,
    derive_status,
    evaluate_live_enqueue_admission,
    fingerprint,
    idempotency_key_fingerprint,
    opaque_fingerprint,
    parse_create_json,
    record_fingerprint,
    v020_v039_chain_fingerprint,
    worker_intake_evidence_fingerprint,
)
from app.worker_intake_admission.contract import (
    build_admission as build_worker_intake_admission,
)
from app.worker_intake_admission.contract import (
    derive_status as derive_worker_intake_status,
)
from app.worker_intake_admission.contract import (
    record_fingerprint as worker_intake_record_fingerprint,
)
from app.worker_intake_admission.contract import (
    status_fingerprint as worker_intake_status_fingerprint,
)
from app.worker_intake_admission.test_contract import ADMISSION_ID as INTAKE_ID
from app.worker_intake_admission.test_contract import DECISION_ID as INTAKE_DECISION_ID
from app.worker_intake_admission.test_contract import REQUESTED_AT
from app.worker_intake_admission.test_contract import _input as worker_intake_input
from app.worker_queue_reservation.contract import (
    status_fingerprint as queue_reservation_status_fingerprint,
)


def _facts(tmp_path: Path):
    intake_validation = worker_intake_input(tmp_path)
    intake_record, _, _ = build_worker_intake_admission(
        intake_validation,
        admission_id=INTAKE_ID,
        decision_id=INTAKE_DECISION_ID,
    )
    intake_status = derive_worker_intake_status(
        intake_record, evaluated_at=REQUESTED_AT
    )
    link = intake_record.linkage
    create = LiveEnqueueAdmissionCreateV1(
        worker_intake_admission_id=intake_record.admission_id,
        worker_intake_admission_fingerprint=intake_record.record_fingerprint,
        worker_intake_admission_valid_until=intake_record.valid_until,
        worker_queue_reservation_id=link.queue_reservation_id,
        worker_queue_reservation_fingerprint=link.queue_reservation_fingerprint,
        queue_item_reference_id=link.queue_item_reference_id,
        queue_item_reference_fingerprint=link.queue_item_reference_fingerprint,
        worker_identity_id=link.worker_identity_id,
        worker_identity_fingerprint=link.worker_identity_fingerprint,
        worker_intake_reference_id=link.worker_intake_reference_id,
        worker_intake_reference_fingerprint=link.worker_intake_reference_fingerprint,
        inherited_limits_fingerprint=intake_record.inherited_limits.limits_fingerprint,
    )
    return (
        intake_record,
        intake_status,
        intake_validation.worker_queue_reservation,
        intake_validation.worker_queue_reservation_status,
        create,
    )


def _input(tmp_path: Path, **changes) -> LiveEnqueueAdmissionValidationInputV1:
    intake_record, intake_status, queue_reservation, queue_status, create = _facts(
        tmp_path
    )
    raw = {
        "operator_id": intake_record.operator_id,
        "authority": LiveEnqueueAdmissionAuthorityContextV1(
            authenticated_operator_id=intake_record.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": intake_record.candidate_record_id,
        "create": create,
        "worker_intake_admission": intake_record,
        "worker_intake_admission_status": intake_status,
        "worker_queue_reservation": queue_reservation,
        "worker_queue_reservation_status": queue_status,
        "idempotency_key": "live-enqueue-admission-key-1",
    }
    raw.update(changes)
    return LiveEnqueueAdmissionValidationInputV1.model_validate(raw)


def test_valid_canonical_golden_produces_only_live_enqueue_admission_recorded(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_live_enqueue_admission(validation)
    second = evaluate_live_enqueue_admission(validation)
    assert first == second
    assert first.eligibility == "live_enqueue_admission_recorded"
    assert first.blockers == ADMISSION_BLOCKERS
    assert first.admission_record_build_allowed
    assert first.recognized_active_v040_worker_intake_count == 1
    assert first.recognized_active_v040_worker_intake_as_inert_evidence
    assert first.worker_intake_evidence is not None
    assert not first.live_enqueue_allowed
    assert not first.payload_constructed
    assert not first.queue_send_allowed
    assert not first.worker_contact_allowed
    assert not first.execution_start_allowed


def test_models_are_deterministic_immutable_and_derive_uuid5_identifiers(
    tmp_path: Path,
) -> None:
    first = build_admission(_input(tmp_path))
    second = build_admission(_input(tmp_path))
    assert first == second
    record, idempotency, permanent = first
    assert record.record_fingerprint == record_fingerprint(record)
    assert record.admission_id == derived_admission_id(record.subject_fingerprint)
    assert record.admission_id.split("-")[2].startswith("5")
    assert record.admission_decision.decision_id.split("-")[2].startswith("5")
    assert idempotency.permanent and permanent.permanent
    with pytest.raises(ValidationError):
        record.record_state = "enqueued"  # type: ignore[misc]


def test_parse_create_rejects_duplicate_keys_utf8_nfc_non_finite_unknown_and_bounds(
    tmp_path: Path,
) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"\xff")
    non_nfc = create.model_dump_json().replace(
        "live-enqueue-admission-create-v1",
        "live-enqueue-admission-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(create.model_dump_json()[:-1] + ',"nan":NaN}')
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        LiveEnqueueAdmissionCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_active_v040_recognition_and_nested_link_substitution_fail_closed(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    evidence = build_worker_intake_evidence(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        admission=validation.worker_intake_admission,
        status=validation.worker_intake_admission_status,
        queue_reservation=validation.worker_queue_reservation,
        queue_reservation_status=validation.worker_queue_reservation_status,
    )
    assert evidence.evidence_fingerprint == worker_intake_evidence_fingerprint(evidence)

    raw = evidence.model_dump(mode="python")
    raw["worker_intake_statuses"][0]["lifecycle"] = "expired"
    raw["worker_intake_statuses"][0]["status_fingerprint"] = (
        worker_intake_status_fingerprint(raw["worker_intake_statuses"][0])
    )
    with pytest.raises(ValidationError, match="active inert"):
        LiveEnqueueWorkerIntakeEvidenceV1.model_validate(raw)

    raw = evidence.model_dump(mode="python")
    raw["queue_reservation_statuses"][0]["lifecycle"] = "expired"
    raw["queue_reservation_statuses"][0]["status_fingerprint"] = (
        queue_reservation_status_fingerprint(raw["queue_reservation_statuses"][0])
    ).model_dump(mode="python")
    with pytest.raises(ValidationError, match="active inert"):
        LiveEnqueueWorkerIntakeEvidenceV1.model_validate(raw)

    raw = validation.model_dump(mode="python")
    raw["worker_intake_admission"]["linkage"]["queue_item_reference_fingerprint"] = (
        opaque_fingerprint("atlas:test:substituted-queue-item:v1", "item")
    ).model_dump(mode="python")
    raw["worker_intake_admission"]["linkage"]["linkage_fingerprint"] = (
        fingerprint(
            "atlas:worker-intake-admission-linkage:v1",
            {
                key: value
                for key, value in raw["worker_intake_admission"]["linkage"].items()
                if key != "linkage_fingerprint"
            },
        )
    ).model_dump(mode="python")
    blocked = evaluate_live_enqueue_admission(raw)
    assert blocked.eligibility == "blocked"
    assert blocked.blockers == ("linkage_mismatch",)
    assert blocked.worker_intake_evidence is None


def test_worker_intake_worker_identity_queue_reference_and_limits_are_exact(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["worker_intake_admission_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="worker intake admission binding"):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["worker_identity_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="linkage"):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["worker_intake_reference_fingerprint"]["value"] = "c" * 64
    with pytest.raises(ValidationError, match="linkage"):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_item_reference_fingerprint"]["value"] = "d" * 64
    with pytest.raises(ValidationError, match="linkage"):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "e" * 64
    with pytest.raises(ValidationError, match="linkage|limits"):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)


def test_stale_expired_foreign_corrupt_home_assistant_and_unknown_vocabulary(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_intake_admission_status"]["lifecycle"] = "expired"
    raw["worker_intake_admission_status"]["status_fingerprint"] = (
        worker_intake_status_fingerprint(raw["worker_intake_admission_status"])
    ).model_dump(mode="python")
    blocked = evaluate_live_enqueue_admission(raw)
    assert blocked.blockers == ("worker_intake_admission_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_live_enqueue_admission(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    del raw["worker_intake_admission"]
    blocked = evaluate_live_enqueue_admission(raw)
    assert blocked.blockers == ("evidence_not_found",)
    assert not blocked.admission_record_build_allowed

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "not a valid operator"
    raw["candidate_record_id"] = "not-a-uuid"
    blocked = evaluate_live_enqueue_admission(raw)
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    assert blocked.candidate_record_id == "00000000-0000-4000-8000-000000000000"

    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    with pytest.raises(ValidationError):
        LiveEnqueueAdmissionValidationInputV1.model_validate(raw)

    blocked = evaluate_live_enqueue_admission(
        {**_input(tmp_path).model_dump(mode="python"), "home_assistant": True}
    )
    assert blocked.eligibility == "blocked"
    assert blocked.blockers == ("installation_capability_unsupported",)
    assert not blocked.admission_record_build_allowed
    assert blocked.worker_intake_evidence is None


def test_fingerprint_domain_confusion_contrary_authority_result_and_collection(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    record, _, _ = build_admission(validation)
    confused = record.model_dump(mode="python")
    confused["record_fingerprint"] = worker_intake_record_fingerprint(
        validation.worker_intake_admission
    ).model_dump(mode="python")
    with pytest.raises(ValidationError, match="record fingerprint"):
        contract.LiveEnqueueAdmissionV1.model_validate(confused)

    contrary = validation.create.model_dump(mode="python")
    contrary["live_enqueue_allowed"] = True
    with pytest.raises(ValidationError):
        LiveEnqueueAdmissionCreateV1.model_validate(contrary)

    status = derive_status(record, evaluated_at=record.recorded_at)
    error = LiveEnqueueAdmissionRedactedErrorV1(
        error_code="not_found",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:live-enqueue-correlation:v1", "blocked"
        ),
    )
    result = LiveEnqueueAdmissionResultV1(
        ok=False,
        admission=None,
        status=None,
        error=error,
        correlation_fingerprint=error.correlation_fingerprint,
    )
    assert result.error.message == contract.SAFE_MESSAGE
    assert result.error.redacted and not result.live_enqueue_allowed
    assert not result.payload_constructed
    assert status.lifecycle == "active"
    collection = build_collection(
        operator_id=record.operator_id,
        candidate_record_id=record.candidate_record_id,
        items=(record,),
    )
    assert collection.count == 1 and collection.items == (record,)
    with pytest.raises(ValidationError, match="collection"):
        LiveEnqueueAdmissionCollectionV1(
            operator_id=record.operator_id,
            candidate_record_id=record.candidate_record_id,
            items=(),
            count=101,
            collection_fingerprint=record.record_fingerprint,
        )


def test_v020_v040_linkage_reconstruction_is_exact(tmp_path: Path) -> None:
    validation = _input(tmp_path)
    record, _, _ = build_admission(validation)
    assert record.linkage.v020_v039_chain_fingerprint == v020_v039_chain_fingerprint(
        validation.worker_intake_admission.linkage
    )
    raw = record.model_dump(mode="python")
    raw["linkage"]["worker_intake_admission_status_fingerprint"]["value"] = "f" * 64
    with pytest.raises(ValidationError, match="linkage fingerprint|fingerprint"):
        contract.LiveEnqueueAdmissionV1.model_validate(raw)


def test_contract_has_no_forbidden_imports_calls_or_consumers() -> None:
    path = Path(contract.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = (
        "atlas_execution_worker",
        "agent",
        "dispatch",
        "docker",
        "provider",
        "repository",
        "requests",
        "socket",
        "subprocess",
        "workflow",
        "transport",
        "deployment",
        "rollback",
    )
    assert not [name for name in imports if any(term in name for term in forbidden)]
    source = path.read_text(encoding="utf-8").lower()
    for call in (
        "subprocess.",
        "os.system",
        "create_subprocess",
        ".enqueue(",
        ".dequeue(",
        ".publish(",
        ".send(",
        ".poll(",
        ".claim(",
        ".lease(",
        ".consume(",
        ".acknowledge(",
        ".delete(",
        ".dispatch(",
        ".start_worker(",
        ".execute(",
        ".invoke_agent(",
    ):
        assert call not in source


def test_idempotency_fingerprint_rejects_invalid_identifier(tmp_path: Path) -> None:
    operator_id = _input(tmp_path).operator_id
    with pytest.raises(ValueError, match="idempotency"):
        idempotency_key_fingerprint(operator_id, "short")
