from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.worker_admission_stub.contract import build_stub
from app.worker_admission_stub.test_contract import INTENT_ID, STUB_ID
from app.worker_admission_stub.test_contract import _input as stub_input
from app.worker_queue_reservation import contract
from app.worker_queue_reservation.contract import (
    PERMISSION,
    RESERVATION_BLOCKERS,
    QueueIntakeReferenceV1,
    WorkerQueueReservationAuthorityContextV1,
    WorkerQueueReservationCollectionV1,
    WorkerQueueReservationCreateV1,
    WorkerQueueReservationRedactedErrorV1,
    WorkerQueueReservationResultV1,
    WorkerQueueReservationValidationInputV1,
    build_queue_intake_reference,
    build_queue_item_reference,
    build_reservation,
    derive_status,
    opaque_fingerprint,
    parse_create_json,
    record_fingerprint,
)

RESERVATION_ID = "34cf9da2-402e-4b24-95e2-10fd933853be"
INTAKE_ID = "d94b82de-14bb-4557-aa5d-a21ec3fc3b6e"
ITEM_ID = "9981517d-b91d-51ef-bbf3-f322a173f7f0"
REQUESTED_AT = "2026-08-27T12:00:34Z"


def _facts(tmp_path: Path):
    stub, _, _ = build_stub(
        stub_input(tmp_path), stub_id=STUB_ID, intent_id=INTENT_ID
    )
    from app.worker_admission_stub.contract import derive_status as stub_status

    status = stub_status(stub, observed_at=REQUESTED_AT)
    intake = build_queue_intake_reference(
        queue_intake_reference_id=INTAKE_ID,
        owner_operator_id=stub.operator_id,
        candidate_record_id=stub.candidate_record_id,
        worker_admission_stub=stub,
        identity_fingerprint=opaque_fingerprint(
            "atlas:test:queue-identity:v1", "abstract-queue"
        ),
        capability_fingerprint=opaque_fingerprint(
            "atlas:test:queue-capability:v1", "reservation-evidence-only"
        ),
        valid_from="2026-08-27T12:00:25Z",
        valid_until="2026-08-27T12:00:45Z",
    )
    item = build_queue_item_reference(
        queue_item_reference_id=ITEM_ID,
        operator_id=stub.operator_id,
        candidate_record_id=stub.candidate_record_id,
        worker_admission_stub=stub,
        queue_intake_reference=intake,
        created_at=REQUESTED_AT,
    )
    create = WorkerQueueReservationCreateV1(
        worker_admission_stub_id=stub.stub_id,
        worker_admission_stub_fingerprint=stub.stub_fingerprint,
        worker_admission_stub_valid_until=stub.valid_until,
        queue_intake_reference_id=intake.queue_intake_reference_id,
        queue_intake_reference_fingerprint=intake.reference_fingerprint,
        queue_item_reference_id=item.queue_item_reference_id,
        queue_item_reference_fingerprint=item.item_fingerprint,
        inherited_limits_fingerprint=stub.inherited_limits.limits_fingerprint,
    )
    return stub, status, intake, create


def _input(tmp_path: Path, **changes) -> WorkerQueueReservationValidationInputV1:
    stub, status, intake, create = _facts(tmp_path)
    raw = {
        "operator_id": stub.operator_id,
        "authority": WorkerQueueReservationAuthorityContextV1(
            authenticated_operator_id=stub.operator_id,
            permission=PERMISSION,
            request_received_at=REQUESTED_AT,
        ),
        "candidate_record_id": stub.candidate_record_id,
        "create": create,
        "worker_admission_stub": stub,
        "worker_admission_stub_status": status,
        "queue_intake_reference": intake,
        "idempotency_key": "worker-queue-reservation-key-1",
    }
    raw.update(changes)
    return WorkerQueueReservationValidationInputV1.model_validate(raw)


def test_valid_models_are_deterministic_immutable_and_evidence_only(tmp_path: Path) -> None:
    first = build_reservation(_input(tmp_path), reservation_id=RESERVATION_ID)
    second = build_reservation(_input(tmp_path), reservation_id=RESERVATION_ID)
    assert first == second
    record, idempotency, permanent = first
    assert record.record_fingerprint == record_fingerprint(record)
    assert record.eligibility == "worker_queue_reservation_recorded"
    assert record.blockers == RESERVATION_BLOCKERS
    assert idempotency.permanent and permanent.permanent
    assert not permanent.released and not permanent.replay_bypass_allowed
    with pytest.raises(ValidationError):
        record.record_state = "enqueued"  # type: ignore[misc]


def test_fixed_false_authority_and_non_enqueuing_references(tmp_path: Path) -> None:
    record, _, _ = build_reservation(_input(tmp_path), reservation_id=RESERVATION_ID)
    authority = (
        "live_enqueue_allowed", "dequeue_allowed", "worker_start_allowed",
        "execution_start_allowed", "runner_binding_allowed", "dispatch_allowed",
        "retry_allowed", "resend_allowed", "agent_invocation_allowed",
        "workflow_start_allowed", "docker_execution_allowed",
        "podman_execution_allowed", "shell_execution_allowed",
        "process_execution_allowed", "provider_mutation_allowed",
        "repository_mutation_allowed", "in_guest_mutation_allowed",
        "installation_allowed", "deployment_allowed", "rollback_allowed",
        "replay_bypass_allowed",
    )
    assert record.evidence_only and not record.default_enabled
    assert not any(getattr(record, field) for field in authority)
    assert not record.queue_intake_reference.queue_exists
    assert not record.queue_item_reference.payload_defined
    assert not record.queue_item_reference.enqueued


