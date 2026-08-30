from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.runner_binding_plan.contract import build_plan
from app.runner_binding_plan.contract import derive_status as plan_status
from app.runner_binding_plan.test_contract import PLAN_ID
from app.runner_binding_plan.test_contract import _validation as plan_input
from app.worker_admission_stub import contract
from app.worker_admission_stub.contract import (
    PERMISSION,
    STUB_BLOCKERS,
    StrictContractError,
    WorkerAdmissionAuthorityContextV1,
    WorkerAdmissionIntakeStubV1,
    WorkerAdmissionStubCollectionV1,
    WorkerAdmissionStubCreateV1,
    WorkerAdmissionStubRedactedErrorV1,
    WorkerAdmissionStubResultV1,
    WorkerAdmissionStubV1,
    WorkerAdmissionStubValidationInputV1,
    WorkerReferenceV1,
    build_intake,
    build_stub,
    build_worker_reference,
    derive_status,
    opaque_fingerprint,
    parse_create_json,
    stub_fingerprint,
)

STUB_ID = "1392e17e-6d79-4d92-b428-a676b39feee9"
INTENT_ID = "5af90ae1-ba3d-567b-ac21-9d439df703a7"
WORKER_ID = "77126d0a-01d3-43f3-959a-5106547936bb"
REQUESTED_AT = "2026-08-27T12:00:33Z"


def _plan(tmp_path: Path):
    value, _, _ = build_plan(plan_input(tmp_path), plan_id=PLAN_ID)
    return value, plan_status(value, observed_at="2026-08-27T12:00:32Z")


def _worker(plan):
    return build_worker_reference(
        worker_reference_id=WORKER_ID,
        owner_operator_id=plan.operator_id,
        runner_reference_id=plan.runner_reference.runner_reference_id,
        runner_reference_fingerprint_value=plan.runner_reference.reference_fingerprint,
        identity_fingerprint=opaque_fingerprint(
            "atlas:test:worker-identity:v1", "abstract-worker-one"
        ),
        capability_profile_fingerprint=opaque_fingerprint(
            "atlas:test:worker-capability:v1", "admission-stub-only"
        ),
        inherited_limits=plan.limits,
        valid_from="2026-08-27T12:00:25Z",
        valid_until="2026-08-27T12:00:45Z",
    )


