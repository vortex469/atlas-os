"""Append-only durable storage for evidence-only v0.32 Agent admissions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import TypeAdapter

from .contract import (
    MAX_RECORD_BYTES,
    AgentLiveIntakeAcknowledgementV1,
    AgentLiveIntakeAdmissionV1,
    AgentLiveIntakeAuditEvidenceV1,
    AgentLiveIntakeAuthenticationContextV1,
    AgentLiveIntakeEnvelopeV1,
    AgentLiveIntakeIdempotencyV1,
    AgentLiveIntakeReceiptV1,
    AgentLiveIntakeResultV1,
    AgentLiveIntakeStatusV1,
    CanonicalOperatorId,
    IdempotencyKey,
    acknowledgement_fingerprint,
    admission_fingerprint,
    admission_lifecycle,
    audit_evidence_fingerprint,
    idempotency_key_fingerprint,
    linkage_fingerprint,
    operator_fingerprint,
    record_fingerprint,
)

MAX_RETAINED_RECORDS_PER_OPERATOR = 16
MAX_ADMISSION_BYTES = 128 * 1024
MAX_ACKNOWLEDGEMENT_BYTES = 64 * 1024
MAX_AUDIT_BYTES = 64 * 1024
MAX_RESULT_BYTES = 256 * 1024


class AgentLiveIntakeStoreError(RuntimeError):
    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class AgentLiveIntakeMalformedError(AgentLiveIntakeStoreError):
    code = "malformed"


class AgentLiveIntakeNotCurrentError(AgentLiveIntakeStoreError):
    code = "not_current"


class AgentLiveIntakeOwnershipError(AgentLiveIntakeStoreError):
    code = "ownership_mismatch"


class AgentLiveIntakeLinkageMismatchError(AgentLiveIntakeStoreError):
    code = "linkage_mismatch"


class AgentLiveIntakeFingerprintMismatchError(AgentLiveIntakeStoreError):
    code = "fingerprint_mismatch"


class AgentLiveIntakeReplayConflictError(AgentLiveIntakeStoreError):
    code = "replay_conflict"


class AgentLiveIntakeQuotaError(AgentLiveIntakeStoreError):
    code = "quota_exceeded"


class AgentLiveIntakeUnavailableError(AgentLiveIntakeStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _server_time(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise AgentLiveIntakeUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise AgentLiveIntakeUnavailableError()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class AgentLiveIntakeAdmissionStore:
    """Atomically reserve one envelope and append its closed evidence graph."""

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
                    CREATE TABLE IF NOT EXISTS agent_live_intake_admissions (
                        admission_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        envelope_fingerprint TEXT NOT NULL UNIQUE,
                        attempt_id TEXT NOT NULL UNIQUE,
                        attempt_fingerprint TEXT NOT NULL UNIQUE,
                        request_id TEXT NOT NULL UNIQUE,
                        request_fingerprint TEXT NOT NULL UNIQUE,
                        delivery_attempt_id TEXT NOT NULL UNIQUE,
                        enablement_id TEXT NOT NULL UNIQUE,
                        preflight_id TEXT NOT NULL UNIQUE,
                        preparation_id TEXT NOT NULL UNIQUE,
                        admission_fingerprint TEXT NOT NULL UNIQUE,
                        admission_json TEXT NOT NULL,
                        acknowledgement_json TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        UNIQUE(operator_id, key_digest)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS agent_live_intake_reservations (
                        principal TEXT NOT NULL,
                        operator_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        envelope_fingerprint TEXT NOT NULL,
                        attempt_fingerprint TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        PRIMARY KEY(principal, operator_id, operation, key_digest)
                    )
                """)
        except Exception as error:
            raise AgentLiveIntakeUnavailableError() from error
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def received_at(self) -> str:
        """Return the same strict server-owned clock used for preservation."""
        return _server_time(self._clock)

    @staticmethod
    def _inputs(operator_id: str, idempotency_key: str) -> tuple[str, str]:
        try:
            operator = TypeAdapter(CanonicalOperatorId).validate_python(operator_id, strict=True)
            key = TypeAdapter(IdempotencyKey).validate_python(idempotency_key, strict=True)
        except Exception as error:
            raise AgentLiveIntakeMalformedError() from error
        digest = hashlib.sha256(b"atlas:agent-live-intake-reservation:v1\0" + key.encode()).hexdigest()
        return operator, digest

    @staticmethod
    def _encode(value, maximum: int) -> str:
        try:
            encoded = json.dumps(value.model_dump(mode="json"), ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        except Exception as error:
            raise AgentLiveIntakeMalformedError() from error
        if len(encoded.encode()) > maximum:
            raise AgentLiveIntakeQuotaError()
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> tuple[
        AgentLiveIntakeAdmissionV1,
        AgentLiveIntakeAcknowledgementV1,
        AgentLiveIntakeReceiptV1,
        AgentLiveIntakeAuditEvidenceV1,
        AgentLiveIntakeResultV1,
    ]:
        try:
            values = (
                ("admission_json", AgentLiveIntakeAdmissionV1, MAX_ADMISSION_BYTES),
                ("acknowledgement_json", AgentLiveIntakeAcknowledgementV1, MAX_ACKNOWLEDGEMENT_BYTES),
                ("record_json", AgentLiveIntakeReceiptV1, MAX_RECORD_BYTES),
                ("audit_json", AgentLiveIntakeAuditEvidenceV1, MAX_AUDIT_BYTES),
                ("result_json", AgentLiveIntakeResultV1, MAX_RESULT_BYTES),
            )
            decoded = []
            for name, model, maximum in values:
                raw = row[name]
                if type(raw) is not str or len(raw.encode()) > maximum:
                    raise ValueError
                decoded.append(model.model_validate_json(raw))
            admission, acknowledgement, record, audit, result = decoded
            expected = (
                admission.admission_id,
                admission.operator_id,
                admission.envelope_fingerprint.value,
                admission.send_attempt_id,
                admission.attempt_fingerprint.value,
                admission.intake_request_id,
                admission.request_fingerprint.value,
                admission.delivery_attempt_id,
                admission.linkage.enablement_id,
                admission.linkage.preflight_id,
                admission.linkage.delivery_preparation_id,
                admission.admission_fingerprint.value,
            )
            stored = tuple(row[name] for name in (
                "admission_id", "operator_id", "envelope_fingerprint", "attempt_id",
                "attempt_fingerprint", "request_id", "request_fingerprint",
                "delivery_attempt_id", "enablement_id", "preflight_id",
                "preparation_id", "admission_fingerprint",
            ))
            if expected != stored:
                raise ValueError
            if record.admission != admission or record.acknowledgement != acknowledgement:
                raise ValueError
            if result.admission != admission or result.acknowledgement != acknowledgement:
                raise ValueError
            if audit.admission_id != admission.admission_id or audit.admission_fingerprint != admission.admission_fingerprint:
                raise ValueError
            return admission, acknowledgement, record, audit, result
        except Exception as error:
            raise AgentLiveIntakeUnavailableError() from error

    def _replay(self, connection: sqlite3.Connection, *, operator: str, key_digest: str, envelope: AgentLiveIntakeEnvelopeV1):
        row = connection.execute(
            "SELECT * FROM agent_live_intake_reservations WHERE principal=? AND operator_id=? AND operation=? AND key_digest=?",
            ("atlas-core/install-intake-v1", operator, "installation_intake:create", key_digest),
        ).fetchone()
        if row is None:
            return None
        if row["envelope_fingerprint"] != envelope.envelope_fingerprint.value or row["attempt_fingerprint"] != envelope.send_attempt.attempt_fingerprint.value:
            raise AgentLiveIntakeReplayConflictError()
        evidence = connection.execute(
            "SELECT * FROM agent_live_intake_admissions WHERE operator_id=? AND admission_id=?",
            (operator, row["admission_id"]),
        ).fetchone()
        if evidence is None:
            raise AgentLiveIntakeUnavailableError()
        return self._decode(evidence)

    @staticmethod
    def _reject_reserved_identity(
        connection: sqlite3.Connection, envelope: AgentLiveIntakeEnvelopeV1
    ) -> None:
        existing = connection.execute(
            "SELECT 1 FROM agent_live_intake_admissions WHERE "
            "envelope_fingerprint=? OR attempt_id=? OR attempt_fingerprint=? "
            "OR request_id=? OR request_fingerprint=? OR delivery_attempt_id=? "
            "OR enablement_id=? OR preflight_id=? OR preparation_id=? LIMIT 1",
            (
                envelope.envelope_fingerprint.value,
                envelope.send_attempt.send_attempt_id,
                envelope.send_attempt.attempt_fingerprint.value,
                envelope.intake_request.intake_request_id,
                envelope.request_fingerprint.value,
                envelope.intake_request.delivery_attempt_id,
                envelope.send_attempt.linkage.enablement_id,
                envelope.send_attempt.linkage.preflight_id,
                envelope.send_attempt.linkage.delivery_preparation_id,
            ),
        ).fetchone()
        if existing is not None:
            raise AgentLiveIntakeReplayConflictError()

    def replay(self, *, operator_id: str, idempotency_key: str, envelope: AgentLiveIntakeEnvelopeV1):
        operator, digest = self._inputs(operator_id, idempotency_key)
        try:
            exact = AgentLiveIntakeEnvelopeV1.model_validate(envelope.model_dump(mode="python"))
            with self._connect() as connection:
                return self._replay(connection, operator=operator, key_digest=digest, envelope=exact)
        except AgentLiveIntakeStoreError:
            raise
        except Exception as error:
            raise AgentLiveIntakeMalformedError() from error

    def preserve(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        envelope: AgentLiveIntakeEnvelopeV1,
        authentication: AgentLiveIntakeAuthenticationContextV1,
        correlation_id: str,
    ) -> tuple[AgentLiveIntakeResultV1, bool]:
        operator, key_digest = self._inputs(operator_id, idempotency_key)
        try:
            exact = AgentLiveIntakeEnvelopeV1.model_validate(envelope.model_dump(mode="python"))
            auth = AgentLiveIntakeAuthenticationContextV1.model_validate(authentication.model_dump(mode="python"))
            if exact.send_attempt.operator_id != operator:
                raise AgentLiveIntakeOwnershipError()
        except AgentLiveIntakeStoreError:
            raise
        except Exception as error:
            raise AgentLiveIntakeMalformedError() from error

        try:
            with self._connect() as connection:
                prior = self._replay(connection, operator=operator, key_digest=key_digest, envelope=exact)
                if prior is None:
                    self._reject_reserved_identity(connection, exact)
            if prior is not None:
                return prior[4], False
        except AgentLiveIntakeStoreError:
            raise
        except Exception as error:
            raise AgentLiveIntakeUnavailableError() from error

        received_at = _server_time(self._clock)
        try:
            if not _instant(exact.send_attempt.created_at) <= _instant(exact.intake_request.sent_at) <= _instant(received_at) < _instant(exact.send_attempt.expires_at):
                raise AgentLiveIntakeNotCurrentError()
            admission_id = str(self._id_factory())
            acknowledgement_id = str(self._id_factory())
            admission_raw = {
                "admission_id": admission_id,
                "send_attempt_id": exact.send_attempt.send_attempt_id,
                "attempt_fingerprint": exact.send_attempt.attempt_fingerprint.model_dump(mode="json"),
                "envelope_fingerprint": exact.envelope_fingerprint.model_dump(mode="json"),
                "intake_request_id": exact.intake_request.intake_request_id,
                "request_fingerprint": exact.request_fingerprint.model_dump(mode="json"),
                "delivery_attempt_id": exact.intake_request.delivery_attempt_id,
                "received_at": received_at,
                "valid_until": exact.send_attempt.expires_at,
                "operator_id": operator,
                "linkage": exact.send_attempt.linkage.model_dump(mode="json"),
            }
            admission_raw["admission_fingerprint"] = admission_fingerprint(admission_raw).model_dump(mode="json")
            admission = AgentLiveIntakeAdmissionV1.model_validate(admission_raw)
            acknowledgement_raw = {
                "acknowledgement_id": acknowledgement_id,
                "admission_id": admission.admission_id,
                "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
                "send_attempt_id": admission.send_attempt_id,
                "attempt_fingerprint": admission.attempt_fingerprint.model_dump(mode="json"),
                "intake_request_id": admission.intake_request_id,
                "received_at": admission.received_at,
                "valid_until": admission.valid_until,
            }
            acknowledgement_raw["acknowledgement_fingerprint"] = acknowledgement_fingerprint(acknowledgement_raw).model_dump(mode="json")
            acknowledgement = AgentLiveIntakeAcknowledgementV1.model_validate(acknowledgement_raw)
            credential_reference_fingerprint = _credential_reference_fingerprint(auth)
            record_raw = {
                "admission": admission.model_dump(mode="json"),
                "acknowledgement": acknowledgement.model_dump(mode="json"),
                "credential_reference_fingerprint": credential_reference_fingerprint.model_dump(mode="json"),
            }
            record_raw["record_fingerprint"] = record_fingerprint(record_raw).model_dump(mode="json")
            record = AgentLiveIntakeReceiptV1.model_validate(record_raw)
            completed_at = _server_time(self._clock)
            audit_raw = {
                "admission_id": admission.admission_id,
                "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
                "acknowledgement_fingerprint": acknowledgement.acknowledgement_fingerprint.model_dump(mode="json"),
                "record_fingerprint": record.record_fingerprint.model_dump(mode="json"),
                "send_attempt_id": admission.send_attempt_id,
                "attempt_fingerprint": admission.attempt_fingerprint.model_dump(mode="json"),
                "envelope_fingerprint": admission.envelope_fingerprint.model_dump(mode="json"),
                "request_fingerprint": admission.request_fingerprint.model_dump(mode="json"),
                "linkage_fingerprint": linkage_fingerprint(admission.linkage).model_dump(mode="json"),
                "operator_fingerprint": operator_fingerprint(operator).model_dump(mode="json"),
                "correlation_id": correlation_id,
                "received_at": received_at,
                "completed_at": completed_at,
                "lifecycle": "admitted_for_evidence_only",
            }
            audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(audit_raw).model_dump(mode="json")
            audit = AgentLiveIntakeAuditEvidenceV1.model_validate(audit_raw)
            result = AgentLiveIntakeResultV1(
                send_attempt_id=admission.send_attempt_id,
                intake_request_id=admission.intake_request_id,
                outcome="admitted_for_evidence_only",
                admission=admission,
                acknowledgement=acknowledgement,
                reason_code=None,
            )
            encoded = (
                self._encode(admission, MAX_ADMISSION_BYTES),
                self._encode(acknowledgement, MAX_ACKNOWLEDGEMENT_BYTES),
                self._encode(record, MAX_RECORD_BYTES),
                self._encode(audit, MAX_AUDIT_BYTES),
                self._encode(result, MAX_RESULT_BYTES),
            )
            reservation = AgentLiveIntakeIdempotencyV1(
                operator_id=operator,
                key=idempotency_key,
                idempotency_key_fingerprint=idempotency_key_fingerprint(operator, idempotency_key),
                send_attempt_id=admission.send_attempt_id,
                attempt_fingerprint=admission.attempt_fingerprint,
                envelope_fingerprint=admission.envelope_fingerprint,
                enablement_id=admission.linkage.enablement_id,
                preflight_id=admission.linkage.preflight_id,
                delivery_preparation_id=admission.linkage.delivery_preparation_id,
                intake_request_id=admission.intake_request_id,
                admission_id=admission.admission_id,
                admission_fingerprint=admission.admission_fingerprint,
            )
        except AgentLiveIntakeStoreError:
            raise
        except Exception as error:
            raise AgentLiveIntakeMalformedError() from error

        try:
            quota_exceeded = False
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = self._replay(connection, operator=operator, key_digest=key_digest, envelope=exact)
                if prior is not None:
                    return prior[4], False
                self._reject_reserved_identity(connection, exact)
                count = connection.execute("SELECT COUNT(*) FROM agent_live_intake_admissions WHERE operator_id=?", (operator,)).fetchone()[0]
                connection.execute(
                    "INSERT INTO agent_live_intake_reservations VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        reservation.authenticated_principal, operator,
                        reservation.operation, key_digest,
                        reservation.envelope_fingerprint.value,
                        reservation.attempt_fingerprint.value, admission.admission_id,
                    ),
                )
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    quota_exceeded = True
                else:
                    connection.execute(
                        "INSERT INTO agent_live_intake_admissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            admission.admission_id, operator, key_digest,
                            admission.envelope_fingerprint.value, admission.send_attempt_id,
                            admission.attempt_fingerprint.value, admission.intake_request_id,
                            admission.request_fingerprint.value, admission.delivery_attempt_id,
                            admission.linkage.enablement_id, admission.linkage.preflight_id,
                            admission.linkage.delivery_preparation_id,
                            admission.admission_fingerprint.value, *encoded,
                        ),
                    )
            if quota_exceeded:
                raise AgentLiveIntakeQuotaError()
            return result, True
        except AgentLiveIntakeStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise AgentLiveIntakeReplayConflictError() from error
        except Exception as error:
            raise AgentLiveIntakeUnavailableError() from error

    def get(self, *, operator_id: str, admission_id: str) -> AgentLiveIntakeReceiptV1:
        row = self._owned_row(operator_id=operator_id, admission_id=admission_id)
        return self._decode(row)[2]

    def get_audit(self, *, operator_id: str, admission_id: str) -> AgentLiveIntakeAuditEvidenceV1:
        row = self._owned_row(operator_id=operator_id, admission_id=admission_id)
        return self._decode(row)[3]

    def get_result(self, *, operator_id: str, admission_id: str) -> AgentLiveIntakeResultV1:
        row = self._owned_row(operator_id=operator_id, admission_id=admission_id)
        return self._decode(row)[4]

    def _owned_row(self, *, operator_id: str, admission_id: str) -> sqlite3.Row:
        operator, _ = self._inputs(operator_id, "read")
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM agent_live_intake_admissions WHERE operator_id=? AND admission_id=?", (operator, admission_id)).fetchone()
            if row is None:
                raise AgentLiveIntakeUnavailableError()
            return row
        except AgentLiveIntakeStoreError:
            raise
        except Exception as error:
            raise AgentLiveIntakeUnavailableError() from error

    def status(self, *, operator_id: str, admission_id: str) -> AgentLiveIntakeStatusV1:
        record = self.get(operator_id=operator_id, admission_id=admission_id)
        observed_at = _server_time(self._clock)
        return AgentLiveIntakeStatusV1(
            admission_id=record.admission.admission_id,
            send_attempt_id=record.admission.send_attempt_id,
            operator_id=record.admission.operator_id,
            observed_at=observed_at,
            valid_until=record.admission.valid_until,
            lifecycle=admission_lifecycle(record.admission, observed_at=observed_at),
        )


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _credential_reference_fingerprint(authentication: AgentLiveIntakeAuthenticationContextV1):
    raw = authentication.credential_reference.model_dump(mode="json")
    return operator_fingerprint(json.dumps(raw, sort_keys=True, separators=(",", ":")))
