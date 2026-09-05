from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.controlled_dequeue_admission import contract
from app.controlled_dequeue_admission.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    ControlledDequeueAdmissionAuthorityContextV1,
    ControlledDequeueAdmissionCreateV1,
    ControlledDequeueAdmissionValidationInputV1,
    admission_record_fingerprint,
    admission_subject_fingerprint,
    build_admission,
    derive_status,
    evaluate_controlled_dequeue_admission,
    item_identity_fingerprint,
    lineage_fingerprint,
    parse_create_json,
    queue_identity_fingerprint,
)
from app.queue_observation_receipt.contract import (
    build_receipt as build_queue_observation_receipt,
)
from app.queue_observation_receipt.contract import (
    derive_status as derive_queue_observation_status,
)
from app.queue_observation_receipt.test_contract import (
    _input as queue_observation_input,
)

REQUESTED_AT = "2026-08-27T12:00:35Z"


def _facts(tmp_path: Path):
    receipt = build_queue_observation_receipt(queue_observation_input(tmp_path))
    status = derive_queue_observation_status(receipt, evaluated_at=REQUESTED_AT)
    enqueue = receipt.v042_enqueue
    item = enqueue.queue_item
    create = ControlledDequeueAdmissionCreateV1(
        queue_observation_receipt_id=receipt.receipt_id,
        queue_observation_receipt_fingerprint=receipt.receipt_record_fingerprint,
        queue_observation_receipt_status_fingerprint=status.status_fingerprint,
        queue_observation_receipt_valid_until=receipt.valid_until,
        enqueue_id=enqueue.enqueue_id,
        inert_queue_item_id=item.queue_item_id,
        inert_queue_item_fingerprint=item.item_fingerprint,
        inherited_limits_fingerprint=enqueue.inherited_limits.limits_fingerprint,
    )
    return receipt, status, create


