"""Explicit, owner-scoped readback of the sole durable v0.51 prerequisite."""

from collections.abc import Callable
from datetime import UTC, datetime

from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
    derive_status,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.store import (
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStore,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStoreError,
)

from .store import ControlledWorkerQueueClaimLeaseAcknowledgementStoreError


class ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStoreReader:
    """Return a stable recorded-time status only while the admission is active.

    The stable status preserves exact prerequisite fingerprints between preview
    and write. Freshness/expiry are independently checked against the Core clock
    here and by the P1 validator at the service's reservation boundary.
    """

    def __init__(
        self,
        *,
        store: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStore,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._clock = clock

    def read_owned(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        admission_id: str,
        admission_valid_until: str,
    ) -> (
        tuple[
            ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
            ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1,
        ]
        | None
    ):
        try:
            record = self._store.get(operator_id=operator_id, admission_id=admission_id)
            record = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1.model_validate_json(
                record.model_dump_json()
            )
            if (
                record.operator_id != operator_id
                or record.candidate_record_id != candidate_record_id
                or record.admission_id != admission_id
                or record.valid_until != admission_valid_until
            ):
                return None
            instant = self._clock()
            if (
                instant.tzinfo is None
                or instant.utcoffset() is None
                or instant.microsecond
            ):
                raise ValueError("invalid clock")
            now = instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            if not record.recorded_at <= now < record.valid_until:
                return None
            return record, derive_status(record, evaluated_at=record.recorded_at)
        except (
            ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStoreError
        ) as error:
            if error.code == "not_found":
                return None
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt" if error.code == "store_corrupt" else "unavailable"
            ) from None
        except Exception:  # noqa: BLE001 - prerequisite details remain internal
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            ) from None
