"""Owner-scoped durable v0.53 evidence readback, with no adapter or worker reader."""

from datetime import timedelta

from app.worker_activation_runtime_prerequisite import contract as v053
from app.worker_activation_runtime_prerequisite.store import (
    WorkerActivationRuntimePrerequisiteStoreError,
)

from .service import server_now
from .store import WorkerActivationRuntimeAdmissionStoreError


class WorkerActivationRuntimeAdmissionPrerequisiteStoreReader:
    def __init__(self, *, store, clock):
        self._store = store
        self._clock = clock

    def read_owned(
        self, *, operator_id, candidate_record_id, prerequisite_id, valid_until
    ):
        try:
            record = self._store.get(
                operator_id=operator_id,
                candidate_record_id=candidate_record_id,
                prerequisite_id=prerequisite_id,
            )
            record = v053.WorkerActivationRuntimePrerequisiteV1.model_validate_json(
                record.model_dump_json()
            )
            now = server_now(self._clock)
            if (
                record.operator_id != operator_id
                or record.candidate_record_id != candidate_record_id
                or record.prerequisite_id != prerequisite_id
                or record.valid_until != valid_until
                or not record.recorded_at <= now < record.valid_until
                or v053.v052._instant(now) - v053.v052._instant(record.recorded_at)
                > timedelta(seconds=30)
            ):
                return None
            return record, v053.derive_status(record, evaluated_at=record.recorded_at)
        except WorkerActivationRuntimePrerequisiteStoreError as error:
            if error.code == "evidence_not_found":
                return None
            raise WorkerActivationRuntimeAdmissionStoreError(
                "store_corrupt" if error.code == "store_corrupt" else "unavailable"
            ) from None
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            raise WorkerActivationRuntimeAdmissionStoreError("store_corrupt") from None
