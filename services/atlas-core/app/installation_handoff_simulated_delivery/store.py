"""Append-only Core evidence stores for simulated handoff delivery.

The stores reserve simulation identities and preserve inert evidence only.  They
do not transport a handoff or grant admission, execution, or mutation authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import TypeAdapter

from app.installation_handoff_simulated_delivery.contract import (
    MAX_ACKNOWLEDGEMENT_BYTES,
    MAX_RECORD_BYTES,
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    IdempotencyKey,
    InstallationHandoffSimulatedDeliveryRecordV1,
    InstallationHandoffSimulatedDeliveryV1,
    OperatorId,
    acknowledgement_fingerprint,
    build_delivery_record,
    delivery_lifecycle,
    delivery_record_fingerprint,
    validate_acknowledgement,
    validate_simulated_delivery,
)

MAX_RETAINED_RECORDS_PER_OPERATOR = 16


class SimulatedHandoffStoreError(RuntimeError):
    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class SimulatedHandoffMalformedError(SimulatedHandoffStoreError):
    code = "malformed"


class SimulatedHandoffNotFoundError(SimulatedHandoffStoreError):
    code = "unavailable"


class SimulatedHandoffNotCurrentError(SimulatedHandoffStoreError):
    code = "not_current"


class SimulatedHandoffOwnershipError(SimulatedHandoffStoreError):
    code = "ownership_mismatch"


class SimulatedHandoffDeliveryMismatchError(SimulatedHandoffStoreError):
    code = "delivery_mismatch"


class SimulatedHandoffEnvelopeMismatchError(SimulatedHandoffStoreError):
    code = "envelope_mismatch"


class SimulatedHandoffLinkageMismatchError(SimulatedHandoffStoreError):
    code = "linkage_mismatch"


class SimulatedHandoffIntakeMismatchError(SimulatedHandoffStoreError):
    code = "intake_mismatch"


class SimulatedHandoffReplayConflictError(SimulatedHandoffStoreError):
    code = "replay_conflict"


class SimulatedHandoffQuotaError(SimulatedHandoffStoreError):
    code = "quota_exceeded"


class SimulatedHandoffUnavailableError(SimulatedHandoffStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise SimulatedHandoffUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise SimulatedHandoffUnavailableError()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class InstallationHandoffSimulatedDeliveryStore:
    """Bounded durable attempt and acknowledgement-copy evidence."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = str(database_path)
        self._clock = clock
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS simulated_handoff_attempts (
                        simulated_delivery_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        simulation_request_id TEXT NOT NULL,
                        dispatch_envelope_id TEXT NOT NULL,
                        dispatch_envelope_fingerprint TEXT NOT NULL,
                        simulated_delivery_fingerprint TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        UNIQUE(operator_id, simulation_request_id),
                        UNIQUE(operator_id, dispatch_envelope_id),
                        UNIQUE(operator_id, dispatch_envelope_fingerprint),
                        UNIQUE(operator_id, simulated_delivery_fingerprint)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS simulated_handoff_idempotency (
                        operator_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        simulated_delivery_id TEXT NOT NULL,
                        simulated_delivery_fingerprint TEXT NOT NULL,
                        simulation_request_id TEXT NOT NULL,
                        dispatch_envelope_id TEXT NOT NULL,
                        dispatch_envelope_fingerprint TEXT NOT NULL,
                        PRIMARY KEY(operator_id, key_digest)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS simulated_handoff_acknowledgements (
                        acknowledgement_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        simulated_delivery_id TEXT NOT NULL,
                        simulated_delivery_fingerprint TEXT NOT NULL,
                        acknowledgement_fingerprint TEXT NOT NULL,
                        acknowledgement_json TEXT NOT NULL,
                        UNIQUE(operator_id, simulated_delivery_id),
                        UNIQUE(operator_id, simulated_delivery_fingerprint),
                        UNIQUE(operator_id, acknowledgement_fingerprint)
                    )
                """)
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path, timeout=5, check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _inputs(operator_id: str, idempotency_key: str) -> tuple[str, str]:
        try:
            operator = TypeAdapter(OperatorId).validate_python(operator_id, strict=True)
            key = TypeAdapter(IdempotencyKey).validate_python(
                idempotency_key, strict=True
            )
        except Exception as error:
            raise SimulatedHandoffMalformedError() from error
        digest = hashlib.sha256(
            b"atlas:installation-handoff-simulated-delivery-idempotency:v1\0"
            + key.encode()
        ).hexdigest()
        return operator, digest

    @staticmethod
    def _encode(value: object, maximum: int) -> str:
        try:
            encoded = json.dumps(
                value.model_dump(mode="json"),  # type: ignore[attr-defined]
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except Exception as error:
            raise SimulatedHandoffMalformedError() from error
        if len(encoded.encode()) > maximum:
            raise SimulatedHandoffQuotaError()
        return encoded

    @staticmethod
    def _decode_record(row: sqlite3.Row) -> InstallationHandoffSimulatedDeliveryRecordV1:
        try:
            raw = row["record_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_RECORD_BYTES:
                raise ValueError
            record = InstallationHandoffSimulatedDeliveryRecordV1.model_validate_json(raw)
            if (
                record.simulated_delivery_id != row["simulated_delivery_id"]
                or record.simulation_request_id != row["simulation_request_id"]
                or record.dispatch_envelope_id != row["dispatch_envelope_id"]
                or record.dispatch_envelope_fingerprint.value
                != row["dispatch_envelope_fingerprint"]
                or record.simulated_delivery_fingerprint.value
                != row["simulated_delivery_fingerprint"]
                or record.delivery_record_fingerprint
                != delivery_record_fingerprint(
                    operator_id=row["operator_id"], record=record
                )
            ):
                raise ValueError
            return record
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error

    @staticmethod
    def _decode_ack(
        row: sqlite3.Row,
    ) -> AgentInstallationHandoffSimulatedAcknowledgementV1:
        try:
            raw = row["acknowledgement_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_ACKNOWLEDGEMENT_BYTES:
                raise ValueError
            acknowledgement = (
                AgentInstallationHandoffSimulatedAcknowledgementV1.model_validate_json(raw)
            )
            if (
                acknowledgement.acknowledgement_id != row["acknowledgement_id"]
                or acknowledgement.source.simulated_delivery_id
                != row["simulated_delivery_id"]
                or acknowledgement.source.simulated_delivery_fingerprint.value
                != row["simulated_delivery_fingerprint"]
                or acknowledgement.acknowledgement_fingerprint.value
                != row["acknowledgement_fingerprint"]
                or acknowledgement.acknowledgement_fingerprint
                != acknowledgement_fingerprint(
                    operator_id=row["operator_id"], acknowledgement=acknowledgement
                )
            ):
                raise ValueError
            return acknowledgement
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error

    def _replay(
        self,
        connection: sqlite3.Connection,
        operator: str,
        key_digest: str,
        delivery: InstallationHandoffSimulatedDeliveryV1,
    ) -> InstallationHandoffSimulatedDeliveryRecordV1 | None:
        reservation = connection.execute(
            "SELECT * FROM simulated_handoff_idempotency "
            "WHERE operator_id=? AND key_digest=?",
            (operator, key_digest),
        ).fetchone()
        if reservation is None:
            return None
        expected = (
            delivery.simulated_delivery_id,
            delivery.simulated_delivery_fingerprint.value,
            delivery.simulation_request_id,
            delivery.envelope.dispatch_envelope_id,
            delivery.envelope.dispatch_envelope_fingerprint.value,
        )
        actual = tuple(
            reservation[name]
            for name in (
                "simulated_delivery_id",
                "simulated_delivery_fingerprint",
                "simulation_request_id",
                "dispatch_envelope_id",
                "dispatch_envelope_fingerprint",
            )
        )
        if actual != expected:
            raise SimulatedHandoffReplayConflictError()
        row = connection.execute(
            "SELECT * FROM simulated_handoff_attempts "
            "WHERE operator_id=? AND simulated_delivery_id=?",
            (operator, delivery.simulated_delivery_id),
        ).fetchone()
        if row is None:
            raise SimulatedHandoffUnavailableError()
        record = self._decode_record(row)
        if record.simulated_delivery_fingerprint != delivery.simulated_delivery_fingerprint:
            raise SimulatedHandoffUnavailableError()
        return record

    def reserve_attempt(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        delivery: InstallationHandoffSimulatedDeliveryV1,
    ) -> tuple[InstallationHandoffSimulatedDeliveryRecordV1, bool]:
        operator, key_digest = self._inputs(operator_id, idempotency_key)
        try:
            exact = InstallationHandoffSimulatedDeliveryV1.model_validate(
                delivery.model_dump(mode="python")
            )
        except Exception as error:
            raise SimulatedHandoffMalformedError() from error
        try:
            with self._connect() as connection:
                prior = self._replay(connection, operator, key_digest, exact)
            if prior is not None:
                return prior, False
        except SimulatedHandoffStoreError:
            raise
        except Exception as error:
            raise self._validation_error(error) from error

        try:
            validate_simulated_delivery(
                exact, operator_id=operator, now=exact.dispatched_at
            )
        except Exception as error:
            raise self._validation_error(error) from error
        observed_at = _instant(self._clock)
        if observed_at != exact.dispatched_at:
            raise SimulatedHandoffNotCurrentError()
        try:
            record = build_delivery_record(operator_id=operator, delivery=exact)
            encoded = self._encode(record, MAX_RECORD_BYTES)
        except SimulatedHandoffStoreError:
            raise
        except Exception as error:
            raise self._validation_error(error) from error
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = self._replay(connection, operator, key_digest, exact)
                if prior is not None:
                    return prior, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM simulated_handoff_attempts WHERE operator_id=?",
                    (operator,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    raise SimulatedHandoffQuotaError()
                connection.execute(
                    "INSERT INTO simulated_handoff_attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.simulated_delivery_id,
                        operator,
                        record.simulation_request_id,
                        record.dispatch_envelope_id,
                        record.dispatch_envelope_fingerprint.value,
                        record.simulated_delivery_fingerprint.value,
                        encoded,
                    ),
                )
                connection.execute(
                    "INSERT INTO simulated_handoff_idempotency VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        operator,
                        key_digest,
                        record.simulated_delivery_id,
                        record.simulated_delivery_fingerprint.value,
                        record.simulation_request_id,
                        record.dispatch_envelope_id,
                        record.dispatch_envelope_fingerprint.value,
                    ),
                )
                return record, True
        except SimulatedHandoffStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise SimulatedHandoffReplayConflictError() from error
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error

    @staticmethod
    def _validation_error(error: Exception) -> SimulatedHandoffStoreError:
        detail = str(error)
        if "ownership" in detail:
            return SimulatedHandoffOwnershipError()
        if "current" in detail or "precedes" in detail or "time" in detail:
            return SimulatedHandoffNotCurrentError()
        if "envelope" in detail:
            return SimulatedHandoffEnvelopeMismatchError()
        if "linkage" in detail:
            return SimulatedHandoffLinkageMismatchError()
        return SimulatedHandoffDeliveryMismatchError()

    def preserve_acknowledgement(
        self,
        *,
        operator_id: str,
        delivery: InstallationHandoffSimulatedDeliveryV1,
        acknowledgement: AgentInstallationHandoffSimulatedAcknowledgementV1,
    ) -> tuple[AgentInstallationHandoffSimulatedAcknowledgementV1, bool]:
        operator, _ = self._inputs(operator_id, "preserve")
        try:
            validate_acknowledgement(
                operator_id=operator,
                delivery=delivery,
                acknowledgement=acknowledgement,
            )
            if acknowledgement.acknowledged_at > _instant(self._clock):
                raise SimulatedHandoffNotCurrentError()
            encoded = self._encode(acknowledgement, MAX_ACKNOWLEDGEMENT_BYTES)
        except SimulatedHandoffStoreError:
            raise
        except Exception as error:
            detail = str(error)
            if "intake" in detail:
                raise SimulatedHandoffIntakeMismatchError() from error
            if "current" in detail or "precedes" in detail or "expiry" in detail:
                raise SimulatedHandoffNotCurrentError() from error
            if "ownership" in detail or "fingerprint" in detail:
                raise SimulatedHandoffOwnershipError() from error
            raise SimulatedHandoffDeliveryMismatchError() from error
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                attempt = connection.execute(
                    "SELECT * FROM simulated_handoff_attempts "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, delivery.simulated_delivery_id),
                ).fetchone()
                if attempt is None:
                    raise SimulatedHandoffUnavailableError()
                self._decode_record(attempt)
                prior = connection.execute(
                    "SELECT * FROM simulated_handoff_acknowledgements "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, delivery.simulated_delivery_id),
                ).fetchone()
                if prior is not None:
                    exact = self._decode_ack(prior)
                    if exact != acknowledgement:
                        raise SimulatedHandoffReplayConflictError()
                    return exact, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM simulated_handoff_acknowledgements "
                    "WHERE operator_id=?",
                    (operator,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    raise SimulatedHandoffQuotaError()
                connection.execute(
                    "INSERT INTO simulated_handoff_acknowledgements VALUES "
                    "(?, ?, ?, ?, ?, ?)",
                    (
                        acknowledgement.acknowledgement_id,
                        operator,
                        delivery.simulated_delivery_id,
                        delivery.simulated_delivery_fingerprint.value,
                        acknowledgement.acknowledgement_fingerprint.value,
                        encoded,
                    ),
                )
                return acknowledgement, True
        except SimulatedHandoffStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise SimulatedHandoffReplayConflictError() from error
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error

    def get_attempt(
        self, *, operator_id: str, simulated_delivery_id: str
    ) -> InstallationHandoffSimulatedDeliveryRecordV1:
        operator, _ = self._inputs(operator_id, "read")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM simulated_handoff_attempts "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, simulated_delivery_id),
                ).fetchone()
            if row is None:
                raise SimulatedHandoffNotFoundError()
            return self._decode_record(row)
        except SimulatedHandoffStoreError:
            raise
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error

    def get_acknowledgement(
        self, *, operator_id: str, simulated_delivery_id: str
    ) -> AgentInstallationHandoffSimulatedAcknowledgementV1 | None:
        operator, _ = self._inputs(operator_id, "read")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM simulated_handoff_acknowledgements "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, simulated_delivery_id),
                ).fetchone()
            return None if row is None else self._decode_ack(row)
        except SimulatedHandoffStoreError:
            raise
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error

    def lifecycle(self, *, operator_id: str, simulated_delivery_id: str) -> str:
        record = self.get_attempt(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )
        acknowledgement = self.get_acknowledgement(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )
        try:
            return delivery_lifecycle(
                record, now=_instant(self._clock), acknowledgement=acknowledgement
            )
        except Exception as error:
            raise SimulatedHandoffUnavailableError() from error
