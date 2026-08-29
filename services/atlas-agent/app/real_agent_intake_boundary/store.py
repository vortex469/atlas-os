"""Append-only, operator-owned storage for inert real-intake evidence."""

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
    MAX_ADMISSION_BYTES,
    AgentInstallationIntakeAcknowledgementV1,
    AgentInstallationIntakeAdmissionV1,
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeEvidenceContextV1,
    AgentInstallationIntakeRequestV1,
    CanonicalOperatorId,
    IdempotencyKey,
    acknowledgement_fingerprint,
    admission_fingerprint,
    intake_lifecycle,
    request_fingerprint,
    validate_real_intake,
)

MAX_RETAINED_RECORDS_PER_OPERATOR = 16
MAX_ACKNOWLEDGEMENT_BYTES = 16 * 1024


class RealIntakeStoreError(RuntimeError):
    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class RealIntakeMalformedError(RealIntakeStoreError):
    code = "malformed"


class RealIntakeNotFoundError(RealIntakeStoreError):
    code = "unavailable"


class RealIntakeNotCurrentError(RealIntakeStoreError):
    code = "not_current"


class RealIntakeOwnershipError(RealIntakeStoreError):
    code = "ownership_mismatch"


class RealIntakeRequestMismatchError(RealIntakeStoreError):
    code = "request_mismatch"


class RealIntakeEnvelopeMismatchError(RealIntakeStoreError):
    code = "envelope_mismatch"


class RealIntakeLinkageMismatchError(RealIntakeStoreError):
    code = "linkage_mismatch"


class RealIntakeSimulationEvidenceMismatchError(RealIntakeStoreError):
    code = "simulation_evidence_mismatch"


class RealIntakeDeliveryEvidenceMismatchError(RealIntakeStoreError):
    code = "delivery_evidence_mismatch"


class RealIntakeReplayConflictError(RealIntakeStoreError):
    code = "replay_conflict"


class RealIntakeQuotaError(RealIntakeStoreError):
    code = "quota_exceeded"


