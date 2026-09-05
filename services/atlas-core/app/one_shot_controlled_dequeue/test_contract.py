from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.controlled_dequeue_admission.contract import (
    PERMISSION as V044_PERMISSION,
)
from app.controlled_dequeue_admission.contract import (
    ControlledDequeueAdmissionAuthorityContextV1,
    ControlledDequeueAdmissionValidationInputV1,
)
from app.controlled_dequeue_admission.contract import (
    build_admission as build_controlled_dequeue_admission,
)
from app.controlled_dequeue_admission.contract import (
    derive_status as derive_controlled_dequeue_admission_status,
)
from app.controlled_dequeue_admission.test_contract import _facts as v044_facts
from app.one_shot_controlled_dequeue import contract
from app.one_shot_controlled_dequeue.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    OneShotControlledDequeueAuthorityContextV1,
    OneShotControlledDequeueCreateV1,
    OneShotControlledDequeueValidationInputV1,
    build_receipt,
    dequeue_record_fingerprint,
    dequeue_subject_fingerprint,
    evaluate_one_shot_controlled_dequeue,
    item_identity_fingerprint,
    lineage_fingerprint,
    parse_create_json,
    queue_identity_fingerprint,
)

REQUESTED_AT = "2026-08-27T12:00:35Z"


def _admission_facts(tmp_path: Path):
    receipt, status, create = v044_facts(tmp_path)
    validation = ControlledDequeueAdmissionValidationInputV1(
        operator_id=receipt.operator_id,
        authority=ControlledDequeueAdmissionAuthorityContextV1(
            authenticated_operator_id=receipt.operator_id,
            permission=V044_PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        candidate_record_id=receipt.candidate_record_id,
        create=create,
        queue_observation_receipt=receipt,
        queue_observation_receipt_status=status,
        idempotency_key="controlled-dequeue-admission-key-1",
    )
    admission = build_controlled_dequeue_admission(validation)
    admission_status = derive_controlled_dequeue_admission_status(
        admission, evaluated_at=REQUESTED_AT
    )
    return admission, admission_status


def _facts(tmp_path: Path):
    admission, admission_status = _admission_facts(tmp_path)
    receipt = admission.queue_observation_receipt
    receipt_status = admission.queue_observation_receipt_status
    enqueue = receipt.v042_enqueue
    item = enqueue.queue_item
    create = OneShotControlledDequeueCreateV1(
        controlled_dequeue_admission_id=admission.admission_id,
        controlled_dequeue_admission_fingerprint=admission.admission_record_fingerprint,
        controlled_dequeue_admission_status_fingerprint=admission_status.status_fingerprint,
        controlled_dequeue_admission_valid_until=admission.valid_until,
        queue_observation_receipt_id=receipt.receipt_id,
        queue_observation_receipt_fingerprint=receipt.receipt_record_fingerprint,
        queue_observation_receipt_status_fingerprint=receipt_status.status_fingerprint,
        enqueue_id=enqueue.enqueue_id,
        inert_queue_item_id=item.queue_item_id,
        inert_queue_item_fingerprint=item.item_fingerprint,
        queue_identity_fingerprint=queue_identity_fingerprint(admission, admission_status),
        item_identity_fingerprint=item_identity_fingerprint(admission),
        lineage_fingerprint=lineage_fingerprint(admission, admission_status),
        inherited_limits_fingerprint=enqueue.inherited_limits.limits_fingerprint,
    )
    return admission, admission_status, create


def _input(tmp_path: Path, **changes) -> OneShotControlledDequeueValidationInputV1:
    admission, admission_status, create = _facts(tmp_path)
    raw = {
        "operator_id": admission.operator_id,
        "authority": OneShotControlledDequeueAuthorityContextV1(
            authenticated_operator_id=admission.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": admission.candidate_record_id,
        "create": create,
        "controlled_dequeue_admission": admission,
        "controlled_dequeue_admission_status": admission_status,
        "idempotency_key": "one-shot-controlled-dequeue-key-1",
    }
    raw.update(changes)
    return OneShotControlledDequeueValidationInputV1.model_validate(raw)


def test_valid_same_owner_lineage_is_deterministic_immutable_and_closed(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = build_receipt(validation)
    second = build_receipt(validation)
    assert first == second
    assert first.dequeue_state == "one_shot_controlled_dequeue_recorded"
    assert first.outcome == "success"
    assert first.disposition == "exact_inert_item_dequeued"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.one_shot_controlled_dequeue_recorded
    assert first.queue_identity_fingerprint == queue_identity_fingerprint(
        validation.controlled_dequeue_admission,
        validation.controlled_dequeue_admission_status,
    )
    assert first.item_identity_fingerprint == item_identity_fingerprint(
        validation.controlled_dequeue_admission
    )
    assert first.lineage_fingerprint == lineage_fingerprint(
        validation.controlled_dequeue_admission,
        validation.controlled_dequeue_admission_status,
    )
    assert first.subject_fingerprint == dequeue_subject_fingerprint(first)
    assert first.dequeue_record_fingerprint == dequeue_record_fingerprint(first)
    assert not first.queue_polling_allowed
    assert not first.queue_claim_allowed
    assert not first.queue_lease_allowed
    assert not first.queue_ack_allowed
    assert not first.worker_contact_allowed
    assert not first.agent_invocation_allowed
    assert not first.process_execution_allowed
    with pytest.raises(ValidationError):
        first.queue_polled = True  # type: ignore[misc]


def test_pure_evaluation_records_only_readiness_gated_receipt_evidence(
    tmp_path: Path,
) -> None:
    evaluation = evaluate_one_shot_controlled_dequeue(_input(tmp_path))
    assert evaluation.dequeue_state == "readiness_gated"
    assert evaluation.outcome == "success"
    assert evaluation.disposition == "exact_inert_item_dequeued"
    assert evaluation.blockers == SUCCESS_BLOCKERS
    assert evaluation.recognized_active_v044_admission_count == 1
    assert evaluation.recognized_exact_v042_inert_queue_item_count == 1
    assert evaluation.one_shot_controlled_dequeue_build_allowed
    assert evaluation.one_shot_controlled_dequeue_recorded
    assert not evaluation.queue_polling_allowed
    assert not evaluation.worker_start_allowed


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
        "one-shot-controlled-dequeue-create-v1",
        "one-shot-controlled-dequeue-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(create.model_dump_json()[:-1] + ',"nan":NaN}')
    raw = create.model_dump(mode="python")
    raw["command"] = "sh -c whoami"
    with pytest.raises(ValidationError):
        OneShotControlledDequeueCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_stale_foreign_mismatched_and_expired_prerequisites_fail_closed(
    tmp_path: Path,
) -> None:
    blocked = evaluate_one_shot_controlled_dequeue({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_dequeue_admission_status"]["lifecycle"] = "expired"
    raw["controlled_dequeue_admission_status"]["status_fingerprint"] = (
        contract.v044_status_fingerprint(raw["controlled_dequeue_admission_status"])
    ).model_dump(mode="python")
    raw["create"]["controlled_dequeue_admission_status_fingerprint"] = raw[
        "controlled_dequeue_admission_status"
    ]["status_fingerprint"]
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("v044_admission_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["controlled_dequeue_admission_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["item_identity_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("item_identity_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_identity_fingerprint"]["value"] = "d" * 64
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("queue_identity_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "c" * 64
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("inherited_limits_mismatch",)


def test_non_inert_replayed_unsupported_authority_and_home_assistant_fail_closed(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_dequeue_admission"]["queue_observation_receipt"][
        "receipt_evidence"
    ]["payload_present"] = True
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("executable_payload",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["controlled_dequeue_admission"]["queue_observation_receipt"]["v042_enqueue"][
        "queue_item"
    ]["dequeued"] = True
    blocked = evaluate_one_shot_controlled_dequeue(raw)
    assert blocked.blockers == ("executable_payload",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["queue_polling_allowed"] = True
    with pytest.raises(ValidationError):
        OneShotControlledDequeueAuthorityContextV1.model_validate(raw["authority"])

    blocked = evaluate_one_shot_controlled_dequeue(
        {**_input(tmp_path).model_dump(mode="python"), "home_assistant": True}
    )
    assert blocked.blockers == ("installation_capability_unsupported",)

    receipt = build_receipt(_input(tmp_path))
    tampered = receipt.model_dump(mode="python")
    tampered["worker_started"] = True
    with pytest.raises(ValidationError):
        contract.OneShotControlledDequeueReceiptV1.model_validate(tampered)


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
