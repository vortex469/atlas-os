"""Owner-scoped durable v0.56 evidence readback, with no adapter or worker reader."""

from datetime import timedelta

from app.worker_activation_runtime_plan_review import contract as v056
from app.worker_activation_runtime_plan_review.store import (
    WorkerActivationRuntimePlanReviewStoreError,
)

from . import contract as c
from .service import server_now
from .store import WorkerActivationRuntimeInterfacePrerequisiteStoreError


class WorkerActivationRuntimeInterfacePrerequisiteReviewStoreReader:
    def __init__(self, *, store, clock):
        self._store = store
        self._clock = clock

    def read_owned(
        self, *, operator_id, candidate_record_id, runtime_plan_review_id, valid_until
    ):
        try:
            record = self._store.get(
                operator_id=operator_id,
                candidate_record_id=candidate_record_id,
                runtime_plan_review_id=runtime_plan_review_id,
            )
            record = v056.WorkerActivationRuntimePlanReviewV1.model_validate(
                c._strict_literals(
                    v056.WorkerActivationRuntimePlanReviewV1, c._plain(record)
                )
            )
            now = server_now(self._clock)
            if (
                record.operator_id != operator_id
                or record.candidate_record_id != candidate_record_id
                or record.runtime_plan_review_id != runtime_plan_review_id
                or record.valid_until != valid_until
                or not record.recorded_at <= now < record.valid_until
                or v056.v055.v054.v053.v052._instant(now)
                - v056.v055.v054.v053.v052._instant(record.recorded_at)
                > timedelta(seconds=30)
            ):
                return None
            return record, v056.derive_status(record, evaluated_at=record.recorded_at)
        except WorkerActivationRuntimePlanReviewStoreError as error:
            if error.code == "evidence_not_found":
                return None
            raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                "store_corrupt" if error.code == "store_corrupt" else "unavailable"
            ) from None
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            raise WorkerActivationRuntimeInterfacePrerequisiteStoreError(
                "store_corrupt"
            ) from None
