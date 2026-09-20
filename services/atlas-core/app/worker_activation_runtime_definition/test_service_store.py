from datetime import UTC, datetime

from . import contract as c
from .service import WorkerActivationRuntimeDefinitionService
from .store import WorkerActivationRuntimeDefinitionStore
from .test_contract import definition


class Reader:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def read_owned(self, *, operator_id, definition_id):
        self.calls += 1
        return self.value


def _create(value):
    return c.WorkerActivationRuntimeDefinitionCreateV1(
        definition_id=value.definition_id,
        definition_fingerprint=value.definition_fingerprint,
        valid_until=value.valid_until,
    )


def test_default_off_and_restart_safe_idempotency(tmp_path):
    value = definition()
    reader = Reader(value)
    store = WorkerActivationRuntimeDefinitionStore(tmp_path / "definitions.sqlite")
    clock = lambda: datetime(2026, 1, 1, tzinfo=UTC)
    service = WorkerActivationRuntimeDefinitionService(
        definition_reader=reader, store=store, clock=clock
    )
    disabled = service.create(
        _create(value),
        authenticated_operator_id=value.operator_id,
        permission_verified=True,
        candidate_record_id=value.candidate_record_id,
        idempotency_key="one",
        correlation_id="private",
    )
    assert disabled.error_code == "installation_capability_unsupported"
    service = WorkerActivationRuntimeDefinitionService(
        definition_reader=reader, store=store, clock=clock, enabled=True
    )
    first = service.create(
        _create(value),
        authenticated_operator_id=value.operator_id,
        permission_verified=True,
        candidate_record_id=value.candidate_record_id,
        idempotency_key="one",
        correlation_id="private",
    )
    assert isinstance(first, c.WorkerActivationRuntimeDefinitionResultV1)
    restarted = WorkerActivationRuntimeDefinitionService(
        definition_reader=Reader(value),
        store=WorkerActivationRuntimeDefinitionStore(store.database_path),
        clock=clock,
        enabled=True,
    )
    duplicate = restarted.create(
        _create(value),
        authenticated_operator_id=value.operator_id,
        permission_verified=True,
        candidate_record_id=value.candidate_record_id,
        idempotency_key="one",
        correlation_id="private",
    )
    assert duplicate.exact_duplicate is True
    assert duplicate.record == first.record


def test_subject_reservation_is_permanent(tmp_path):
    value = definition()
    store = WorkerActivationRuntimeDefinitionStore(tmp_path / "definitions.sqlite")
    service = WorkerActivationRuntimeDefinitionService(
        definition_reader=Reader(value),
        store=store,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        enabled=True,
    )
    common = {
        "authenticated_operator_id": value.operator_id,
        "permission_verified": True,
        "candidate_record_id": value.candidate_record_id,
        "correlation_id": "private",
    }
    assert isinstance(
        service.create(_create(value), idempotency_key="one", **common),
        c.WorkerActivationRuntimeDefinitionResultV1,
    )
    conflict = service.create(_create(value), idempotency_key="two", **common)
    assert conflict.error_code == "permanent_subject_reserved"