def _input(tmp_path: Path, **changes) -> ControlledDequeueAdmissionValidationInputV1:
    receipt, status, create = _facts(tmp_path)
    raw = {
        "operator_id": receipt.operator_id,
        "authority": ControlledDequeueAdmissionAuthorityContextV1(
            authenticated_operator_id=receipt.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": receipt.candidate_record_id,
        "create": create,
        "queue_observation_receipt": receipt,
        "queue_observation_receipt_status": status,
        "idempotency_key": "controlled-dequeue-admission-key-1",
    }
    raw.update(changes)
    return ControlledDequeueAdmissionValidationInputV1.model_validate(raw)


def test_valid_same_owner_lineage_is_deterministic_immutable_and_closed(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = build_admission(validation)
    second = build_admission(validation)
    assert first == second
    assert first.disposition == "controlled_dequeue_admission_recorded"
    assert first.admission_state == "readiness_gated"
    assert first.eligibility == "eligible_for_later_dequeue_consideration"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.controlled_dequeue_admission_recorded
    assert first.queue_identity_fingerprint == queue_identity_fingerprint(
        validation.queue_observation_receipt,
        validation.queue_observation_receipt_status,
    )
    assert first.item_identity_fingerprint == item_identity_fingerprint(
        validation.queue_observation_receipt
    )
    assert first.lineage_fingerprint == lineage_fingerprint(
        validation.queue_observation_receipt,
        validation.queue_observation_receipt_status,
    )
    assert first.subject_fingerprint == admission_subject_fingerprint(first)
    assert first.admission_record_fingerprint == admission_record_fingerprint(first)
    assert not first.dequeue_allowed
    assert not first.dequeue_attempted
    assert not first.dequeued
    assert not first.queue_polling_allowed
    assert not first.queue_claim_allowed
    assert not first.queue_lease_allowed
    assert not first.queue_ack_allowed
    assert not first.worker_contact_allowed
    assert not first.agent_invocation_allowed
    assert not first.process_execution_allowed
    with pytest.raises(ValidationError):
        first.dequeued = True  # type: ignore[misc]


def test_pure_evaluation_records_only_readiness_gated_evidence(tmp_path: Path) -> None:
    evaluation = evaluate_controlled_dequeue_admission(_input(tmp_path))
    assert evaluation.admission_state == "readiness_gated"
    assert evaluation.eligibility == "eligible_for_later_dequeue_consideration"
    assert evaluation.blockers == SUCCESS_BLOCKERS
    assert evaluation.recognized_active_v043_observation_count == 1
    assert evaluation.recognized_exact_v042_inert_queue_item_count == 1
    assert evaluation.controlled_dequeue_admission_build_allowed
    assert evaluation.controlled_dequeue_admission_recorded
    assert not evaluation.dequeue_allowed
    assert not evaluation.dequeued


def test_status_expires_without_implying_dequeue(tmp_path: Path) -> None:
    record = build_admission(_input(tmp_path))
    active = derive_status(record, evaluated_at=record.recorded_at)
    expired = derive_status(record, evaluated_at=record.valid_until)
    assert active.lifecycle == "active"
    assert expired.lifecycle == "expired"
    assert active.admission_state == "readiness_gated"
    assert expired.eligibility == "eligible_for_later_dequeue_consideration"
    assert not active.dequeue_allowed
    assert not expired.dequeued


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
        "controlled-dequeue-admission-create-v1",
        "controlled-dequeue-admission-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(create.model_dump_json()[:-1] + ',"nan":NaN}')
    raw = create.model_dump(mode="python")
    raw["command"] = "sh -c whoami"
    with pytest.raises(ValidationError):
        ControlledDequeueAdmissionCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_identity_linkage_and_fingerprint_mismatch_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_identity"] = "transport:queue"
    with pytest.raises(ValidationError):
        ControlledDequeueAdmissionCreateV1.model_validate(raw["create"])

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inert_queue_item_id"] = "9981517d-b91d-51ef-bbf3-f322a173f7f0"
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.admission_state == "blocked"
    assert blocked.blockers == ("item_identity_mismatch",)
    assert not blocked.controlled_dequeue_admission_recorded

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_observation_receipt_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("observation_receipt_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["queue_observation_receipt_status"]["status_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "c" * 64
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("inherited_limits_mismatch",)


def test_missing_stale_foreign_inactive_and_home_assistant_fail_closed(
    tmp_path: Path,
) -> None:
    blocked = evaluate_controlled_dequeue_admission({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["queue_observation_receipt_status"]["lifecycle"] = "expired"
    raw["queue_observation_receipt_status"]["status_fingerprint"] = (
        contract.v043_status_fingerprint(raw["queue_observation_receipt_status"])
    ).model_dump(mode="python")
    raw["create"]["queue_observation_receipt_status_fingerprint"] = raw[
        "queue_observation_receipt_status"
    ]["status_fingerprint"]
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("v043_observation_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["queue_observation_receipt"]["v042_enqueue_status"]["lifecycle"] = "expired"
    raw["queue_observation_receipt"]["v042_enqueue_status"]["status_fingerprint"] = (
        contract.v042_status_fingerprint(
            raw["queue_observation_receipt"]["v042_enqueue_status"]
        )
    ).model_dump(mode="python")
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("item_identity_mismatch",)

    blocked = evaluate_controlled_dequeue_admission(
        {**_input(tmp_path).model_dump(mode="python"), "home_assistant": True}
    )
    assert blocked.blockers == ("installation_capability_unsupported",)


def test_ambiguous_executable_authority_and_dequeue_implication_are_closed(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["queue_observation_receipt"]["queue_observation"][
        "observation_state"
    ] = "ambiguous"
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("ambiguous_state",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["queue_observation_receipt"]["receipt_evidence"]["payload_present"] = True
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("executable_payload",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["queue_observation_receipt"]["v042_enqueue"]["queue_item"]["payload_bytes"] = 1
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("executable_payload",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["dequeue_allowed"] = True
    with pytest.raises(ValidationError):
        ControlledDequeueAdmissionAuthorityContextV1.model_validate(raw["authority"])

    raw = _input(tmp_path).model_dump(mode="python")
    raw["dequeued"] = True
    blocked = evaluate_controlled_dequeue_admission(raw)
    assert blocked.blockers == ("evidence_not_found",)

    record = build_admission(_input(tmp_path))
    tampered = record.model_dump(mode="python")
    tampered["dequeued"] = True
    with pytest.raises(ValidationError):
        contract.ControlledDequeueAdmissionV1.model_validate(tampered)


def test_contract_has_no_forbidden_imports_calls_or_effect_surfaces() -> None:
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
