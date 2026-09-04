from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_one_shot_live_enqueue.contract import (
    build_enqueue as build_one_shot_enqueue,
)
from app.installation_one_shot_live_enqueue.contract import (
    derive_status as derive_one_shot_status,
)
from app.installation_one_shot_live_enqueue.test_contract import (
    _input as one_shot_input,
)
from app.queue_observation_receipt import contract
from app.queue_observation_receipt.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    QueueObservationReceiptAuthorityContextV1,
    QueueObservationReceiptCreateV1,
    QueueObservationReceiptValidationInputV1,
    build_receipt,
    evaluate_queue_observation_receipt,
    observation_fingerprint,
    parse_create_json,
    receipt_fingerprint,
    receipt_record_fingerprint,
)

REQUESTED_AT = "2026-08-27T12:00:34Z"


def _facts(tmp_path: Path):
    enqueue, _, _ = build_one_shot_enqueue(one_shot_input(tmp_path))
    status = derive_one_shot_status(enqueue, evaluated_at=REQUESTED_AT)
    item = enqueue.queue_item
    create = QueueObservationReceiptCreateV1(
        enqueue_id=enqueue.enqueue_id,
        enqueue_record_fingerprint=enqueue.record_fingerprint,
        enqueue_status_fingerprint=status.status_fingerprint,
        enqueue_valid_until=enqueue.valid_until,
        queue_intake_reference_id=item.queue_intake_reference_id,
        queue_intake_reference_fingerprint=item.queue_intake_reference_fingerprint,
        queue_item_reference_id=item.queue_item_reference_id,
        queue_item_reference_fingerprint=item.queue_item_reference_fingerprint,
        inert_queue_item_id=item.queue_item_id,
        inert_queue_item_fingerprint=item.item_fingerprint,
    )
    return enqueue, status, create


def _input(tmp_path: Path, **changes) -> QueueObservationReceiptValidationInputV1:
    enqueue, status, create = _facts(tmp_path)
    raw = {
        "operator_id": enqueue.operator_id,
        "authority": QueueObservationReceiptAuthorityContextV1(
            authenticated_operator_id=enqueue.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": enqueue.candidate_record_id,
        "create": create,
        "v042_enqueue": enqueue,
        "v042_enqueue_status": status,
        "idempotency_key": "queue-observation-receipt-key-1",
    }
    raw.update(changes)
    return QueueObservationReceiptValidationInputV1.model_validate(raw)


def test_valid_receipt_observation_is_deterministic_immutable_and_closed(
    tmp_path: Path,
) -> None:
    first = build_receipt(_input(tmp_path))
    second = build_receipt(_input(tmp_path))
    assert first == second
    assert first.disposition == "observation_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.receipt_evidence.receipt_disposition == "contract_eligible"
    assert first.queue_observation.observation_state == "observed_recorded_not_consumable"
    assert first.receipt_evidence.receipt_fingerprint == receipt_fingerprint(
        first.receipt_evidence
    )
    assert first.queue_observation.observation_fingerprint == observation_fingerprint(
        first.queue_observation
    )
    assert first.receipt_record_fingerprint == receipt_record_fingerprint(first)
    assert not first.dequeue_allowed
    assert not first.queue_polling_allowed
    assert not first.worker_contact_allowed
    assert not first.process_execution_allowed
    with pytest.raises(ValidationError):
        first.disposition = "dequeued"  # type: ignore[misc]


def test_evaluation_records_one_exact_contract_eligible_v042_attempt(
    tmp_path: Path,
) -> None:
    evaluation = evaluate_queue_observation_receipt(_input(tmp_path))
    assert evaluation.disposition == "observation_recorded"
    assert evaluation.recognized_exact_v042_enqueue_count == 1
    assert evaluation.recognized_contract_eligible_enqueue
    assert evaluation.receipt_build_allowed
    assert evaluation.blockers == SUCCESS_BLOCKERS


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
        "queue-observation-receipt-create-v1",
        "queue-observation-receipt-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(create.model_dump_json()[:-1] + ',"nan":NaN}')
    raw = create.model_dump(mode="python")
    raw["command"] = "sh -c whoami"
    with pytest.raises(ValidationError):
        QueueObservationReceiptCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_mismatched_queue_item_identity_and_fingerprints_fail_closed(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_intake_reference_id"] = "34cf9da2-402e-4b24-95e2-10fd933853be"
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.disposition == "blocked"
    assert blocked.blockers == ("queue_identity_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inert_queue_item_id"] = "9981517d-b91d-51ef-bbf3-f322a173f7f0"
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("item_identity_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["enqueue_record_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)


def test_invalid_stale_foreign_and_unsupported_v042_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["v042_enqueue_status"]["lifecycle"] = "expired"
    raw["v042_enqueue_status"]["status_fingerprint"] = (
        contract.v042_status_fingerprint(raw["v042_enqueue_status"])
    ).model_dump(mode="python")
    raw["create"]["enqueue_status_fingerprint"] = raw["v042_enqueue_status"][
        "status_fingerprint"
    ]
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("v042_enqueue_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["v042_enqueue"]["one_shot_live_enqueue_recorded"] = False
    raw["v042_enqueue"]["record_fingerprint"] = (
        contract.v042_record_fingerprint(raw["v042_enqueue"])
    ).model_dump(mode="python")
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("v042_enqueue_not_recorded",)

    blocked = evaluate_queue_observation_receipt(
        {**_input(tmp_path).model_dump(mode="python"), "home_assistant": True}
    )
    assert blocked.blockers == ("installation_capability_unsupported",)


def test_malformed_observation_ambiguous_state_payload_and_authority_are_closed(
    tmp_path: Path,
) -> None:
    raw_create = _input(tmp_path).create.model_dump(mode="python")
    raw_create["observation_state"] = "maybe_enqueued"
    with pytest.raises(ValidationError):
        QueueObservationReceiptCreateV1.model_validate(raw_create)

    raw_create = _input(tmp_path).create.model_dump(mode="python")
    raw_create["receipt_disposition"] = "unknown"
    with pytest.raises(ValidationError):
        QueueObservationReceiptCreateV1.model_validate(raw_create)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["v042_enqueue"]["queue_item"]["payload_bytes"] = 1
    blocked = evaluate_queue_observation_receipt(raw)
    assert blocked.blockers == ("executable_payload",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["dequeue_allowed"] = True
    with pytest.raises(ValidationError):
        QueueObservationReceiptAuthorityContextV1.model_validate(raw["authority"])

    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    with pytest.raises(ValidationError):
        QueueObservationReceiptValidationInputV1.model_validate(raw)


def test_built_models_reject_tampered_receipt_observation_and_record(
    tmp_path: Path,
) -> None:
    receipt = build_receipt(_input(tmp_path))
    raw = receipt.model_dump(mode="python")
    raw["receipt_evidence"]["receipt_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="receipt|fingerprint"):
        contract.QueueObservationReceiptV1.model_validate(raw)

    raw = receipt.model_dump(mode="python")
    raw["queue_observation"]["observation_state"] = "observed_and_dequeued"
    with pytest.raises(ValidationError):
        contract.QueueObservationReceiptV1.model_validate(raw)

    raw = receipt.model_dump(mode="python")
    raw["receipt_record_fingerprint"]["value"] = "c" * 64
    with pytest.raises(ValidationError, match="record fingerprint"):
        contract.QueueObservationReceiptV1.model_validate(raw)


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
