from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.controlled_worker_queue_claim_admission import contract
from app.controlled_worker_queue_claim_admission.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    ControlledWorkerQueueClaimAdmissionAuthorityContextV1,
    ControlledWorkerQueueClaimAdmissionCreateV1,
    ControlledWorkerQueueClaimAdmissionValidationInputV1,
    build_admission,
    build_create,
    derive_status,
    evaluate_controlled_worker_queue_claim_admission,
    parse_create_json,
)
from app.worker_binding_activation_evidence.contract import (
    build_activation_evidence as build_v048_activation_evidence,
)
from app.worker_binding_activation_evidence.contract import (
    derive_status as derive_v048_status,
)
from app.worker_binding_activation_evidence.test_contract import _input as v048_input

REQUESTED_AT = "2026-08-27T12:00:44Z"


def _facts(tmp_path: Path):
    activation_validation = v048_input(tmp_path)
    activation_evidence = build_v048_activation_evidence(activation_validation)
    activation_status = derive_v048_status(
        activation_evidence, evaluated_at=REQUESTED_AT
    )
    create = build_create(
        activation_evidence=activation_evidence,
        activation_evidence_status=activation_status,
    )
    return activation_evidence, activation_status, create


def _input(
    tmp_path: Path, **changes
) -> ControlledWorkerQueueClaimAdmissionValidationInputV1:
    activation_evidence, activation_status, create = _facts(tmp_path)
    raw = {
        "operator_id": activation_evidence.operator_id,
        "authority": ControlledWorkerQueueClaimAdmissionAuthorityContextV1(
            authenticated_operator_id=activation_evidence.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": activation_evidence.candidate_record_id,
        "create": create,
        "worker_binding_activation_evidence": activation_evidence,
        "worker_binding_activation_evidence_status": activation_status,
        "idempotency_key": "controlled-worker-queue-claim-key-1",
    }
    raw.update(changes)
    return ControlledWorkerQueueClaimAdmissionValidationInputV1.model_validate(raw)


def test_active_v048_activation_evidence_records_queue_claim_admission_deterministically(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_controlled_worker_queue_claim_admission(validation)
    second = evaluate_controlled_worker_queue_claim_admission(validation)
    assert first == second
    assert first.admission_state == "readiness_gated"
    assert first.eligibility == "controlled_worker_queue_claim_admission_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.recognized_v048_activation_evidence_count == 1
    assert first.admission_record_build_allowed
    assert first.controlled_worker_queue_claim_admission_recorded
    assert not first.queue_claim_allowed
    assert not first.queue_lease_allowed
    assert not first.queue_ack_allowed
    assert not first.queue_claimed
    assert not first.queue_leased
    assert not first.queue_acknowledged
    assert not first.worker_activation_runtime_allowed
    assert not first.store_contact_allowed
    assert not first.runtime_contact_allowed
    assert not first.worker_start_admission_allowed
    assert not first.worker_start_allowed
    assert not first.worker_start_admitted
    assert not first.worker_started
    assert not first.agent_invocation_allowed
    assert not first.execution_start_allowed
    assert not first.execution_started

    record = build_admission(validation)
    status = derive_status(record, evaluated_at=record.recorded_at)
    assert record.controlled_worker_queue_claim_admission_recorded
    assert status.lifecycle == "active"
    assert status.admission_id == record.admission_id
    with pytest.raises(ValidationError):
        first.queue_claim_allowed = True  # type: ignore[misc]


def test_create_is_closed_strict_nfc_and_size_bounded(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"\xff")
    non_nfc = create.model_dump_json().replace(
        "controlled-worker-queue-claim-admission-create-v1",
        "controlled-worker-queue-claim-admission-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    raw = create.model_dump(mode="python")
    raw["credential"] = "secret"
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimAdmissionCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_rejects_credentials_endpoints_payloads_and_authority(tmp_path: Path) -> None:
    for field, blocker in (
        ("credential_material_present", "caller_supplied_credential"),
        ("endpoint_material_present", "caller_supplied_endpoint"),
        ("command_material_present", "caller_supplied_command"),
        ("payload_material_present", "caller_supplied_command"),
    ):
        raw = _input(tmp_path).model_dump(mode="python")
        raw["create"][field] = True
        blocked = evaluate_controlled_worker_queue_claim_admission(raw)
        assert blocked.blockers == (blocker,)
        assert not blocked.admission_record_build_allowed

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["payload"] = {"claim": True}
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("caller_supplied_command",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["endpoint"] = "https://worker.invalid/queue"
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("caller_supplied_endpoint",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["queue_claim_allowed"] = True
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("unsupported_authority",)
    with pytest.raises(ValidationError):
        ControlledWorkerQueueClaimAdmissionAuthorityContextV1.model_validate(
            raw["authority"]
        )

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_claim_allowed"] = True
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("unsupported_authority",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("unsupported_authority",)


def test_stale_unsupported_identity_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_controlled_worker_queue_claim_admission({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    blocked = evaluate_controlled_worker_queue_claim_admission("not an object")  # type: ignore[arg-type]
    assert blocked.blockers == ("evidence_not_found",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:40Z"
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_activation_evidence_count"] = 2
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_expired_or_tampered_v048_activation_evidence(tmp_path: Path) -> None:
    activation_evidence, _, _ = _facts(tmp_path)
    expired_status = derive_v048_status(
        activation_evidence, evaluated_at=activation_evidence.valid_until
    )
    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_binding_activation_evidence_status"] = expired_status.model_dump(
        mode="python"
    )
    raw["create"]["activation_evidence_status_fingerprint"] = (
        expired_status.status_fingerprint
    )
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("v048_activation_evidence_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_binding_activation_evidence"]["eligibility"] = "blocked"
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("v048_activation_evidence_not_recorded",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["activation_evidence_record_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_controlled_worker_queue_claim_admission(raw)
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
