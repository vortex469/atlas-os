from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.one_shot_dequeue_worker_binding.contract import (
    build_binding as build_v046_binding,
)
from app.one_shot_dequeue_worker_binding.contract import (
    derive_status as derive_v046_status,
)
from app.one_shot_dequeue_worker_binding.test_contract import _input as v046_input
from app.worker_binding_activation_preflight import contract
from app.worker_binding_activation_preflight.contract import (
    PERMISSION,
    SUCCESS_BLOCKERS,
    WorkerBindingActivationPreflightAuthorityContextV1,
    WorkerBindingActivationPreflightCreateV1,
    WorkerBindingActivationPreflightValidationInputV1,
    build_create,
    evaluate_worker_binding_activation_preflight,
    parse_create_json,
)

REQUESTED_AT = "2026-08-27T12:00:36Z"


def _facts(tmp_path: Path):
    binding = build_v046_binding(v046_input(tmp_path))
    binding_status = derive_v046_status(binding, evaluated_at=REQUESTED_AT)
    create = build_create(binding=binding, binding_status=binding_status)
    return binding, binding_status, create


def _input(
    tmp_path: Path, **changes
) -> WorkerBindingActivationPreflightValidationInputV1:
    binding, binding_status, create = _facts(tmp_path)
    raw = {
        "operator_id": binding.operator_id,
        "authority": WorkerBindingActivationPreflightAuthorityContextV1(
            authenticated_operator_id=binding.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": binding.candidate_record_id,
        "create": create,
        "one_shot_dequeue_worker_binding": binding,
        "one_shot_dequeue_worker_binding_status": binding_status,
        "idempotency_key": "worker-binding-activation-preflight-key-1",
    }
    raw.update(changes)
    return WorkerBindingActivationPreflightValidationInputV1.model_validate(raw)


def test_active_v046_binding_preflights_deterministically(tmp_path: Path) -> None:
    validation = _input(tmp_path)
    first = evaluate_worker_binding_activation_preflight(validation)
    second = evaluate_worker_binding_activation_preflight(validation)
    assert first == second
    assert first.preflight_state == "readiness_gated"
    assert first.eligibility == "worker_binding_activation_preflight_recorded"
    assert first.blockers == SUCCESS_BLOCKERS
    assert first.recognized_v046_binding_count == 1
    assert first.preflight_record_build_allowed
    assert first.worker_binding_activation_preflight_recorded
    assert not first.binding_activation_allowed
    assert not first.store_contact_allowed
    assert not first.runtime_contact_allowed
    assert not first.queue_claim_allowed
    assert not first.queue_lease_allowed
    assert not first.queue_ack_allowed
    assert not first.worker_start_allowed
    assert not first.agent_invocation_allowed
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
        "worker-binding-activation-preflight-create-v1",
        "worker-binding-activation-preflight-create-v1-e\u0301",
    )
    with pytest.raises(contract.StrictContractError):
        parse_create_json(non_nfc)
    raw = create.model_dump(mode="python")
    raw["credential"] = "secret"
    with pytest.raises(ValidationError):
        WorkerBindingActivationPreflightCreateV1.model_validate(raw)
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
        blocked = evaluate_worker_binding_activation_preflight(raw)
        assert blocked.blockers == (blocker,)
        assert not blocked.preflight_record_build_allowed

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["payload"] = {"start": True}
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("caller_supplied_command",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["endpoint"] = "https://worker.invalid/intake"
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("caller_supplied_endpoint",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["queue_claim_allowed"] = True
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("unsupported_authority",)
    with pytest.raises(ValidationError):
        WorkerBindingActivationPreflightAuthorityContextV1.model_validate(
            raw["authority"]
        )

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["queue_claim_allowed"] = True
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("unsupported_authority",)


def test_stale_unsupported_identity_and_ambiguity_fail_closed(tmp_path: Path) -> None:
    blocked = evaluate_worker_binding_activation_preflight({})
    assert blocked.blockers == ("evidence_not_found",)
    assert blocked.operator_id == "blocked-evaluation"
    blocked = evaluate_worker_binding_activation_preflight("not an object")  # type: ignore[arg-type]
    assert blocked.blockers == ("evidence_not_found",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("evidence_stale",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["operator_id"] = "foreign-operator"
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("ownership_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["home_assistant"] = True
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("installation_capability_unsupported",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["ambiguous_binding_count"] = 2
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("ambiguous_state",)


def test_rejects_expired_or_tampered_v046_binding(tmp_path: Path) -> None:
    binding, _, _ = _facts(tmp_path)
    expired_status = derive_v046_status(binding, evaluated_at=binding.valid_until)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["one_shot_dequeue_worker_binding_status"] = expired_status.model_dump(
        mode="python"
    )
    raw["create"]["binding_status_fingerprint"] = expired_status.status_fingerprint
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("v046_binding_not_active",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["one_shot_dequeue_worker_binding"]["eligibility"] = "blocked"
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("v046_binding_not_recorded",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["binding_subject_fingerprint"]["value"] = "a" * 64
    blocked = evaluate_worker_binding_activation_preflight(raw)
    assert blocked.blockers == ("fingerprint_mismatch",)

    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    blocked = evaluate_worker_binding_activation_preflight(raw)
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
