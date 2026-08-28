"""Bounded durable storage for simulation-only Agent intake evidence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import TypeAdapter

from .models import (
    MAX_RECORD_BYTES,
    AgentInstallationIntakeSimulationCreateV1,
    AgentInstallationIntakeSimulationV1,
    AgentInstallationIntakeSimulationValidationV1,
    IdempotencyKey,
    OperatorId,
    intake_record_fingerprint,
    simulation_create_fingerprint,
    simulation_lifecycle,
    validate_simulated_intake,
    validation_fingerprint,
)

MAX_RETAINED_RECORDS_PER_OPERATOR = 16


class IntakeSimulationStoreError(RuntimeError):
    """A closed store failure whose message is safe to expose as a code."""

    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class IntakeSimulationMalformedError(IntakeSimulationStoreError):
    code = "malformed"


class IntakeSimulationNotFoundError(IntakeSimulationStoreError):
    code = "not_found"


class IntakeSimulationNotCurrentError(IntakeSimulationStoreError):
    code = "not_current"


class IntakeSimulationOwnershipError(IntakeSimulationStoreError):
    code = "ownership_mismatch"


class IntakeSimulationEnvelopeMismatchError(IntakeSimulationStoreError):
    code = "envelope_mismatch"


class IntakeSimulationReplayConflictError(IntakeSimulationStoreError):
    code = "replay_conflict"


class IntakeSimulationQuotaError(IntakeSimulationStoreError):
    code = "quota_exceeded"


class IntakeSimulationUnavailableError(IntakeSimulationStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise IntakeSimulationUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise IntakeSimulationUnavailableError()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentIntakeSimulationStore:
    """Atomically reserve identities and append immutable simulated records."""

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
                    CREATE TABLE IF NOT EXISTS agent_intake_simulations (
                        intake_record_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        simulation_request_id TEXT NOT NULL,
                        dispatch_envelope_id TEXT NOT NULL,
                        dispatch_envelope_fingerprint TEXT NOT NULL,
                        intake_record_fingerprint TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        UNIQUE(operator_id, simulation_request_id),
                        UNIQUE(operator_id, dispatch_envelope_id),
                        UNIQUE(operator_id, dispatch_envelope_fingerprint),
                        UNIQUE(operator_id, intake_record_fingerprint)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS agent_intake_simulation_idempotency (
                        operator_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        intake_record_id TEXT NOT NULL,
                        PRIMARY KEY(operator_id, key_digest)
                    )
                """)
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _inputs(operator_id: str, idempotency_key: str) -> tuple[str, str]:
        try:
            operator = TypeAdapter(OperatorId).validate_python(operator_id, strict=True)
            key = TypeAdapter(IdempotencyKey).validate_python(idempotency_key, strict=True)
        except Exception as error:
            raise IntakeSimulationMalformedError() from error
        digest = hashlib.sha256(
            b"atlas:agent-installation-intake-simulation-idempotency:v1\0"
            + key.encode()
        ).hexdigest()
        return operator, digest

    @staticmethod
    def _encode(record: AgentInstallationIntakeSimulationV1) -> str:
        encoded = json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode()) > MAX_RECORD_BYTES:
            raise IntakeSimulationQuotaError()
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> AgentInstallationIntakeSimulationValidationV1:
        try:
            raw = row["record_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_RECORD_BYTES:
                raise ValueError
            record = AgentInstallationIntakeSimulationV1.model_validate_json(raw)
            if (
                row["operator_id"] is None
                or record.intake_record_id != row["intake_record_id"]
                or record.simulation_request_id != row["simulation_request_id"]
                or record.source.dispatch_envelope_id != row["dispatch_envelope_id"]
                or record.source.dispatch_envelope_fingerprint.value
                != row["dispatch_envelope_fingerprint"]
                or record.intake_record_fingerprint.value != row["intake_record_fingerprint"]
                or intake_record_fingerprint(operator_id=row["operator_id"], record=record)
                != record.intake_record_fingerprint
            ):
                raise ValueError
            validation_raw = {
                "schema": "agent-installation-intake-simulation-validation-v1",
                "observed_at": record.observed_at,
                "status": "simulated_valid",
                "reason_codes": [],
                "capability_status": "unsupported",
                "default_enabled": False,
                "simulation_only": True,
                "delivery_received": False,
                "live_admission_granted": False,
                "execution_authorized": False,
                "worker_allowed": False,
                "mutation_allowed": False,
                "replay_allowed": False,
                "record": record.model_dump(mode="json"),
            }
            validation_raw["validation_fingerprint"] = validation_fingerprint(
                validation_raw
            ).model_dump(mode="json")
            return AgentInstallationIntakeSimulationValidationV1.model_validate(
                validation_raw
            )
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error

    def _replay(
        self, connection: sqlite3.Connection, operator: str, key_digest: str, create_digest: str
    ) -> AgentInstallationIntakeSimulationValidationV1 | None:
        reservation = connection.execute(
            "SELECT * FROM agent_intake_simulation_idempotency "
            "WHERE operator_id=? AND key_digest=?",
            (operator, key_digest),
        ).fetchone()
        if reservation is None:
            return None
        if reservation["create_fingerprint"] != create_digest:
            raise IntakeSimulationReplayConflictError()
        row = connection.execute(
            "SELECT * FROM agent_intake_simulations WHERE operator_id=? AND intake_record_id=?",
            (operator, reservation["intake_record_id"]),
        ).fetchone()
        if row is None or row["create_fingerprint"] != create_digest:
            raise IntakeSimulationUnavailableError()
        return self._decode(row)

    def create(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create: AgentInstallationIntakeSimulationCreateV1,
    ) -> tuple[AgentInstallationIntakeSimulationValidationV1, bool]:
        operator, key_digest = self._inputs(operator_id, idempotency_key)
        try:
            exact = AgentInstallationIntakeSimulationCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            create_digest = simulation_create_fingerprint(exact).value
        except Exception as error:
            raise IntakeSimulationMalformedError() from error
        try:
            with self._connect() as connection:
                prior = self._replay(connection, operator, key_digest, create_digest)
            if prior is not None:
                return prior, False
        except IntakeSimulationStoreError:
            raise
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error

        observed_at = _instant(self._clock)
        try:
            record_id = str(self._id_factory())
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error
        try:
            validation = validate_simulated_intake(
                exact,
                operator_id=operator,
                observed_at=observed_at,
                intake_record_id=record_id,
            )
            encoded = self._encode(validation.record)
        except IntakeSimulationStoreError:
            raise
        except Exception as error:
            detail = str(error)
            if "not current" in detail or "precedes" in detail:
                raise IntakeSimulationNotCurrentError() from error
            if "ownership" in detail:
                raise IntakeSimulationOwnershipError() from error
            raise IntakeSimulationEnvelopeMismatchError() from error

        record = validation.record
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = self._replay(connection, operator, key_digest, create_digest)
                if prior is not None:
                    return prior, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM agent_intake_simulations WHERE operator_id=?",
                    (operator,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    raise IntakeSimulationQuotaError()
                connection.execute(
                    "INSERT INTO agent_intake_simulations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.intake_record_id,
                        operator,
                        create_digest,
                        record.simulation_request_id,
                        record.source.dispatch_envelope_id,
                        record.source.dispatch_envelope_fingerprint.value,
                        record.intake_record_fingerprint.value,
                        encoded,
                    ),
                )
                connection.execute(
                    "INSERT INTO agent_intake_simulation_idempotency VALUES (?, ?, ?, ?)",
                    (operator, key_digest, create_digest, record.intake_record_id),
                )
                return validation, True
        except IntakeSimulationStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise IntakeSimulationReplayConflictError() from error
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error

    def get(
        self, *, operator_id: str, intake_record_id: str
    ) -> AgentInstallationIntakeSimulationV1:
        operator, _ = self._inputs(operator_id, "read")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM agent_intake_simulations "
                    "WHERE operator_id=? AND intake_record_id=?",
                    (operator, intake_record_id),
                ).fetchone()
            if row is None:
                raise IntakeSimulationNotFoundError()
            return self._decode(row).record
        except IntakeSimulationStoreError:
            raise
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error

    def lifecycle(self, *, operator_id: str, intake_record_id: str) -> str:
        record = self.get(operator_id=operator_id, intake_record_id=intake_record_id)
        try:
            return simulation_lifecycle(record, now=_instant(self._clock))
        except Exception as error:
            raise IntakeSimulationUnavailableError() from error