class RealIntakeUnavailableError(RealIntakeStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _server_time(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise RealIntakeUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise RealIntakeUnavailableError()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentRealIntakeEvidenceStore:
    """Atomically reserve every v0.20-v0.27 identity and append one admission."""

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
                    CREATE TABLE IF NOT EXISTS agent_real_intake_admissions (
                        admission_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        request_id TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        delivery_attempt_id TEXT NOT NULL,
                        envelope_id TEXT NOT NULL,
                        envelope_fingerprint TEXT NOT NULL,
                        simulation_request_id TEXT NOT NULL,
                        intake_record_id TEXT NOT NULL,
                        intake_record_fingerprint TEXT NOT NULL,
                        simulated_delivery_id TEXT NOT NULL,
                        simulated_delivery_fingerprint TEXT NOT NULL,
                        delivery_record_fingerprint TEXT NOT NULL,
                        acknowledgement_id TEXT NOT NULL,
                        prior_acknowledgement_fingerprint TEXT NOT NULL,
                        admission_fingerprint TEXT NOT NULL,
                        admission_json TEXT NOT NULL,
                        acknowledgement_json TEXT NOT NULL,
                        UNIQUE(operator_id, request_id),
                        UNIQUE(operator_id, request_fingerprint),
                        UNIQUE(operator_id, delivery_attempt_id),
                        UNIQUE(operator_id, envelope_id),
                        UNIQUE(operator_id, envelope_fingerprint),
                        UNIQUE(operator_id, simulation_request_id),
                        UNIQUE(operator_id, intake_record_id),
                        UNIQUE(operator_id, intake_record_fingerprint),
                        UNIQUE(operator_id, simulated_delivery_id),
                        UNIQUE(operator_id, simulated_delivery_fingerprint),
                        UNIQUE(operator_id, delivery_record_fingerprint),
                        UNIQUE(operator_id, acknowledgement_id),
                        UNIQUE(operator_id, prior_acknowledgement_fingerprint),
                        UNIQUE(operator_id, admission_fingerprint)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS agent_real_intake_idempotency (
                        principal TEXT NOT NULL,
                        operator_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        PRIMARY KEY(principal, operator_id, operation, key_digest)
                    )
                """)
        except Exception as error:
            raise RealIntakeUnavailableError() from error
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
            operator = TypeAdapter(CanonicalOperatorId).validate_python(
                operator_id, strict=True
            )
            key = TypeAdapter(IdempotencyKey).validate_python(
                idempotency_key, strict=True
            )
        except Exception as error:
            raise RealIntakeMalformedError() from error
        digest = hashlib.sha256(
            b"atlas:agent-installation-intake-idempotency:v1\0" + key.encode()
        ).hexdigest()
        return operator, digest

    @staticmethod
    def _encode(
        value: AgentInstallationIntakeAdmissionV1
        | AgentInstallationIntakeAcknowledgementV1,
        *,
        maximum: int,
    ) -> str:
        try:
            encoded = json.dumps(
                value.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except Exception as error:
            raise RealIntakeMalformedError() from error
        if len(encoded.encode()) > maximum:
            raise RealIntakeQuotaError()
        return encoded

    @staticmethod
    def _acknowledgement(
        admission: AgentInstallationIntakeAdmissionV1,
    ) -> AgentInstallationIntakeAcknowledgementV1:
        raw = {
            "schema": "agent-installation-intake-acknowledgement-v1",
            "admission_id": admission.admission_id,
            "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
            "intake_request_id": admission.intake_request_id,
            "received_at": admission.received_at,
            "valid_until": admission.valid_until,
            "status": "admitted_for_evidence_only",
            "provenance": "authenticated_core_intake_evidence_only",
            "execution_admission_granted": False,
            "execution_authorized": False,
            "worker_allowed": False,
            "mutation_allowed": False,
            "replay_allowed": False,
        }
        raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(
            raw
        ).model_dump(mode="json")
        return AgentInstallationIntakeAcknowledgementV1.model_validate(raw)

    @staticmethod
    def _decode(
        row: sqlite3.Row,
    ) -> tuple[
        AgentInstallationIntakeAdmissionV1,
        AgentInstallationIntakeAcknowledgementV1,
    ]:
        try:
            admission_raw = row["admission_json"]
            acknowledgement_raw = row["acknowledgement_json"]
            if (
                type(admission_raw) is not str
                or len(admission_raw.encode()) > MAX_ADMISSION_BYTES
                or type(acknowledgement_raw) is not str
                or len(acknowledgement_raw.encode()) > MAX_ACKNOWLEDGEMENT_BYTES
            ):
                raise ValueError
            admission = AgentInstallationIntakeAdmissionV1.model_validate_json(
                admission_raw
            )
            acknowledgement = (
                AgentInstallationIntakeAcknowledgementV1.model_validate_json(
                    acknowledgement_raw
                )
            )
            simulation = admission.prior_evidence.intake_simulation
            delivery = admission.prior_evidence.simulated_delivery
            expected = (
                admission.admission_id,
                admission.intake_request_id,
                admission.source.request_fingerprint.value,
                admission.delivery_attempt_id,
                admission.source.dispatch_envelope_id,
                admission.source.dispatch_envelope_fingerprint.value,
                simulation.simulation_request_id,
                simulation.intake_record_id,
                simulation.intake_record_fingerprint.value,
                delivery.simulated_delivery_id,
                delivery.simulated_delivery_fingerprint.value,
                delivery.delivery_record_fingerprint.value,
                delivery.acknowledgement_id,
                delivery.acknowledgement_fingerprint.value,
                admission.admission_fingerprint.value,
            )
            stored = tuple(
                row[name]
                for name in (
                    "admission_id",
                    "request_id",
                    "request_fingerprint",
                    "delivery_attempt_id",
                    "envelope_id",
                    "envelope_fingerprint",
                    "simulation_request_id",
                    "intake_record_id",
                    "intake_record_fingerprint",
                    "simulated_delivery_id",
                    "simulated_delivery_fingerprint",
                    "delivery_record_fingerprint",
                    "acknowledgement_id",
                    "prior_acknowledgement_fingerprint",
                    "admission_fingerprint",
                )
            )
            if (
                type(row["operator_id"]) is not str
                or expected != stored
                or admission.admission_fingerprint
                != admission_fingerprint(
                    operator_id=row["operator_id"], admission=admission
                )
                or acknowledgement.admission_id != admission.admission_id
                or acknowledgement.admission_fingerprint
                != admission.admission_fingerprint
                or acknowledgement.intake_request_id != admission.intake_request_id
            ):
                raise ValueError
            return admission, acknowledgement
        except Exception as error:
            raise RealIntakeUnavailableError() from error

    def _replay(
        self,
        connection: sqlite3.Connection,
        *,
        operator: str,
        key_digest: str,
        request_digest: str,
    ) -> AgentInstallationIntakeAdmissionV1 | None:
        reservation = connection.execute(
            "SELECT * FROM agent_real_intake_idempotency WHERE principal=? "
            "AND operator_id=? AND operation=? AND key_digest=?",
            (
                "atlas-core/install-intake-v1",
                operator,
                "installation_intake:create",
                key_digest,
            ),
        ).fetchone()
        if reservation is None:
            return None
        if reservation["request_fingerprint"] != request_digest:
            raise RealIntakeReplayConflictError()
        row = connection.execute(
            "SELECT * FROM agent_real_intake_admissions WHERE operator_id=? "
            "AND admission_id=?",
            (operator, reservation["admission_id"]),
        ).fetchone()
        if row is None or row["request_fingerprint"] != request_digest:
            raise RealIntakeUnavailableError()
        return self._decode(row)[0]

    def replay(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        request: AgentInstallationIntakeRequestV1,
    ) -> AgentInstallationIntakeAdmissionV1 | None:
        operator, key_digest = self._inputs(operator_id, idempotency_key)
        try:
            exact = AgentInstallationIntakeRequestV1.model_validate(
                request.model_dump(mode="python")
            )
            request_digest = request_fingerprint(exact).value
            if request_digest != exact.request_fingerprint.value:
                raise RealIntakeRequestMismatchError()
            with self._connect() as connection:
                return self._replay(
                    connection,
                    operator=operator,
                    key_digest=key_digest,
                    request_digest=request_digest,
                )
        except RealIntakeStoreError:
            raise
        except Exception as error:
            raise RealIntakeMalformedError() from error

    def preserve(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        request: AgentInstallationIntakeRequestV1,
        authentication: AgentInstallationIntakeAuthenticationContextV1,
        evidence: AgentInstallationIntakeEvidenceContextV1,
    ) -> tuple[AgentInstallationIntakeAdmissionV1, bool]:
        operator, key_digest = self._inputs(operator_id, idempotency_key)
        try:
            exact = AgentInstallationIntakeRequestV1.model_validate(
                request.model_dump(mode="python")
            )
            request_digest = request_fingerprint(exact).value
            if request_digest != exact.request_fingerprint.value:
                raise RealIntakeRequestMismatchError()
        except RealIntakeStoreError:
            raise
        except Exception as error:
            raise RealIntakeMalformedError() from error
        try:
            with self._connect() as connection:
                prior = self._replay(
                    connection,
                    operator=operator,
                    key_digest=key_digest,
                    request_digest=request_digest,
                )
            if prior is not None:
                return prior, False
        except RealIntakeStoreError:
            raise
        except Exception as error:
            raise RealIntakeUnavailableError() from error

        received_at = _server_time(self._clock)
        try:
            admission_id = str(self._id_factory())
            validation = validate_real_intake(
                exact,
                authentication=authentication,
                evidence=evidence,
                received_at=received_at,
                admission_id=admission_id,
            )
            admission = validation.admission
            acknowledgement = self._acknowledgement(admission)
            admission_json = self._encode(admission, maximum=MAX_ADMISSION_BYTES)
            acknowledgement_json = self._encode(
                acknowledgement, maximum=MAX_ACKNOWLEDGEMENT_BYTES
            )
        except RealIntakeStoreError:
            raise
        except Exception as error:
            detail = str(error)
            if "current" in detail or "precedes" in detail or "window" in detail or "postdates" in detail:
                raise RealIntakeNotCurrentError() from error
            if "ownership or envelope" in detail:
                raise RealIntakeEnvelopeMismatchError() from error
            if "ownership" in detail:
                raise RealIntakeOwnershipError() from error
            if "request fingerprint" in detail:
                raise RealIntakeRequestMismatchError() from error
            if "envelope fingerprint" in detail:
                raise RealIntakeEnvelopeMismatchError() from error
            if "linkage" in detail:
                raise RealIntakeLinkageMismatchError() from error
            if "simulation evidence" in detail:
                raise RealIntakeSimulationEvidenceMismatchError() from error
            if "delivery evidence" in detail:
                raise RealIntakeDeliveryEvidenceMismatchError() from error
            raise RealIntakeMalformedError() from error

        simulation = admission.prior_evidence.intake_simulation
        delivery = admission.prior_evidence.simulated_delivery
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = self._replay(
                    connection,
                    operator=operator,
                    key_digest=key_digest,
                    request_digest=request_digest,
                )
                if prior is not None:
                    return prior, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM agent_real_intake_admissions "
                    "WHERE operator_id=?",
                    (operator,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    raise RealIntakeQuotaError()
                connection.execute(
                    "INSERT INTO agent_real_intake_admissions VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        admission.admission_id,
                        operator,
                        admission.intake_request_id,
                        admission.source.request_fingerprint.value,
                        admission.delivery_attempt_id,
                        admission.source.dispatch_envelope_id,
                        admission.source.dispatch_envelope_fingerprint.value,
                        simulation.simulation_request_id,
                        simulation.intake_record_id,
                        simulation.intake_record_fingerprint.value,
                        delivery.simulated_delivery_id,
                        delivery.simulated_delivery_fingerprint.value,
                        delivery.delivery_record_fingerprint.value,
                        delivery.acknowledgement_id,
                        delivery.acknowledgement_fingerprint.value,
                        admission.admission_fingerprint.value,
                        admission_json,
                        acknowledgement_json,
                    ),
                )
                connection.execute(
                    "INSERT INTO agent_real_intake_idempotency VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        authentication.authenticated_principal,
                        operator,
                        authentication.permission,
                        key_digest,
                        request_digest,
                        admission.admission_id,
                    ),
                )
                return admission, True
        except RealIntakeStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise RealIntakeReplayConflictError() from error
        except Exception as error:
            raise RealIntakeUnavailableError() from error

    def get(
        self, *, operator_id: str, admission_id: str
    ) -> AgentInstallationIntakeAdmissionV1:
        operator, _ = self._inputs(operator_id, "read")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM agent_real_intake_admissions "
                    "WHERE operator_id=? AND admission_id=?",
                    (operator, admission_id),
                ).fetchone()
            if row is None:
                raise RealIntakeNotFoundError()
            return self._decode(row)[0]
        except RealIntakeStoreError:
            raise
        except Exception as error:
            raise RealIntakeUnavailableError() from error

    def get_acknowledgement(
        self, *, operator_id: str, admission_id: str
    ) -> AgentInstallationIntakeAcknowledgementV1:
        operator, _ = self._inputs(operator_id, "read")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM agent_real_intake_admissions "
                    "WHERE operator_id=? AND admission_id=?",
                    (operator, admission_id),
                ).fetchone()
            if row is None:
                raise RealIntakeNotFoundError()
            return self._decode(row)[1]
        except RealIntakeStoreError:
            raise
        except Exception as error:
            raise RealIntakeUnavailableError() from error

    def lifecycle(self, *, operator_id: str, admission_id: str) -> str:
        admission = self.get(operator_id=operator_id, admission_id=admission_id)
        try:
            return intake_lifecycle(admission, now=_server_time(self._clock))
        except Exception as error:
            raise RealIntakeUnavailableError() from error
