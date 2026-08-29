"""Append-only durable reservation evidence for the v0.31 P2 boundary."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .contract import (
    MAX_ATTEMPT_BYTES,
    MAX_AUDIT_EVIDENCE_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_TRANSPORT_ENVELOPE_BYTES,
    AgentInstallationIntakeAcknowledgementV1,
    AgentInstallationIntakeResultV1,
    LiveDeliverySendAttemptV1,
    LiveDeliverySendAuditEvidenceV1,
    LiveDeliverySendReceiptV1,
    LiveDeliveryTransportEnvelopeV1,
    audit_evidence_fingerprint,
    receipt_fingerprint,
    validate_send_attempt,
)

MAX_RECORDS_PER_OPERATOR = 16


class LiveDeliverySendStoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LiveDeliverySendStoredEvidence:
    attempt: LiveDeliverySendAttemptV1
    envelope: LiveDeliveryTransportEnvelopeV1
    audit_evidence: LiveDeliverySendAuditEvidenceV1
    receipt: LiveDeliverySendReceiptV1 | None = None
    agent_result: AgentInstallationIntakeResultV1 | None = None
    acknowledgement: AgentInstallationIntakeAcknowledgementV1 | None = None
    terminal_audit_evidence: LiveDeliverySendAuditEvidenceV1 | None = None


class LiveDeliverySendStore:
    """Independent SQLite store with permanent multi-identity reservations."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS live_delivery_send_attempts (
                        operator_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        enablement_id TEXT NOT NULL,
                        enablement_fingerprint TEXT NOT NULL,
                        preflight_id TEXT NOT NULL,
                        delivery_preparation_id TEXT NOT NULL,
                        preparation_fingerprint TEXT NOT NULL,
                        intake_request_id TEXT NOT NULL,
                        send_attempt_id TEXT NOT NULL,
                        attempt_fingerprint TEXT NOT NULL,
                        attempt_json TEXT NOT NULL,
                        envelope_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, send_attempt_id),
                        UNIQUE (operator_id, idempotency_key),
                        UNIQUE (operator_id, enablement_id),
                        UNIQUE (operator_id, enablement_fingerprint),
                        UNIQUE (operator_id, preflight_id),
                        UNIQUE (operator_id, delivery_preparation_id),
                        UNIQUE (operator_id, preparation_fingerprint),
                        UNIQUE (operator_id, intake_request_id),
                        UNIQUE (operator_id, attempt_fingerprint)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS live_delivery_send_receipts (
                        operator_id TEXT NOT NULL,
                        send_attempt_id TEXT NOT NULL,
                        receipt_fingerprint TEXT NOT NULL,
                        receipt_json TEXT NOT NULL,
                        agent_result_json TEXT,
                        acknowledgement_json TEXT,
                        terminal_audit_json TEXT,
                        PRIMARY KEY (operator_id, send_attempt_id),
                        UNIQUE (operator_id, receipt_fingerprint),
                        FOREIGN KEY (operator_id, send_attempt_id) REFERENCES
                            live_delivery_send_attempts (operator_id, send_attempt_id)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error

    def resolve_reservation(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        enablement_id: str,
        delivery_preparation_id: str,
    ) -> LiveDeliverySendStoredEvidence | None:
        rows = self._reservation_rows(
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            enablement_id=enablement_id,
            delivery_preparation_id=delivery_preparation_id,
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise LiveDeliverySendStoreError("unavailable")
        row = rows[0]
        if (
            row["idempotency_key"] != idempotency_key
            or row["create_fingerprint"] != create_fingerprint
            or row["enablement_id"] != enablement_id
            or row["delivery_preparation_id"] != delivery_preparation_id
        ):
            raise LiveDeliverySendStoreError("replay_conflict")
        return self._decode(row, operator_id=operator_id)

    def reserve(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        evidence: LiveDeliverySendStoredEvidence,
    ) -> tuple[LiveDeliverySendStoredEvidence, bool]:
        attempt, envelope, audit = (
            evidence.attempt,
            evidence.envelope,
            evidence.audit_evidence,
        )
        if any(value is not None for value in (
            evidence.receipt, evidence.agent_result, evidence.acknowledgement,
            evidence.terminal_audit_evidence,
        )):
            raise LiveDeliverySendStoreError("unavailable")
        attempt_json = self._encode(attempt, MAX_ATTEMPT_BYTES)
        envelope_json = self._encode(envelope, MAX_TRANSPORT_ENVELOPE_BYTES)
        audit_json = self._encode(audit, MAX_AUDIT_EVIDENCE_BYTES)
        linkage = attempt.linkage
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT attempts.*, receipts.receipt_json,
                           receipts.agent_result_json, receipts.acknowledgement_json,
                           receipts.terminal_audit_json
                    FROM live_delivery_send_attempts AS attempts
                    LEFT JOIN live_delivery_send_receipts AS receipts USING (
                        operator_id, send_attempt_id
                    )
                    WHERE attempts.operator_id = ? AND (
                        attempts.idempotency_key = ? OR attempts.enablement_id = ?
                        OR attempts.enablement_fingerprint = ? OR attempts.preflight_id = ?
                        OR attempts.delivery_preparation_id = ? OR attempts.preparation_fingerprint = ?
                        OR attempts.intake_request_id = ? OR attempts.send_attempt_id = ?
                        OR attempts.attempt_fingerprint = ?
                    )
                    """,
                    (
                        operator_id, idempotency_key, linkage.enablement_id,
                        linkage.enablement_fingerprint.value, linkage.preflight_id,
                        linkage.delivery_preparation_id,
                        linkage.preparation_fingerprint.value, linkage.intake_request_id,
                        attempt.send_attempt_id, attempt.attempt_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact(
                        rows[0], idempotency_key, create_fingerprint, evidence
                    ):
                        raise LiveDeliverySendStoreError("replay_conflict")
                    connection.execute("COMMIT")
                    return self._decode(rows[0], operator_id=operator_id), False
                count = connection.execute(
                    "SELECT COUNT(*) FROM live_delivery_send_attempts WHERE operator_id = ?",
                    (operator_id,),
                ).fetchone()[0]
                if count >= MAX_RECORDS_PER_OPERATOR:
                    raise LiveDeliverySendStoreError("quota_exceeded")
                connection.execute(
                    """
                    INSERT INTO live_delivery_send_attempts (
                        operator_id, idempotency_key, create_fingerprint,
                        enablement_id, enablement_fingerprint, preflight_id,
                        delivery_preparation_id, preparation_fingerprint,
                        intake_request_id, send_attempt_id, attempt_fingerprint,
                        attempt_json, envelope_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operator_id, idempotency_key, create_fingerprint,
                        linkage.enablement_id, linkage.enablement_fingerprint.value,
                        linkage.preflight_id, linkage.delivery_preparation_id,
                        linkage.preparation_fingerprint.value, linkage.intake_request_id,
                        attempt.send_attempt_id, attempt.attempt_fingerprint.value,
                        attempt_json, envelope_json, audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return evidence, True
        except LiveDeliverySendStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise LiveDeliverySendStoreError("replay_conflict") from error
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error

    def append_receipt(
        self,
        *,
        operator_id: str,
        receipt: LiveDeliverySendReceiptV1,
    ) -> LiveDeliverySendStoredEvidence:
        """Append one closed receipt; P2 service has no caller for this operation."""
        encoded = self._encode(receipt, MAX_RECEIPT_BYTES)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT attempts.*, receipts.receipt_json,
                              receipts.agent_result_json, receipts.acknowledgement_json,
                              receipts.terminal_audit_json
                    FROM live_delivery_send_attempts AS attempts
                    LEFT JOIN live_delivery_send_receipts AS receipts USING (
                        operator_id, send_attempt_id
                    )
                    WHERE attempts.operator_id = ? AND attempts.send_attempt_id = ?""",
                    (operator_id, receipt.send_attempt_id),
                ).fetchone()
                if row is None:
                    raise LiveDeliverySendStoreError("not_found")
                existing = self._decode(row, operator_id=operator_id)
                if receipt.attempt_fingerprint != existing.attempt.attempt_fingerprint:
                    raise LiveDeliverySendStoreError("replay_conflict")
                if existing.receipt is not None:
                    if existing.receipt != receipt:
                        raise LiveDeliverySendStoreError("replay_conflict")
                    connection.execute("COMMIT")
                    return existing
                connection.execute(
                    """INSERT INTO live_delivery_send_receipts (
                        operator_id, send_attempt_id, receipt_fingerprint, receipt_json
                    ) VALUES (?, ?, ?, ?)""",
                    (
                        operator_id,
                        receipt.send_attempt_id,
                        receipt.receipt_fingerprint.value,
                        encoded,
                    ),
                )
                connection.execute("COMMIT")
                return LiveDeliverySendStoredEvidence(
                    attempt=existing.attempt,
                    envelope=existing.envelope,
                    audit_evidence=existing.audit_evidence,
                    receipt=receipt,
                )
        except LiveDeliverySendStoreError:
            raise
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error

    def append_outcome(
        self,
        *,
        operator_id: str,
        receipt: LiveDeliverySendReceiptV1,
        agent_result: AgentInstallationIntakeResultV1 | None,
        acknowledgement: AgentInstallationIntakeAcknowledgementV1 | None,
        audit_evidence: LiveDeliverySendAuditEvidenceV1,
    ) -> LiveDeliverySendStoredEvidence:
        encoded = (
            self._encode(receipt, MAX_RECEIPT_BYTES),
            None if agent_result is None else self._encode(agent_result, MAX_RECEIPT_BYTES),
            None if acknowledgement is None else self._encode(
                acknowledgement, MAX_RECEIPT_BYTES
            ),
            self._encode(audit_evidence, MAX_AUDIT_EVIDENCE_BYTES),
        )
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT attempts.*, receipts.receipt_json,
                              receipts.agent_result_json, receipts.acknowledgement_json,
                              receipts.terminal_audit_json
                       FROM live_delivery_send_attempts AS attempts
                       LEFT JOIN live_delivery_send_receipts AS receipts USING (
                           operator_id, send_attempt_id
                       )
                       WHERE attempts.operator_id = ? AND attempts.send_attempt_id = ?""",
                    (operator_id, receipt.send_attempt_id),
                ).fetchone()
                if row is None:
                    raise LiveDeliverySendStoreError("not_found")
                existing = self._decode(row, operator_id=operator_id)
                if receipt.attempt_fingerprint != existing.attempt.attempt_fingerprint:
                    raise LiveDeliverySendStoreError("replay_conflict")
                if existing.receipt is not None:
                    if (
                        existing.receipt, existing.agent_result,
                        existing.acknowledgement, existing.terminal_audit_evidence,
                    ) != (receipt, agent_result, acknowledgement, audit_evidence):
                        raise LiveDeliverySendStoreError("replay_conflict")
                    connection.execute("COMMIT")
                    return existing
                connection.execute(
                    """INSERT INTO live_delivery_send_receipts (
                           operator_id, send_attempt_id, receipt_fingerprint,
                           receipt_json, agent_result_json, acknowledgement_json,
                           terminal_audit_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        operator_id, receipt.send_attempt_id,
                        receipt.receipt_fingerprint.value, *encoded,
                    ),
                )
                connection.execute("COMMIT")
                return LiveDeliverySendStoredEvidence(
                    existing.attempt, existing.envelope, existing.audit_evidence,
                    receipt, agent_result, acknowledgement, audit_evidence,
                )
        except LiveDeliverySendStoreError:
            raise
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error

    def get(self, *, operator_id: str, send_attempt_id: str) -> LiveDeliverySendStoredEvidence:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT attempts.*, receipts.receipt_json,
                              receipts.agent_result_json, receipts.acknowledgement_json,
                              receipts.terminal_audit_json
                    FROM live_delivery_send_attempts AS attempts
                    LEFT JOIN live_delivery_send_receipts AS receipts USING (
                        operator_id, send_attempt_id
                    )
                    WHERE attempts.operator_id = ? AND attempts.send_attempt_id = ?""",
                    (operator_id, send_attempt_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error
        if row is None:
            raise LiveDeliverySendStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(self, *, operator_id: str) -> tuple[LiveDeliverySendStoredEvidence, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT attempts.*, receipts.receipt_json,
                              receipts.agent_result_json, receipts.acknowledgement_json,
                              receipts.terminal_audit_json
                    FROM live_delivery_send_attempts AS attempts
                    LEFT JOIN live_delivery_send_receipts AS receipts USING (
                        operator_id, send_attempt_id
                    )
                    WHERE attempts.operator_id = ?
                    ORDER BY json_extract(attempts.attempt_json, '$.created_at') DESC,
                             attempts.send_attempt_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error
        if len(rows) > MAX_RECORDS_PER_OPERATOR:
            raise LiveDeliverySendStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    def _reservation_rows(self, *, operator_id: str, idempotency_key: str,
                          enablement_id: str, delivery_preparation_id: str):
        try:
            with self._connect() as connection:
                return connection.execute(
                    """SELECT attempts.*, receipts.receipt_json,
                              receipts.agent_result_json, receipts.acknowledgement_json,
                              receipts.terminal_audit_json
                    FROM live_delivery_send_attempts AS attempts
                    LEFT JOIN live_delivery_send_receipts AS receipts USING (
                        operator_id, send_attempt_id
                    )
                    WHERE attempts.operator_id = ? AND (
                        attempts.idempotency_key = ? OR attempts.enablement_id = ?
                        OR attempts.delivery_preparation_id = ?
                    )""",
                    (operator_id, idempotency_key, enablement_id, delivery_preparation_id),
                ).fetchall()
        except sqlite3.Error as error:
            raise LiveDeliverySendStoreError("unavailable") from error

    @staticmethod
    def _is_exact(row, idempotency_key, create_fingerprint, evidence) -> bool:
        attempt = evidence.attempt
        return (
            row["idempotency_key"] == idempotency_key
            and row["create_fingerprint"] == create_fingerprint
            and row["send_attempt_id"] == attempt.send_attempt_id
            and row["attempt_fingerprint"] == attempt.attempt_fingerprint.value
            and row["attempt_json"] == attempt.model_dump_json()
            and row["envelope_json"] == evidence.envelope.model_dump_json()
            and row["audit_json"] == evidence.audit_evidence.model_dump_json()
        )

    @staticmethod
    def _encode(value, maximum: int) -> str:
        encoded = value.model_dump_json()
        if len(encoded.encode()) > maximum:
            raise LiveDeliverySendStoreError("size_exceeded")
        return encoded

    @staticmethod
    def _decode(row, *, operator_id: str) -> LiveDeliverySendStoredEvidence:
        try:
            raw_values = (
                (row["attempt_json"], MAX_ATTEMPT_BYTES),
                (row["envelope_json"], MAX_TRANSPORT_ENVELOPE_BYTES),
                (row["audit_json"], MAX_AUDIT_EVIDENCE_BYTES),
            )
            if any(
                not isinstance(raw, str) or len(raw.encode()) > maximum
                for raw, maximum in raw_values
            ):
                raise ValueError("persisted evidence exceeds bound")
            attempt = LiveDeliverySendAttemptV1.model_validate_json(row["attempt_json"])
            envelope = LiveDeliveryTransportEnvelopeV1.model_validate_json(row["envelope_json"])
            audit = LiveDeliverySendAuditEvidenceV1.model_validate_json(row["audit_json"])
            validate_send_attempt(attempt, operator_id=operator_id)
            if audit.evidence_fingerprint != audit_evidence_fingerprint(audit):
                raise ValueError("audit fingerprint mismatch")
            receipt = None
            agent_result = None
            acknowledgement = None
            terminal_audit = None
            if row["receipt_json"] is not None:
                if not isinstance(row["receipt_json"], str) or len(row["receipt_json"].encode()) > MAX_RECEIPT_BYTES:
                    raise ValueError("persisted receipt exceeds bound")
                receipt = LiveDeliverySendReceiptV1.model_validate_json(row["receipt_json"])
                if receipt.receipt_fingerprint != receipt_fingerprint(receipt):
                    raise ValueError("receipt fingerprint mismatch")
                if row["agent_result_json"] is not None:
                    if len(row["agent_result_json"].encode()) > MAX_RECEIPT_BYTES:
                        raise ValueError("persisted Agent result exceeds bound")
                    agent_result = AgentInstallationIntakeResultV1.model_validate_json(
                        row["agent_result_json"]
                    )
                if row["acknowledgement_json"] is not None:
                    if len(row["acknowledgement_json"].encode()) > MAX_RECEIPT_BYTES:
                        raise ValueError("persisted acknowledgement exceeds bound")
                    acknowledgement = AgentInstallationIntakeAcknowledgementV1.model_validate_json(
                        row["acknowledgement_json"]
                    )
                if row["terminal_audit_json"] is not None:
                    if len(row["terminal_audit_json"].encode()) > MAX_AUDIT_EVIDENCE_BYTES:
                        raise ValueError("persisted terminal audit exceeds bound")
                    terminal_audit = LiveDeliverySendAuditEvidenceV1.model_validate_json(
                        row["terminal_audit_json"]
                    )
                    if terminal_audit.evidence_fingerprint != audit_evidence_fingerprint(
                        terminal_audit
                    ):
                        raise ValueError("terminal audit fingerprint mismatch")
                admitted = receipt.lifecycle == "admitted_evidence_only"
                if admitted != (agent_result is not None and acknowledgement is not None):
                    raise ValueError("persisted Agent evidence mismatch")
                if (
                    receipt.send_attempt_id != attempt.send_attempt_id
                    or (
                        terminal_audit is not None
                        and (
                            terminal_audit.send_attempt_id != attempt.send_attempt_id
                            or terminal_audit.attempt_fingerprint
                            != attempt.attempt_fingerprint
                            or terminal_audit.receipt_fingerprint
                            != receipt.receipt_fingerprint
                            or terminal_audit.lifecycle != receipt.lifecycle
                        )
                    )
                ):
                    raise ValueError("persisted terminal linkage mismatch")
            elif any(
                row[name] is not None
                for name in (
                    "agent_result_json", "acknowledgement_json", "terminal_audit_json"
                )
            ):
                raise ValueError("persisted terminal evidence has no receipt")
            linkage = attempt.linkage
            if (
                row["enablement_id"] != linkage.enablement_id
                or row["enablement_fingerprint"] != linkage.enablement_fingerprint.value
                or row["preflight_id"] != linkage.preflight_id
                or row["delivery_preparation_id"] != linkage.delivery_preparation_id
                or row["preparation_fingerprint"] != linkage.preparation_fingerprint.value
                or row["intake_request_id"] != linkage.intake_request_id
                or row["send_attempt_id"] != attempt.send_attempt_id
                or row["attempt_fingerprint"] != attempt.attempt_fingerprint.value
                or envelope.send_attempt_id != attempt.send_attempt_id
                or audit.send_attempt_id != attempt.send_attempt_id
            ):
                raise ValueError("persisted identity mismatch")
            return LiveDeliverySendStoredEvidence(
                attempt, envelope, audit, receipt, agent_result,
                acknowledgement, terminal_audit,
            )
        except Exception as error:
            raise LiveDeliverySendStoreError("unavailable") from error
