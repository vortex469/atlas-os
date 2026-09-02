from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.worker_intake_admission import contract
from app.worker_intake_admission.contract import (
    ADMISSION_BLOCKERS,
    PERMISSION,
    WorkerIntakeAdmissionAuthorityContextV1,
    WorkerIntakeAdmissionCollectionV1,
    WorkerIntakeAdmissionCreateV1,
    WorkerIntakeAdmissionQueueReservationEvidenceV1,
    WorkerIntakeAdmissionRedactedErrorV1,
    WorkerIntakeAdmissionResultV1,
    WorkerIntakeAdmissionValidationInputV1,
    build_admission,
    build_collection,
    build_queue_reservation_evidence,
    build_worker_identity,
    build_worker_intake_reference,
    derive_status,
    evaluate_worker_intake_admission,
    opaque_fingerprint,
    parse_create_json,
    queue_reservation_evidence_fingerprint,
    record_fingerprint,
)
from app.worker_queue_reservation.contract import build_reservation
from app.worker_queue_reservation.test_contract import (
    RESERVATION_ID,
    _input as queue_input,
)

ADMISSION_ID = "5ac56d6f-5791-496c-8fe6-946c6011b3f6"
DECISION_ID = "b1cef0d5-1ed7-5ce9-91e2-ecac31bd0d49"
WORKER_IDENTITY_ID = "5286e7d4-762a-475a-94c0-c24bd7b590b8"
INTAKE_REFERENCE_ID = "606c8f27-03bd-4603-907b-2395d15f1ccf"
REQUESTED_AT = "2026-08-27T12:00:34Z"


def _facts(tmp_path: Path):
    reservation, _, _ = build_reservation(
        queue_input(tmp_path), reservation_id=RESERVATION_ID
    )
    from app.worker_queue_reservation.contract import derive_status as queue_status

    status = queue_status(reservation, observed_at=REQUESTED_AT)
    identity = build_worker_identity(
        worker_identity_id=WORKER_IDENTITY_ID,
        owner_operator_id=reservation.operator_id,
        candidate_record_id=reservation.candidate_record_id,
        worker_queue_reservation=reservation,
        identity_fingerprint=opaque_fingerprint(
            "atlas:test:worker-identity:v1", "abstract-worker"
        ),
        capability_profile_fingerprint=opaque_fingerprint(
            "atlas:test:worker-capability:v1", "intake-admission-only"
        ),
        valid_from="2026-08-27T12:00:25Z",
        valid_until="2026-08-27T12:00:45Z",
    )
    intake = build_worker_intake_reference(
        worker_intake_reference_id=INTAKE_REFERENCE_ID,
        owner_operator_id=reservation.operator_id,
        candidate_record_id=reservation.candidate_record_id,
        worker_queue_reservation=reservation,
        worker_identity=identity,
        valid_from="2026-08-27T12:00:25Z",
        valid_until="2026-08-27T12:00:45Z",
    )
    create = WorkerIntakeAdmissionCreateV1(
        worker_queue_reservation_id=reservation.reservation_id,
        worker_queue_reservation_fingerprint=reservation.record_fingerprint,
        worker_queue_reservation_valid_until=reservation.valid_until,
        worker_identity_id=identity.worker_identity_id,
        worker_identity_fingerprint=identity.worker_identity_fingerprint,
        worker_intake_reference_id=intake.worker_intake_reference_id,
        worker_intake_reference_fingerprint=intake.intake_reference_fingerprint,
        inherited_limits_fingerprint=reservation.inherited_limits.limits_fingerprint,
    )
    return reservation, status, identity, intake, create