def test_closed_duplicate_unknown_and_bounds(tmp_path: Path) -> None:
    create = _input(tmp_path).create
    assert parse_create_json(create.model_dump_json()) == create
    duplicate = create.model_dump_json()[:-1] + ',"schema":"duplicate"}'
    with pytest.raises(contract.StrictContractError):
        parse_create_json(duplicate)
    raw = create.model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        WorkerQueueReservationCreateV1.model_validate(raw)
    with pytest.raises(contract.StrictContractError):
        parse_create_json(b"{" + b" " * (16 * 1024) + b"}")
    with pytest.raises(ValidationError, match="collection"):
        WorkerQueueReservationCollectionV1(items=(), count=101)


def test_missing_and_mismatched_fingerprints_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).create.model_dump(mode="python")
    raw.pop("queue_item_reference_fingerprint")
    with pytest.raises(ValidationError):
        WorkerQueueReservationCreateV1.model_validate(raw)
    record, _, _ = build_reservation(_input(tmp_path), reservation_id=RESERVATION_ID)
    raw = record.linkage.model_dump(mode="python")
    raw["v020_v037_chain_fingerprint"]["value"] = "a" * 64
    with pytest.raises(ValidationError, match="embedded"):
        contract.WorkerQueueReservationLinkageV1.model_validate(raw)
    raw = record.model_dump(mode="python")
    raw["record_fingerprint"]["value"] = "b" * 64
    with pytest.raises(ValidationError, match="record fingerprint"):
        contract.WorkerQueueReservationV1.model_validate(raw)


def test_ownership_permission_and_linkage_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["permission"] = "installation.execution.worker_admission_stub.record"
    with pytest.raises(ValidationError):
        WorkerQueueReservationValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["authenticated_operator_id"] = "operator-b"
    with pytest.raises(ValidationError, match="ownership"):
        WorkerQueueReservationValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["worker_admission_stub_fingerprint"]["value"] = "c" * 64
    with pytest.raises(ValidationError, match="stub linkage"):
        WorkerQueueReservationValidationInputV1.model_validate(raw)


def test_stale_expired_default_disabled_and_home_assistant(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["authority"]["request_received_at"] = "2026-08-27T12:01:20Z"
    with pytest.raises(ValidationError, match="stale|expired"):
        WorkerQueueReservationValidationInputV1.model_validate(raw)
    raw = _input(tmp_path).model_dump(mode="python")
    raw["boundary_enabled"] = True
    with pytest.raises(ValidationError):
        WorkerQueueReservationValidationInputV1.model_validate(raw)
    with pytest.raises(ValidationError, match="Home Assistant"):
        _input(tmp_path, home_assistant=True)


def test_inherited_ceiling_and_reference_fail_closed(tmp_path: Path) -> None:
    raw = _input(tmp_path).model_dump(mode="python")
    raw["create"]["inherited_limits_fingerprint"]["value"] = "d" * 64
    with pytest.raises(ValidationError, match="limits"):
        WorkerQueueReservationValidationInputV1.model_validate(raw)
    intake = _input(tmp_path).queue_intake_reference.model_dump(mode="python")
    intake["eligibility"] = "live"
    with pytest.raises(ValidationError):
        QueueIntakeReferenceV1.model_validate(intake)


def test_status_lifecycle_and_closed_readiness_states(tmp_path: Path) -> None:
    record, _, _ = build_reservation(_input(tmp_path), reservation_id=RESERVATION_ID)
    assert derive_status(record, observed_at=record.recorded_at).lifecycle == "active"
    assert derive_status(record, observed_at=record.valid_until).lifecycle == "expired"
    raw = derive_status(record, observed_at=record.recorded_at).model_dump(mode="python")
    raw["eligibility"] = "ready_to_enqueue"
    with pytest.raises(ValidationError):
        contract.WorkerQueueReservationStatusV1.model_validate(raw)


def test_redacted_error_and_result_shape() -> None:
    error = WorkerQueueReservationRedactedErrorV1(
        error_code="not_eligible",
        correlation_fingerprint=opaque_fingerprint(
            "atlas:test:queue-correlation:v1", "blocked"
        ),
    )
    result = WorkerQueueReservationResultV1(
        disposition="blocked", reservation=None, status=None,
        audit_evidence=None, error=error,
    )
    assert result.error.message == contract.SAFE_MESSAGE
    assert result.error.redacted and not result.execution_start_allowed
    raw = result.model_dump(mode="python")
    raw["error"]["message"] = "secret=/internal/path"
    with pytest.raises(ValidationError):
        WorkerQueueReservationResultV1.model_validate(raw)


def test_idempotency_shape_is_hashed_and_permanent(tmp_path: Path) -> None:
    _, idem, permanent = build_reservation(_input(tmp_path), reservation_id=RESERVATION_ID)
    assert "worker-queue-reservation-key-1" not in idem.model_dump_json()
    assert idem.permanent and not idem.raw_key_persisted
    assert permanent.permanent and not permanent.consumed
    raw = permanent.model_dump(mode="python")
    raw["released"] = True
    with pytest.raises(ValidationError):
        contract.WorkerQueueSubjectReservationV1.model_validate(raw)


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
        "atlas_execution_worker", "agent", "dispatch", "docker", "provider",
        "repository", "requests", "socket", "subprocess", "workflow",
    )
    assert not [name for name in imports if any(term in name for term in forbidden)]
    source = path.read_text(encoding="utf-8").lower()
    for call in (
        "subprocess.", "os.system", "create_subprocess", ".enqueue(",
        ".dequeue(", ".dispatch(", ".start_worker(", ".execute(",
        ".invoke_agent(",
    ):
        assert call not in source
