from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.one_shot_controlled_dequeue.contract import (
    build_receipt as build_v045_receipt,
)
from app.one_shot_controlled_dequeue.contract import (
    derive_status as derive_v045_status,
)
from app.one_shot_controlled_dequeue.test_contract import _input as v045_input
from app.one_shot_dequeue_worker_binding import contract
from app.one_shot_dequeue_worker_binding.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    OneShotDequeueWorkerBindingAuthorityContextV1,
    OneShotDequeueWorkerBindingCreateV1,
    OneShotDequeueWorkerBindingValidationInputV1,
    build_create,
    evaluate_one_shot_dequeue_worker_binding,
    parse_create_json,
)
from app.worker_intake_admission.contract import (
    build_admission as build_v040_admission,
)
from app.worker_intake_admission.contract import (
    derive_status as derive_v040_status,
)
from app.worker_intake_admission.test_contract import _input as v040_input

V040_ADMISSION_ID = "5ac56d6f-5791-496c-8fe6-946c6011b3f6"
V040_DECISION_ID = "b1cef0d5-1ed7-5ce9-91e2-ecac31bd0d49"
REQUESTED_AT = "2026-08-27T12:00:35Z"


def _facts(tmp_path: Path):
    dequeue = build_v045_receipt(v045_input(tmp_path))
    dequeue_status = derive_v045_status(dequeue, evaluated_at=REQUESTED_AT)
    worker, _, _ = build_v040_admission(
        v040_input(tmp_path),
        admission_id=V040_ADMISSION_ID,
        decision_id=V040_DECISION_ID,
    )
    worker_status = derive_v040_status(worker, evaluated_at=REQUESTED_AT)
    create = build_create(
        dequeue=dequeue,
        dequeue_status=dequeue_status,
        worker=worker,
        worker_status=worker_status,
    )
    return dequeue, dequeue_status, worker, worker_status, create


def _input(tmp_path: Path, **changes) -> OneShotDequeueWorkerBindingValidationInputV1:
    dequeue, dequeue_status, worker, worker_status, create = _facts(tmp_path)
    raw = {
        "operator_id": dequeue.operator_id,
        "authority": OneShotDequeueWorkerBindingAuthorityContextV1(
            authenticated_operator_id=dequeue.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": dequeue.candidate_record_id,
        "create": create,
        "one_shot_controlled_dequeue": dequeue,
        "one_shot_controlled_dequeue_status": dequeue_status,
        "worker_intake_admission": worker,
        "worker_intake_admission_status": worker_status,
        "idempotency_key": "one-shot-dequeue-worker-binding-key-1",
    }
    raw.update(changes)
    return OneShotDequeueWorkerBindingValidationInputV1.model_validate(raw)


def test_successful_v045_binds_exact_worker_subject_deterministically(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_one_shot_dequeue_worker_binding(validation)
    second = evaluate_one_shot_dequeue_worker_binding(validation)
    assert first == second
    assert first.binding_state == "readiness_gated"
    assert first.eligibility == "one_shot_dequeue_worker_binding_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.recognized_successful_v045_dequeue_count == 1
    assert first.recognized_worker_subject_count == 1
    assert first.binding_record_build_allowed
    assert first.one_shot_dequeue_worker_binding_recorded
    assert not first.store_contact_allowed
    assert not first.runtime_contact_allowed
    assert not first.worker_contact_allowed
    assert not first.worker_start_allowed
    assert not first.execution_start_allowed
    with pytest.raises(ValidationError):
        first.worker_start_allowed = True  # type: ignore[misc]


def test_create_is_closed_strict_nfc_and_size_bounded(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"\xff")
    non_nfc = create.model_dump_json().replace(
        "one-shot-dequeue-worker-binding-create-v1",
        "one-shot-dequeue-worker-binding-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    raw = create.model_dump(mode="python")
    raw["credential"] = "secret"
    with pytest.raises(ValidationError):
        OneShotDequeueWorkerBindingCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_rejects_caller_credentials_endpoints_commands_and_authority(
    tmp_path: Path,
) -> None:
    for field, blocker in (
        ("credential_material_present", "caller_supplied_credential"),
        ("endpoint_material_present", "caller_supplied_endpoint"),
        ("command_material_present", "caller_supplied_command"),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["create"][field] = True
        blocked = evaluate_one_shot_dequeue_worker_binding(raw)
        assert blocked.blockers == (blocker,)
        assert not blocked.binding_record_build_allowed

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["command"] = "sh -c whoami"
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("caller_supplied_command",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["endpoint"] = "https://worker.invalid/intake"
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("caller_supplied_endpoint",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["worker_start_allowed"] = True
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("unsupported_authority",)
    with pytest.raises(ValidationError):
        OneShotDequeueWorkerBindingAuthorityContextV1.model_validate(raw["authority"])


def test_stale_unsupported_identity_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_one_shot_dequeue_worker_binding({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_worker_subject_count"] = 2
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_unsuccessful_v045_and_worker_subject_mismatch(tmp_path: Path) -> None:
    _, _, worker, worker_status, _ = _facts(tmp_path)
    failed_dequeue = build_v045_receipt(v045_input(tmp_path), outcome="failure")
    failed_dequeue_status = derive_v045_status(failed_dequeue, evaluated_at=REQUESTED_AT)
    failed_create = build_create(
        dequeue=failed_dequeue,
        dequeue_status=failed_dequeue_status,
        worker=worker,
        worker_status=worker_status,
    )
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"] = failed_create.model_dump(mode="python")
    raw["one_shot_controlled_dequeue"] = failed_dequeue.model_dump(mode="python")
    raw["one_shot_controlled_dequeue_status"] = failed_dequeue_status.model_dump(
        mode="python"
    )
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("v045_dequeue_not_successful",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["worker_subject_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("worker_subject_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_item_reference_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("queue_item_reference_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "c" * 64
    blocked = evaluate_one_shot_dequeue_worker_binding(raw)
    assert blocked.blockers == ("inherited_limits_mismatch",)


def test_contract_has_no_forbidden_imports_calls_or_runtime_surfaces() -> None:
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