def _input(tmp_path: Path, **changes) -> WorkerIntakeAdmissionValidationInputV1:
    reservation, status, identity, intake, create = _facts(tmp_path)
    raw = {
        "operator_id": reservation.operator_id,
        "authority": WorkerIntakeAdmissionAuthorityContextV1(
            authenticated_operator_id=reservation.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": reservation.candidate_record_id,
        "create": create,
        "worker_queue_reservation": reservation,
        "worker_queue_reservation_status": status,
        "worker_identity": identity,
        "worker_intake_reference": intake,
        "idempotency_key": "worker-intake-admission-key-1",
    }
    raw.update(changes)
    return WorkerIntakeAdmissionValidationInputV1.model_validate(raw)


def test_valid_models_are_deterministic_immutable_and_evidence_only(tmp_path: Path) -> None:
    first = build_admission(
        _input(tmp_path), admission_id=ADMISSION_ID, decision_id=DECISION_ID
    )
    second = build_admission(
        _input(tmp_path), admission_id=ADMISSION_ID, decision_id=DECISION_ID
    )
    assert first == second
    record, idempotency, permanent = first
    assert record.record_fingerprint == record_fingerprint(record)
    assert record.eligibility == "worker_intake_admission_recorded"
    assert record.blockers == ADMISSION_BLOCKERS
    assert idempotency.permanent and permanent.permanent
    assert not permanent.released and not permanent.replay_bypass_allowed
    with pytest.raises(ValidationError):
        record.record_state = "enqueued"  # type: ignore[misc]


def test_deterministic_evaluator_recognizes_one_inert_v039_queue_reservation(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    first = evaluate_worker_intake_admission(validation)
    second = evaluate_worker_intake_admission(validation)
    assert first == second
    assert first.eligibility == "worker_intake_admission_recorded"
    assert first.blockers == ADMISSION_BLOCKERS
    assert first.admission_record_build_allowed
    assert first.recognized_v039_queue_reservation_count == 1
    assert first.recognized_v039_queue_reservation_as_inert_evidence
    assert first.queue_reservation_evidence is not None
    assert first.queue_reservation_evidence.reservations == (
        validation.worker_queue_reservation,
    )
    assert not first.queue_reservation_evidence.live_enqueue_defined
    assert not first.queue_reservation_evidence.dequeue_defined
    assert not first.queue_reservation_evidence.worker_start_defined
    assert not first.live_enqueue_allowed
    assert not first.dequeue_allowed
    assert not first.queue_polling_allowed
    assert not first.worker_start_allowed
    assert not first.execution_start_allowed


def test_queue_reservation_evidence_requires_exactly_one_active_v039_record(
    tmp_path: Path,
) -> None:
    validation = _input(tmp_path)
    evidence = build_queue_reservation_evidence(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        reservation=validation.worker_queue_reservation,
        status=validation.worker_queue_reservation_status,
    )
    assert evidence.evidence_fingerprint == queue_reservation_evidence_fingerprint(
        evidence
    )
    raw = evidence.model_dump(mode="python")
    raw["reservations"] = [raw["reservations"][0], raw["reservations"][0]]
    raw["count"] = 2
    with pytest.raises(ValidationError, match="exactly one v0.39"):
        WorkerIntakeAdmissionQueueReservationEvidenceV1.model_validate(raw)
    raw = evidence.model_dump(mode="python")
    raw["statuses"][0]["lifecycle"] = "expired"
    with pytest.raises(ValidationError, match="active inert"):
        WorkerIntakeAdmissionQueueReservationEvidenceV1.model_validate(raw)


def test_fixed_false_authority_and_non_runtime_references(tmp_path: Path) -> None:
    record, _, _ = build_admission(
        _input(tmp_path), admission_id=ADMISSION_ID, decision_id=DECISION_ID
    )
    authority = (
        "live_enqueue_allowed",
        "dequeue_allowed",
        "queue_polling_allowed",
        "worker_contact_allowed",
        "worker_start_allowed",
        "execution_start_allowed",
        "runner_binding_allowed",
        "dispatch_allowed",
        "retry_allowed",
        "resend_allowed",
        "agent_invocation_allowed",
        "workflow_start_allowed",
        "docker_execution_allowed",
        "podman_execution_allowed",
        "shell_execution_allowed",
        "process_execution_allowed",
        "provider_mutation_allowed",
        "repository_mutation_allowed",
        "in_guest_mutation_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "replay_bypass_allowed",
    )
    assert record.evidence_only
    assert not any(getattr(record, field) for field in authority)
    assert not record.worker_identity.reachable
    assert not record.worker_intake_reference.intake_exists
    assert not record.admission_decision.queue_enqueued


def test_closed_duplicate_unknown_and_bounds(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate)
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        WorkerIntakeAdmissionCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")


def test_queue_reservation_binding_and_limits_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["worker_queue_reservation_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="queue reservation binding"):
        WorkerIntakeAdmissionValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="limits"):
        WorkerIntakeAdmissionValidationInputV1.model_validate(raw)


def test_stale_expired_default_disabled_and_home_assistant(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        WorkerIntakeAdmissionValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    with pytest.raises(ValidationError):
        WorkerIntakeAdmissionValidationInputV1.model_validate(raw)
    with pytest.raises(ValidationError, match="Home Assistant"):
        _input(tmp_path, home_assistant=True)
    blocked = evaluate_worker_intake_admission(
        {
            **_input(tmp_path).model_dump(mode="python"),
            "home_assistant": True,
        }
    )
    assert blocked.eligibility == "blocked"
    assert blocked.blockers == ("installation_capability_unsupported",)
    assert not blocked.admission_record_build_allowed
    assert blocked.queue_reservation_evidence is None
    assert blocked.recognized_v039_queue_reservation_count == 0


def test_status_result_collection_and_redacted_error(tmp_path: Path) -> None:
    record, _, _ = build_admission(
        _input(tmp_path), admission_id=ADMISSION_ID, decision_id=DECISION_ID
    )
    assert derive_status(record, evaluated_at=record.recorded_at).lifecycle == "active"
    assert derive_status(record, evaluated_at=record.valid_until).lifecycle == "expired"
    raw = derive_status(record, evaluated_at=record.recorded_at).model_dump(mode="python")
    raw["eligibility"] = "ready_to_dequeue"
    with pytest.raises(ValidationError):
        contract.WorkerIntakeAdmissionStatusV1.model_validate(raw)
    error = WorkerIntakeAdmissionRedactedErrorV1(
        error_code="not_found",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:intake-correlation:v1", "blocked"
        ),
    )
    result = WorkerIntakeAdmissionResultV1(
        ok=False,
        admission=None,
        error=error,
        correlation_fingerprint=error.correlation_fingerprint,
    )
    assert result.error.message == contract.SAFE_MESSAGE
    assert result.error.redacted and not result.execution_start_allowed
    collection = build_collection(
        operator_id=record.operator_id,
        candidate_record_id=record.candidate_record_id,
        items=(record,),
    )
    assert collection.count == 1 and collection.items == (record,)
    with pytest.raises(ValidationError, match="collection"):
        WorkerIntakeAdmissionCollectionV1(
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
    )
    assert not [name for name in imports if any(term in name for term in forbidden)]
    source = path.read_text(encoding="utf-8").lower()
    for call in (
        "subprocess.",
        "os.system",
        "create_subprocess",
        ".enqueue(",
        ".dequeue(",
        ".dispatch(",
        ".start_worker(",
        ".execute(",
        ".invoke_agent(",
    ):
        assert call not in source
