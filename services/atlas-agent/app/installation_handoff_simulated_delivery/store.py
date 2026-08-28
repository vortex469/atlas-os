"""Bounded append-only Agent evidence for simulated handoff acknowledgements."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import TypeAdapter

from app.agent_intake_simulation.models import OperatorId, intake_record_fingerprint

from .models import (
    MAX_ACKNOWLEDGEMENT_BYTES,
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    InstallationHandoffSimulatedDeliveryV1,
    acknowledgement_fingerprint,
    acknowledgement_lifecycle,
    build_acknowledgement,
    validate_simulated_delivery,
)

MAX_RETAINED_RECORDS_PER_OPERATOR = 16


class SimulatedAcknowledgementStoreError(RuntimeError):
    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class SimulatedAcknowledgementMalformedError(SimulatedAcknowledgementStoreError):
    code = "malformed"


class SimulatedAcknowledgementNotCurrentError(SimulatedAcknowledgementStoreError):
    code = "not_current"


class SimulatedAcknowledgementOwnershipError(SimulatedAcknowledgementStoreError):
    code = "ownership_mismatch"


class SimulatedAcknowledgementDeliveryMismatchError(SimulatedAcknowledgementStoreError):
    code = "delivery_mismatch"


class SimulatedAcknowledgementIntakeMismatchError(SimulatedAcknowledgementStoreError):
    code = "intake_mismatch"


class SimulatedAcknowledgementReplayConflictError(SimulatedAcknowledgementStoreError):
    code = "replay_conflict"


class SimulatedAcknowledgementQuotaError(SimulatedAcknowledgementStoreError):
    code = "quota_exceeded"


class SimulatedAcknowledgementUnavailableError(SimulatedAcknowledgementStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise SimulatedAcknowledgementUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise SimulatedAcknowledgementUnavailableError()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentSimulatedAcknowledgementStore:
    """Atomically reserve all v0.25/v0.26 identities and preserve one value."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self.database_path = str(database_path)
        self._clock = clock
        self._id_factory = id_factory
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS agent_simulated_acknowledgements (
                        acknowledgement_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        simulated_delivery_id TEXT NOT NULL,
                        simulated_delivery_fingerprint TEXT NOT NULL,
                        acknowledgement_fingerprint TEXT NOT NULL,
                        simulation_request_id TEXT NOT NULL,
                        intake_record_id TEXT NOT NULL,
                        intake_record_fingerprint TEXT NOT NULL,
                        dispatch_envelope_id TEXT NOT NULL,
                        dispatch_envelope_fingerprint TEXT NOT NULL,
                        acknowledgement_json TEXT NOT NULL,
                        UNIQUE(operator_id, simulated_delivery_id),
                        UNIQUE(operator_id, simulated_delivery_fingerprint),
                        UNIQUE(operator_id, acknowledgement_fingerprint),
                        UNIQUE(operator_id, simulation_request_id),
                        UNIQUE(operator_id, intake_record_id),
                        UNIQUE(operator_id, intake_record_fingerprint),
                        UNIQUE(operator_id, dispatch_envelope_id),
                        UNIQUE(operator_id, dispatch_envelope_fingerprint)
                    )
                """)
        except Exception as error:
            raise SimulatedAcknowledgementUnavailableError() from error
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
    def _operator(operator_id: str) -> str:
        try:
            return TypeAdapter(OperatorId).validate_python(operator_id, strict=True)
        except Exception as error:
            raise SimulatedAcknowledgementMalformedError() from error

    @staticmethod
    def _encode(value: AgentInstallationHandoffSimulatedAcknowledgementV1) -> str:
        try:
            encoded = json.dumps(
                value.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except Exception as error:
            raise SimulatedAcknowledgementMalformedError() from error
        if len(encoded.encode()) > MAX_ACKNOWLEDGEMENT_BYTES:
            raise SimulatedAcknowledgementQuotaError()
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> AgentInstallationHandoffSimulatedAcknowledgementV1:
        try:
            raw = row["acknowledgement_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_ACKNOWLEDGEMENT_BYTES:
                raise ValueError
            value = (
                AgentInstallationHandoffSimulatedAcknowledgementV1.model_validate_json(
                    raw
                )
            )
            columns = (
                value.acknowledgement_id,
                value.source.simulated_delivery_id,
                value.source.simulated_delivery_fingerprint.value,
                value.acknowledgement_fingerprint.value,
                value.intake.simulation_request_id,
                value.intake.intake_record_id,
                value.intake.intake_record_fingerprint.value,
                value.source.dispatch_envelope_id,
                value.source.dispatch_envelope_fingerprint.value,
            )
            stored = tuple(
                row[name]
                for name in (
                    "acknowledgement_id",
                    "simulated_delivery_id",
                    "simulated_delivery_fingerprint",
                    "acknowledgement_fingerprint",
                    "simulation_request_id",
                    "intake_record_id",
                    "intake_record_fingerprint",
                    "dispatch_envelope_id",
                    "dispatch_envelope_fingerprint",
                )
            )
            if (
                columns != stored
                or value.acknowledgement_fingerprint
                != acknowledgement_fingerprint(
                    operator_id=row["operator_id"], acknowledgement=value
                )
            ):
                raise ValueError
            return value
        except Exception as error:
            raise SimulatedAcknowledgementUnavailableError() from error

    @staticmethod
    def _matches_delivery(
        value: AgentInstallationHandoffSimulatedAcknowledgementV1,
        delivery: InstallationHandoffSimulatedDeliveryV1,
    ) -> bool:
        return (
            value.source.simulated_delivery_id == delivery.simulated_delivery_id
            and value.source.simulated_delivery_fingerprint
            == delivery.simulated_delivery_fingerprint
            and value.source.dispatch_envelope_id
            == delivery.envelope.dispatch_envelope_id
            and value.source.dispatch_envelope_fingerprint
            == delivery.envelope.dispatch_envelope_fingerprint
            and value.intake.simulation_request_id == delivery.simulation_request_id
        )

    def find_for_delivery(
        self, *, operator_id: str, delivery: InstallationHandoffSimulatedDeliveryV1
    ) -> AgentInstallationHandoffSimulatedAcknowledgementV1 | None:
        operator = self._operator(operator_id)
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM agent_simulated_acknowledgements "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, delivery.simulated_delivery_id),
                ).fetchone()
            if row is None:
                return None
            value = self._decode(row)
            if not self._matches_delivery(value, delivery):
                raise SimulatedAcknowledgementReplayConflictError()
            return value
        except SimulatedAcknowledgementStoreError:
            raise
        except Exception as error:
            raise SimulatedAcknowledgementUnavailableError() from error

    def preserve(
        self,
        *,
        operator_id: str,
        delivery: InstallationHandoffSimulatedDeliveryV1,
        intake_record: object,
    ) -> tuple[AgentInstallationHandoffSimulatedAcknowledgementV1, bool]:
        operator = self._operator(operator_id)
        try:
            validate_simulated_delivery(
                delivery,
                operator_id=operator,
                observed_at=intake_record.observed_at,  # type: ignore[attr-defined]
            )
            if intake_record.intake_record_fingerprint != intake_record_fingerprint(  # type: ignore[attr-defined]
                operator_id=operator, record=intake_record
            ):
                raise ValueError("intake record fingerprint mismatch")
            now = _instant(self._clock)
            if intake_record.observed_at > now:  # type: ignore[attr-defined]
                raise SimulatedAcknowledgementNotCurrentError()
        except SimulatedAcknowledgementStoreError:
            raise
        except Exception as error:
            detail = str(error)
            if "ownership" in detail:
                raise SimulatedAcknowledgementOwnershipError() from error
            if "current" in detail or "precedes" in detail:
                raise SimulatedAcknowledgementNotCurrentError() from error
            if "intake" in detail or "linkage" in detail:
                raise SimulatedAcknowledgementIntakeMismatchError() from error
            raise SimulatedAcknowledgementDeliveryMismatchError() from error

        prior = self.find_for_delivery(operator_id=operator, delivery=delivery)
        if prior is not None:
            return prior, False
        try:
            acknowledgement_id = str(self._id_factory())
            value = build_acknowledgement(
                operator_id=operator,
                delivery=delivery,
                intake_record=intake_record,
                acknowledgement_id=acknowledgement_id,
            )
            encoded = self._encode(value)
        except SimulatedAcknowledgementStoreError:
            raise
        except Exception as error:
            raise SimulatedAcknowledgementIntakeMismatchError() from error
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM agent_simulated_acknowledgements "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, delivery.simulated_delivery_id),
                ).fetchone()
                if row is not None:
                    prior = self._decode(row)
                    if not self._matches_delivery(prior, delivery):
                        raise SimulatedAcknowledgementReplayConflictError()
                    return prior, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM agent_simulated_acknowledgements WHERE operator_id=?",
                    (operator,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    raise SimulatedAcknowledgementQuotaError()
                connection.execute(
                    "INSERT INTO agent_simulated_acknowledgements VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        value.acknowledgement_id,
                        operator,
                        value.source.simulated_delivery_id,
                        value.source.simulated_delivery_fingerprint.value,
                        value.acknowledgement_fingerprint.value,
                        value.intake.simulation_request_id,
                        value.intake.intake_record_id,
                        value.intake.intake_record_fingerprint.value,
                        value.source.dispatch_envelope_id,
                        value.source.dispatch_envelope_fingerprint.value,
                        encoded,
                    ),
                )
                return value, True
        except SimulatedAcknowledgementStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise SimulatedAcknowledgementReplayConflictError() from error
        except Exception as error:
            raise SimulatedAcknowledgementUnavailableError() from error

    def get(
        self, *, operator_id: str, simulated_delivery_id: str
    ) -> AgentInstallationHandoffSimulatedAcknowledgementV1:
        operator = self._operator(operator_id)
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM agent_simulated_acknowledgements "
                    "WHERE operator_id=? AND simulated_delivery_id=?",
                    (operator, simulated_delivery_id),
                ).fetchone()
            if row is None:
                raise SimulatedAcknowledgementUnavailableError()
            return self._decode(row)
        except SimulatedAcknowledgementStoreError:
            raise
        except Exception as error:
            raise SimulatedAcknowledgementUnavailableError() from error

    def lifecycle(self, *, operator_id: str, simulated_delivery_id: str) -> str:
        value = self.get(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )
        try:
            return acknowledgement_lifecycle(value, now=_instant(self._clock))
        except Exception as error:
            raise SimulatedAcknowledgementUnavailableError() from error
