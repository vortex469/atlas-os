"""Owner-scoped durable v0.52 evidence readback, with no adapter or worker reader."""

from datetime import timedelta

from app.controlled_worker_queue_claim_lease_acknowledgement import contract as v052
from app.controlled_worker_queue_claim_lease_acknowledgement.store import (
    ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
)

from .service import server_now
from .store import WorkerActivationRuntimePrerequisiteStoreError


class WorkerActivationRuntimePrerequisiteReceiptStoreReader:
    def __init__(self, *, store, clock):
        self._store = store
        self._clock = clock

    def read_owned(
        self, *, operator_id, candidate_record_id, admission_id, valid_until
    ):
        try:
            record = self._store.get(operator_id=operator_id, admission_id=admission_id)
            record = v052.ControlledWorkerQueueClaimLeaseAcknowledgementV1.model_validate_json(
                record.model_dump_json()
            )
            now = server_now(self._clock)
            if (
                record.operator_id != operator_id
                or record.candidate_record_id != candidate_record_id
                or record.admission_id != admission_id
                or record.valid_until != valid_until
                or not record.recorded_at <= now < record.valid_until
                or v052._instant(now) - v052._instant(record.recorded_at)
                > timedelta(seconds=30)
            ):
                return None
            return record, v052.derive_status(record, evaluated_at=record.recorded_at)
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError as error:
            if error.code == "not_found":
                return None
            raise WorkerActivationRuntimePrerequisiteStoreError(
                "store_corrupt" if error.code == "store_corrupt" else "unavailable"
            ) from None
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            raise WorkerActivationRuntimePrerequisiteStoreError(
                "store_corrupt"
            ) from None