def _input(tmp_path: Path, **changes) -> WorkerAdmissionStubValidationInputV1:
    plan, status = changes.pop("plan_status", _plan(tmp_path))
    worker = changes.pop("worker_reference", _worker(plan))
    create = changes.pop(
        "create",
        WorkerAdmissionStubCreateV1(
            runner_binding_plan_id=plan.plan_id,
            runner_binding_plan_fingerprint=plan.plan_fingerprint,
            runner_binding_plan_valid_until=plan.valid_until,
            worker_reference_id=worker.worker_reference_id,
            worker_reference_fingerprint=worker.reference_fingerprint,
            inherited_limits_fingerprint=plan.limits.limits_fingerprint,
        ),
    )
    values = {
        "operator_id": plan.operator_id,
        "authority": WorkerAdmissionAuthorityContextV1(
            authenticated_operator_id=plan.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": plan.candidate_record_id,
        "create": create,
        "runner_binding_plan": plan,
        "runner_binding_plan_status": status,
        "worker_reference": worker,
        "idempotency_key": "worker-admission-stub-key-1",
    }
    values.update(changes)
    return WorkerAdmissionStubValidationInputV1.model_validate(values)


def test_valid_stub_is_deterministic_immutable_and_evidence_only(
    tmp_path: Path,
) -> None:
    first = build_stub(_input(tmp_path), stub_id=STUB_ID, intent_id=INTENT_ID)
    second = build_stub(_input(tmp_path), stub_id=STUB_ID, intent_id=INTENT_ID)
    assert first == second
    stub, idempotency, reservation = first
    assert stub.stub_fingerprint == stub_fingerprint(stub)
    assert stub.eligibility == "worker_admission_stubbed"
    assert stub.blockers == STUB_BLOCKERS
    assert stub.valid_until == "2026-08-27T12:00:45Z"
    assert stub.worker_admission_intake.intake_state == "undefined"
    assert stub.inherited_limits == stub.worker_reference.inherited_limits
    assert idempotency.reservation_state == "permanently_reserved"
    assert reservation.reservation_state == "permanent"
    assert not reservation.released and not reservation.replay_allowed
    with pytest.raises(ValidationError):
        stub.record_state = "queued"  # type: ignore[misc]


def test_all_effect_authority_is_fixed_false(tmp_path: Path) -> None:
    stub, _, _ = build_stub(_input(tmp_path), stub_id=STUB_ID, intent_id=INTENT_ID)
    fields = (
        "runner_binding_allowed",
        "worker_registered",
        "worker_contacted",
        "worker_reserved",
        "worker_bound",
        "worker_started",
        "queue_created",
        "queue_allowed",
        "work_enqueued",
        "enqueue_allowed",
        "dispatch_allowed",
        "execution_start_allowed",
        "execution_authorized",
        "installation_allowed",
        "retry_allowed",
        "resend_allowed",
        "agent_invocation_allowed",
        "workflow_allowed",
        "docker_allowed",
        "podman_allowed",
        "shell_allowed",
        "process_allowed",
        "provider_mutation_allowed",
        "repository_mutation_allowed",
        "in_guest_mutation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "replay_allowed",
    )
    assert stub.evidence_only and not any(getattr(stub, field) for field in fields)
    assert not stub.worker_admission_intake.request_sent
    assert not stub.worker_reference.invocation_allowed


def test_closed_unknown_duplicate_and_body_envelope_bounds(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(StrictContractError):
        parse_create_json(duplicate)
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        WorkerAdmissionStubCreateV1.model_validate(raw)
    with pytest.raises(StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")
    with pytest.raises(ValidationError, match="collection"):
        WorkerAdmissionStubCollectionV1(stubs=tuple([_blocked()] * 101))


def test_missing_and_mismatched_fingerprints_are_rejected(tmp_path: Path) -> None:
    raw = _input(tmp_path).create.model_dump(mode="python")
    raw.pop("worker_reference_fingerprint")
    with pytest.raises(ValidationError):
        WorkerAdmissionStubCreateV1.model_validate(raw)
    stub, _, _ = build_stub(_input(tmp_path), stub_id=STUB_ID, intent_id=INTENT_ID)
    raw = stub.linkage.model_dump(mode="python")
    raw["v020_v036_chain_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="embedded"):
        contract.WorkerAdmissionStubLinkageV1.model_validate(raw)
    raw = stub.model_dump(mode="python")
    raw["stub_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="fingerprint"):
        WorkerAdmissionStubV1.model_validate(raw)


def test_permission_ownership_and_plan_linkage_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["permission"] = "installation.runner.binding.plan.record"
    with pytest.raises(ValidationError):
        WorkerAdmissionStubValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValidationError, match="ownership"):
        WorkerAdmissionStubValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["runner_binding_plan_fingerprint"]["value"] = "c" * 64
    with pytest.raises(ValidationError, match="plan linkage"):
        WorkerAdmissionStubValidationInputV1.model_validate(raw)


def test_worker_reference_intake_and_inherited_limits_fail_closed(
    tmp_path: Path,
) -> None:
    raw = _input(tmp_path).worker_reference.model_dump(mode="python")
    raw["reference_fingerprint"]["value"] = "d" * 64
    with pytest.raises(ValidationError, match="reference fingerprint"):
        WorkerReferenceV1.model_validate(raw)
    raw = _input(tmp_path).worker_reference.model_dump(mode="python")
    raw["eligibility"] = "available"
    with pytest.raises(ValidationError):
        WorkerReferenceV1.model_validate(raw)
    stub, _, _ = build_stub(_input(tmp_path), stub_id=STUB_ID, intent_id=INTENT_ID)
    raw = stub.worker_admission_intake.model_dump(mode="python")
    raw["queue_created"] = True
    with pytest.raises(ValidationError):
        WorkerAdmissionIntakeStubV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "e" * 64
    with pytest.raises(ValidationError, match="limits"):
        WorkerAdmissionStubValidationInputV1.model_validate(raw)


def test_stale_expired_and_non_active_plan_are_rejected(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:01Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        WorkerAdmissionStubValidationInputV1.model_validate(raw)
    plan, _ = _plan(tmp_path)
    expired = plan_status(plan, observed_at=plan.valid_until)
    with pytest.raises(ValidationError, match="not active"):
        _input(tmp_path, plan_status=(plan, expired))


def test_stubbed_readiness_gated_blocked_and_lifecycle_states(tmp_path: Path) -> None:
    validation = _input(tmp_path)
    assert (
        validation.runner_binding_plan.linkage.execution_admission_linkage
        .permission_grant_linkage.readiness_linkage
    )
    assert validation.runner_binding_plan.eligibility == "binding_planned"
    stub, _, _ = build_stub(validation, stub_id=STUB_ID, intent_id=INTENT_ID)
    assert stub.eligibility == "worker_admission_stubbed"
    assert derive_status(stub, observed_at=stub.recorded_at).lifecycle == "active"
    assert derive_status(stub, observed_at=stub.valid_until).lifecycle == "expired"
    blocked = _blocked()
    assert blocked.disposition == "blocked"
    assert not blocked.execution_authorized


def _blocked() -> WorkerAdmissionStubResultV1:
    error = WorkerAdmissionStubRedactedErrorV1(
        error_code="not_eligible",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:worker-admission-correlation:v1", "blocked"
        ),
    )
    return WorkerAdmissionStubResultV1(
        disposition="blocked",
        stub=None,
        status=None,
        audit_evidence=None,
        error=error,
    )


def test_home_assistant_is_blocked_golden(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Home Assistant"):
        _input(tmp_path, home_assistant=True)


def test_intake_and_fingerprints_are_deterministic(tmp_path: Path) -> None:
    validation = _input(tmp_path)
    stub, _, _ = build_stub(validation, stub_id=STUB_ID, intent_id=INTENT_ID)
    assert build_intake(stub.worker_admission_intent) == stub.worker_admission_intake
    assert build_stub(validation, stub_id=STUB_ID, intent_id=INTENT_ID)[0] == stub


def test_contract_has_no_forbidden_runtime_or_execution_worker_imports() -> None:
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
        "app.execution.worker",
        "agent",
        "dispatch",
        "docker",
        "provider",
        "repository",
        "requests",
        "socket",
        "subprocess",
        "workflow",
    )
    assert not [name for name in imports if any(term in name for term in forbidden)]
    source = path.read_text(encoding="utf-8").lower()
    for call in (
        "subprocess.",
        "os.system",
        "create_subprocess",
        "docker ",
        "podman ",
        ".enqueue(",
        ".dispatch(",
        ".start_worker(",
        ".execute(",
        ".invoke_agent(",
    ):
        assert call not in source
