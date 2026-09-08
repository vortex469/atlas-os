"""Owner-scoped durable v0.54 evidence readback, with no adapter or worker reader."""

from datetime import timedelta

from app.worker_activation_runtime_admission import contract as v054
from app.worker_activation_runtime_admission.store import (
    WorkerActivationRuntimeAdmissionStoreError,
)

from . import contract as c
from .service import server_now
from .store import WorkerActivationRuntimePlanStoreError


class WorkerActivationRuntimePlanPrerequisiteStoreReader:
    def __init__(self, *, store, clock):
        self._store = store
        self._clock = clock

    def read_owned(
        self, *, operator_id, candidate_record_id, runtime_admission_id, valid_until
    ):
        try:
            record = self._store.get(
                operator_id=operator_id,
                candidate_record_id=candidate_record_id,
                runtime_admission_id=runtime_admission_id,
            )
            record = v054.WorkerActivationRuntimeAdmissionV1.model_validate(
                c._strict_literals(
                    v054.WorkerActivationRuntimeAdmissionV1, c._plain(record)
                )
            )
            now = server_now(self._clock)
            if (
                record.operator_id != operator_id
                or record.candidate_record_id != candidate_record_id
                or record.runtime_admission_id != runtime_admission_id
                or record.valid_until != valid_until
                or not record.recorded_at <= now < record.valid_until
                or v054.v053.v052._instant(now)
                - v054.v053.v052._instant(record.recorded_at)
                > timedelta(seconds=30)
            ):
                return None
            return record, v054.derive_status(record, evaluated_at=record.recorded_at)
        except WorkerActivationRuntimeAdmissionStoreError as error:
            if error.code == "evidence_not_found":
                return None
            raise WorkerActivationRuntimePlanStoreError(
                "store_corrupt" if error.code == "store_corrupt" else "unavailable"
            ) from None
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            raise WorkerActivationRuntimePlanStoreError("store_corrupt") from None
