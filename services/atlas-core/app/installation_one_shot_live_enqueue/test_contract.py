from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_live_enqueue_admission.contract import (
    build_admission as build_live_enqueue_admission,
)
from app.installation_live_enqueue_admission.contract import (
    derive_status as derive_live_enqueue_status,
)
from app.installation_live_enqueue_admission.test_contract import (
    _input as live_enqueue_input,
)
from app.installation_one_shot_live_enqueue import contract
from app.installation_one_shot_live_enqueue.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    OneShotLiveEnqueueAuthorityContextV1,
    OneShotLiveEnqueueCollectionV1,
    OneShotLiveEnqueueCreateV1,
    OneShotLiveEnqueueRedactedErrorV1,
    OneShotLiveEnqueueResultV1,
    OneShotLiveEnqueueValidationInputV1,
    build_collection,
    build_enqueue,
    derive_status,
    evaluate_one_shot_live_enqueue,
    idempotency_key_fingerprint,
    item_fingerprint,
    opaque_fingerprint,
    parse_create_json,
    record_fingerprint,
    v020_v041_chain_fingerprint,
)
from app.worker_intake_admission.contract import (
    status_fingerprint as worker_intake_status_fingerprint,
)
from app.worker_queue_reservation.contract import (
    status_fingerprint as queue_reservation_status_fingerprint,
)

REQUESTED_AT = "2026-08-27T12:00:34Z"


def _facts(tmp_path: Path):
    live_validation = live_enqueue_input(tmp_path)
    live_record, _, _ = build_live_enqueue_admission(live_validation)
    live_status = derive_live_enqueue_status(live_record, evaluated_at=REQUESTED_AT)
    link = live_record.linkage
    create = OneShotLiveEnqueueCreateV1(
        live_enqueue_admission_id=live_record.admission_id,
        live_enqueue_admission_fingerprint=live_record.record_fingerprint,
        live_enqueue_admission_status_fingerprint=live_status.status_fingerprint,
        live_enqueue_admission_valid_until=live_record.valid_until,
        worker_intake_admission_id=link.worker_intake_admission_id,
        worker_intake_admission_fingerprint=link.worker_intake_admission_fingerprint,
        worker_queue_reservation_id=link.queue_reservation_id,
        worker_queue_reservation_fingerprint=link.queue_reservation_fingerprint,
        worker_identity_id=link.worker_identity_id,
        worker_identity_fingerprint=link.worker_identity_fingerprint,
        worker_intake_reference_id=link.worker_intake_reference_id,
        worker_intake_reference_fingerprint=link.worker_intake_reference_fingerprint,
        queue_intake_reference_id=link.queue_intake_reference_id,
        queue_intake_reference_fingerprint=link.queue_intake_reference_fingerprint,
        queue_item_reference_id=link.queue_item_reference_id,
        queue_item_reference_fingerprint=link.queue_item_reference_fingerprint,
        inherited_limits_fingerprint=link.inherited_limits_fingerprint,
    )
    return (
        live_record,
        live_status,
        live_validation.worker_intake_admission,
        live_validation.worker_intake_admission_status,
        live_validation.worker_queue_reservation,
        live_validation.worker_queue_reservation_status,
        create,
    )


