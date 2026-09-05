from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.worker_binding_activation_evidence import contract
from app.worker_binding_activation_evidence.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    WorkerBindingActivationEvidenceAuthorityContextV1,
    WorkerBindingActivationEvidenceCreateV1,
    WorkerBindingActivationEvidenceValidationInputV1,
    build_activation_evidence,
    build_create,
    derive_status,
    evaluate_worker_binding_activation_evidence,
    parse_create_json,
)
from app.worker_binding_activation_preflight.contract import (
    build_preflight as build_v047_preflight,
)
from app.worker_binding_activation_preflight.contract import (
    derive_status as derive_v047_status,
)
from app.worker_binding_activation_preflight.test_contract import _input as v047_input

REQUESTED_AT = "2026-08-27T12:00:40Z"


def _facts(tmp_path: Path):
    preflight_validation = v047_input(tmp_path)
    preflight = build_v047_preflight(preflight_validation)
    preflight_status = derive_v047_status(preflight, evaluated_at=REQUESTED_AT)
    create = build_create(preflight=preflight, preflight_status=preflight_status)
    return preflight, preflight_status, create


def _input(
    tmp_path: Path, **changes
) -> WorkerBindingActivationEvidenceValidationInputV1:
    preflight, preflight_status, create = _facts(tmp_path)
    raw = {
        "operator_id": preflight.operator_id,
        "authority": WorkerBindingActivationEvidenceAuthorityContextV1(
            authenticated_operator_id=preflight.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": preflight.candidate_record_id,
        "create": create,
        "worker_binding_activation_preflight": preflight,
        "worker_binding_activation_preflight_status": preflight_status,
        "idempotency_key": "worker-binding-activation-evidence-key-1",
    }
    raw.update(changes)
    return WorkerBindingActivationEvidenceValidationInputV1.model_validate(raw)


def test_active_v047_preflight_records_activation_evidence_deterministically(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_worker_binding_activation_evidence(validation)
    second = evaluate_worker_binding_activation_evidence(validation)
    assert first == second
    assert first.activation_evidence_state == "readiness_gated"
    assert first.eligibility == "worker_binding_activation_evidence_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.recognized_v047_preflight_count == 1
    assert first.activation_evidence_record_build_allowed
    assert first.worker_binding_activation_evidence_recorded
    assert not first.binding_activation_allowed
    assert not first.worker_activation_runtime_allowed
    assert not first.worker_start_admission_allowed
    assert not first.store_contact_allowed
    assert not first.runtime_contact_allowed
    assert not first.queue_claim_allowed
    assert not first.queue_lease_allowed
    assert not first.queue_ack_allowed
    assert not first.worker_start_allowed
    assert not first.agent_invocation_allowed
    assert not first.execution_start_allowed

    record = build_activation_evidence(validation)
    status = derive_status(record, evaluated_at=record.recorded_at)
    assert record.worker_binding_activation_evidence_recorded
    assert status.lifecycle == "active"
    assert status.activation_evidence_id == record.activation_evidence_id
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
        "worker-binding-activation-evidence-create-v1",
        "worker-binding-activation-evidence-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    raw = create.model_dump(mode="python")
    raw["credential"] = "secret"
    with pytest.raises(ValidationError):
        WorkerBindingActivationEvidenceCreateV1.model_validate(raw)
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
        blocked = evaluate_worker_binding_activation_evidence(raw)
        assert blocked.blockers == (blocker,)
        assert not blocked.activation_evidence_record_build_allowed

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["payload"] = {"start": True}
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("caller_supplied_command",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["endpoint"] = "https://worker.invalid/intake"
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("caller_supplied_endpoint",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["worker_start_admission_allowed"] = True
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("unsupported_authority",)
    with pytest.raises(ValidationError):
        WorkerBindingActivationEvidenceAuthorityContextV1.model_validate(
            raw["authority"]
        )

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_claim_allowed"] = True
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("unsupported_authority",)


def test_stale_unsupported_identity_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_worker_binding_activation_evidence({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    blocked = evaluate_worker_binding_activation_evidence("not an object")  # type: ignore[arg-type]
    assert blocked.blockers == ("evidence_not_found",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:40Z"
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_preflight_count"] = 2
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_expired_or_tampered_v047_preflight(tmp_path: Path) -> None:
    preflight, _, _ = _facts(tmp_path)
    expired_status = derive_v047_status(preflight, evaluated_at=preflight.valid_until)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_binding_activation_preflight_status"] = expired_status.model_dump(
        mode="python"
    )
    raw["create"]["preflight_status_fingerprint"] = expired_status.status_fingerprint
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("v047_preflight_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["worker_binding_activation_preflight"]["eligibility"] = "blocked"
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("v047_preflight_not_recorded",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["preflight_record_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_worker_binding_activation_evidence(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_worker_binding_activation_evidence(raw)
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
