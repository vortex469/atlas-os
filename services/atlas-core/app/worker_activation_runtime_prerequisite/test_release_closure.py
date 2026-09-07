"""v0.53 release locks: durable predecessor lineage and exact evidence consumers."""

from datetime import datetime
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from app.controlled_worker_queue_claim_lease_acknowledgement.test_service_store import (
    _record,
)
from app.controlled_worker_queue_claim_lease_acknowledgement.test_service_store import (
    _service as prior_service,
)
from app.worker_activation_runtime_prerequisite import contract as c
from app.worker_activation_runtime_prerequisite.readers import (
    WorkerActivationRuntimePrerequisiteReceiptStoreReader,
)
from app.worker_activation_runtime_prerequisite.service import (
    WorkerActivationRuntimePrerequisiteService,
)
from app.worker_activation_runtime_prerequisite.store import (
    WorkerActivationRuntimePrerequisiteStore,
)

ROOT = Path(__file__).resolve().parents[4]


def test_durable_v052_to_v053_lineage_and_restart_no_replay(tmp_path):
    prior, prior_store, _, _, admission, _, _, request = prior_service(tmp_path)
    # Use the actual durable v0.52 service/store, not a successor reader stub.
    receipt = _record(prior, admission, request).record

    def clock():
        return datetime.fromisoformat(receipt.recorded_at)

    reader = WorkerActivationRuntimePrerequisiteReceiptStoreReader(
        store=type(prior_store)(prior_store.database_path), clock=clock
    )
    pair = reader.read_owned(
        operator_id=receipt.operator_id,
        candidate_record_id=receipt.candidate_record_id,
        admission_id=receipt.admission_id,
        valid_until=receipt.valid_until,
    )
    create = c.build_create(receipt=pair[0], receipt_status=pair[1])
    store = WorkerActivationRuntimePrerequisiteStore(tmp_path / "v053.sqlite")
    service = WorkerActivationRuntimePrerequisiteService(
        receipt_reader=reader, store=store, clock=clock, enabled=True
    )
    arguments = {
        "authenticated_operator_id": receipt.operator_id,
        "permission_verified": True,
        "candidate_record_id": receipt.candidate_record_id,
        "idempotency_key": "v053-release-closure",
        "correlation_id": "release-closure",
    }
    result = service.create(create, **arguments)
    assert isinstance(result, c.WorkerActivationRuntimePrerequisiteResultV1)
    record = result.record
    assert record.admission_id == receipt.admission_id
    assert record.operator_id == receipt.operator_id
    assert record.candidate_record_id == receipt.candidate_record_id
    assert record.valid_until == receipt.valid_until
    # Byte-exact recursive evidence includes every inherited ID, limit and hash.
    assert (
        record.controlled_worker_queue_claim_lease_acknowledgement.model_dump_json()
        == receipt.model_dump_json()
    )
    assert record.controlled_worker_queue_claim_lease_acknowledgement_status == pair[1]
    assert create.receipt_record_fingerprint == receipt.receipt_record_fingerprint
    assert create.status_fingerprint == pair[1].status_fingerprint
    assert record.blockers == c.SUCCESS_BLOCKERS == c.v052.SUCCESS_BLOCKERS
    for model in (record, result.status, result):
        for name, field in type(model).model_fields.items():
            if get_origin(field.annotation) is Literal and get_args(field.annotation)[0] is False:
                assert getattr(model, name) is False
                for invalid in (True, 0, 1, "false"):
                    with pytest.raises(ValidationError):
                        type(model).model_validate_json(
                            model.model_copy(update={name: invalid}).model_dump_json()
                        )

    def no_read(**_kwargs):
        pytest.fail("historical duplicate must not consume its predecessor again")

    reader.read_owned = no_read
    restarted = WorkerActivationRuntimePrerequisiteService(
        receipt_reader=reader,
        store=WorkerActivationRuntimePrerequisiteStore(store.database_path),
        clock=lambda: datetime.fromisoformat(receipt.valid_until),
        enabled=True,
    )
    duplicate = restarted.create(create, **arguments)
    assert duplicate.exact_duplicate and duplicate.record == record
    assert duplicate.status.lifecycle == "expired"
    replay = restarted.create(create, **{**arguments, "idempotency_key": "another-release-key"})
    assert replay.error_code == "permanent_subject_reserved"
    assert replay.retryable is False


def test_exact_v053_production_consumers():
    markers = (
        "worker_activation_runtime_prerequisite",
        "worker-activation-runtime-prerequisite",
        "workerActivationRuntimePrerequisite",
        "WorkerActivationRuntimePrerequisite",
        "WORKER_ACTIVATION_RUNTIME_PREREQUISITE",
    )
    expected = {
        "services/atlas-core/app/worker_activation_runtime_admission/contract.py",
        "services/atlas-core/app/worker_activation_runtime_prerequisite/contract.py",
        "services/atlas-core/app/worker_activation_runtime_prerequisite/readers.py",
        "services/atlas-core/app/worker_activation_runtime_prerequisite/service.py",
        "services/atlas-core/app/worker_activation_runtime_prerequisite/store.py",
        "services/atlas-core/app/routes/worker_activation_runtime_prerequisite.py",
        "services/atlas-core/app/api/v1/router.py",
        "services/atlas-core/app/operator_auth/models.py",
        "services/mission-control/src/api/workerActivationRuntimePrerequisite.ts",
        "services/mission-control/src/types/workerActivationRuntimePrerequisite.ts",
        "services/mission-control/src/features/installation/WorkerActivationRuntimePrerequisite.tsx",
        "services/mission-control/src/features/installation/ControlledWorkerQueueReceipt.tsx",
    }
    found = set()
    for area in (
        "services/atlas-core/app",
        "services/atlas-agent/app",
        "services/atlas-execution-worker/atlas_execution_worker",
        "services/mission-control/src",
    ):
        assert (ROOT / area).is_dir()
        for path in (ROOT / area).rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".json", ".yaml", ".yml"}:
                continue
            if path.name.startswith("test_") or ".test." in path.name or "test" in path.parts:
                continue
            if any(marker in path.read_text() for marker in markers):
                found.add(path.relative_to(ROOT).as_posix())
    assert found == expected