def _input(tmp_path: Path, **changes) -> OneShotLiveEnqueueValidationInputV1:
    (
        live_record,
        live_status,
        intake,
        intake_status,
        queue,
        queue_status,
        create,
    ) = _facts(tmp_path)
    raw = {
        "operator_id": live_record.operator_id,
        "authority": OneShotLiveEnqueueAuthorityContextV1(
            authenticated_operator_id=live_record.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": live_record.candidate_record_id,
        "create": create,
        "live_enqueue_admission": live_record,
        "live_enqueue_admission_status": live_status,
        "worker_intake_admission": intake,
        "worker_intake_admission_status": intake_status,
        "worker_queue_reservation": queue,
        "worker_queue_reservation_status": queue_status,
        "idempotency_key": "one-shot-live-enqueue-key-1",
    }
    raw.update(changes)
    return OneShotLiveEnqueueValidationInputV1.model_validate(raw)


def test_valid_canonical_golden_records_only_inert_reference_item(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_one_shot_live_enqueue(validation)
    second = evaluate_one_shot_live_enqueue(validation)
    assert first == second
    assert first.outcome == "one_shot_live_enqueue_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.queue_item_record_build_allowed
    assert first.recognized_active_v041_live_enqueue_count == 1
    assert first.recognized_active_v041_live_enqueue_as_inert_evidence
    assert first.one_shot_live_enqueue_recorded
    assert first.reference_only
    assert not first.dequeue_allowed
    assert not first.queue_polling_allowed
    assert not first.worker_contact_allowed
    assert not first.process_execution_allowed


def test_models_are_deterministic_immutable_and_fingerprint_exact(
    tmp_path: Path,
) -> None:
    first = build_enqueue(_input(tmp_path))
    second = build_enqueue(_input(tmp_path))
    assert first == second
    record, idempotency, permanent = first
    assert record.record_fingerprint == record_fingerprint(record)
    assert record.queue_item.item_fingerprint == item_fingerprint(record.queue_item)
    assert record.enqueue_id == contract.derived_queue_item_id(
        record.item_subject_fingerprint
    )
    assert record.enqueue_id.split("-")[2].startswith("5")
    assert idempotency.permanent and permanent.permanent
    assert record.one_shot_live_enqueue_recorded
    assert not record.worker_start_allowed
    with pytest.raises(ValidationError):
        record.record_state = "dequeued"  # type: ignore[misc]


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
        "one-shot-live-enqueue-create-v1",
        "one-shot-live-enqueue-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(create.model_dump_json()[:-1] + ',"nan":NaN}')
    raw = create.model_dump(mode="python")
    raw["command"] = "sh -c whoami"
    with pytest.raises(ValidationError):
        OneShotLiveEnqueueCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_v041_lineage_reference_and_fingerprint_mismatch_fail_closed(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    record, _, _ = build_enqueue(validation)
    assert record.lineage.v020_v041_chain_fingerprint == v020_v041_chain_fingerprint(
        validation.live_enqueue_admission,
        validation.live_enqueue_admission_status,
    )

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["live_enqueue_admission_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="live enqueue admission binding"):
        OneShotLiveEnqueueValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_intake_reference_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_one_shot_live_enqueue(raw)
    assert blocked.outcome == "blocked"
    assert blocked.blockers == ("linkage_mismatch",)
    assert not blocked.queue_item_record_build_allowed

    raw_record = record.model_dump(mode="python")
    raw_record["lineage"]["worker_identity_fingerprint"]["value"] = "c" * 64
    with pytest.raises(ValidationError, match="lineage|fingerprint"):
        contract.OneShotLiveEnqueueV1.model_validate(raw_record)


def test_stale_expired_inactive_foreign_malformed_and_home_assistant_fail_closed(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        OneShotLiveEnqueueValidationInputV1.model_validate(raw)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["live_enqueue_admission_status"]["lifecycle"] = "expired"
    raw["live_enqueue_admission_status"]["status_fingerprint"] = (
        contract.v041_status_fingerprint(raw["live_enqueue_admission_status"])
    ).model_dump(mode="python")
    blocked = evaluate_one_shot_live_enqueue(raw)
    assert blocked.blockers == ("live_enqueue_admission_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_intake_admission_status"]["lifecycle"] = "expired"
    raw["worker_intake_admission_status"]["status_fingerprint"] = (
        worker_intake_status_fingerprint(raw["worker_intake_admission_status"])
    ).model_dump(mode="python")
    blocked = evaluate_one_shot_live_enqueue(raw)
    assert blocked.blockers == ("worker_intake_admission_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_queue_reservation_status"]["lifecycle"] = "expired"
    raw["worker_queue_reservation_status"]["status_fingerprint"] = (
        queue_reservation_status_fingerprint(raw["worker_queue_reservation_status"])
    ).model_dump(mode="python")
    blocked = evaluate_one_shot_live_enqueue(raw)
    assert blocked.blockers == ("queue_reservation_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_one_shot_live_enqueue(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "not a valid operator"
    raw["candidate_record_id"] = "not-a-uuid"
    blocked = evaluate_one_shot_live_enqueue(raw)
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    assert blocked.candidate_record_id == "00000000-0000-4000-8000-000000000000"

    blocked = evaluate_one_shot_live_enqueue(
        {**_input(tmp_path).model_dump(mode="python"), "home_assistant": True}
    )
    assert blocked.blockers == ("installation_capability_unsupported",)
    assert not blocked.one_shot_live_enqueue_recorded


def test_contrary_authority_result_error_and_collection_are_closed(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    record, _, _ = build_enqueue(validation)
    contrary = validation.create.model_dump(mode="python")
    contrary["process_execution_allowed"] = True
    with pytest.raises(ValidationError):
        OneShotLiveEnqueueCreateV1.model_validate(contrary)

    status = derive_status(record, evaluated_at=record.recorded_at)
    error = OneShotLiveEnqueueRedactedErrorV1(
        error_code="not_found",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:one-shot-correlation:v1", "blocked"
        ),
    )
    result = OneShotLiveEnqueueResultV1(
        ok=False,
        outcome="failure",
        record=None,
        status=None,
        error=error,
        correlation_fingerprint=error.correlation_fingerprint,
    )
    assert result.error.message == contract.SAFE_MESSAGE
    assert result.error.redacted and not result.retry_allowed
    assert not result.one_shot_live_enqueue_recorded
    assert status.lifecycle == "active"
    collection = build_collection(
        operator_id=record.operator_id,
        candidate_record_id=record.candidate_record_id,
        items=(record,),
    )
    assert collection.count == 1 and collection.items == (record,)
    with pytest.raises(ValidationError, match="collection"):
        OneShotLiveEnqueueCollectionV1(
            operator_id=record.operator_id,
            candidate_record_id=record.candidate_record_id,
            items=(),
            count=101,
            collection_fingerprint=record.record_fingerprint,
        )


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
