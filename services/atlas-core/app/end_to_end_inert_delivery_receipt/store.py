"""Append-only durable storage for v0.33 inert delivery receipt evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .contract import (
    MAX_AUDIT_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_VERIFICATION_BYTES,
    EndToEndInertDeliveryAuditEvidenceV1,
    EndToEndInertDeliveryReceiptV1,
    EndToEndInertDeliveryVerificationV1,
)

MAX_RECORDS_PER_OPERATOR = 1000


class InertDeliveryReceiptStoreError(RuntimeError):
    """Durable evidence could not be safely read or appended."""


class InertDeliveryReceiptConflictError(InertDeliveryReceiptStoreError):
    pass


class InertDeliveryReceiptQuotaError(InertDeliveryReceiptStoreError):
    pass


class InertDeliveryReceiptUnavailableError(InertDeliveryReceiptStoreError):
    pass


@dataclass(frozen=True)
class StoredInertDeliveryReceipt:
    receipt: EndToEndInertDeliveryReceiptV1
    verification: EndToEndInertDeliveryVerificationV1
    audit_evidence: EndToEndInertDeliveryAuditEvidenceV1


@dataclass(frozen=True)
class ReservationDisposition:
    disposition: str
    stored: StoredInertDeliveryReceipt | None


class InertDeliveryReceiptStore:
    """SQLite append-only receipt store with permanent attempt reservations."""

    def __init__(self, database: Path, *, quota: int = MAX_RECORDS_PER_OPERATOR) -> None:
        self._database = Path(database)
        self._quota = quota
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self._database.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS inert_delivery_receipt_reservations (
                        operator_id TEXT NOT NULL,
                        send_attempt_id TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        receipt_id TEXT NOT NULL,
                        PRIMARY KEY (operator_id, send_attempt_id),
                        UNIQUE (operator_id, receipt_id)
                    );
                    CREATE TABLE IF NOT EXISTS inert_delivery_receipts (
                        operator_id TEXT NOT NULL,
                        receipt_id TEXT NOT NULL,
                        send_attempt_id TEXT NOT NULL,
                        receipt_json TEXT NOT NULL,
                        verification_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, receipt_id),
                        UNIQUE (operator_id, send_attempt_id)
                    );
                    """
                )
        except Exception as error:
            raise InertDeliveryReceiptUnavailableError("store unavailable") from error

    def reserve(
        self,
        *,
        operator_id: str,
        send_attempt_id: str,
        request_fingerprint: str,
        idempotency_key_fingerprint: str,
        receipt_id: str,
    ) -> ReservationDisposition:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT request_fingerprint, idempotency_key_fingerprint,
                              receipt_id
                       FROM inert_delivery_receipt_reservations
                       WHERE operator_id = ? AND send_attempt_id = ?""",
                    (operator_id, send_attempt_id),
                ).fetchone()
                if row is not None:
                    if (
                        row["request_fingerprint"] != request_fingerprint
                        or row["idempotency_key_fingerprint"]
                        != idempotency_key_fingerprint
                    ):
                        raise InertDeliveryReceiptConflictError("reservation conflict")
                    stored = self._get_with_connection(
                        connection,
                        operator_id=operator_id,
                        receipt_id=row["receipt_id"],
                    )
                    if stored is None:
                        raise InertDeliveryReceiptUnavailableError(
                            "permanent reservation is incomplete"
                        )
                    return ReservationDisposition("exact_duplicate", stored)
                count = connection.execute(
                    "SELECT COUNT(*) FROM inert_delivery_receipts WHERE operator_id = ?",
                    (operator_id,),
                ).fetchone()[0]
                if count >= self._quota:
                    raise InertDeliveryReceiptQuotaError("operator quota exceeded")
                connection.execute(
                    """INSERT INTO inert_delivery_receipt_reservations
                       (operator_id, send_attempt_id, request_fingerprint,
                        idempotency_key_fingerprint, receipt_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        operator_id,
                        send_attempt_id,
                        request_fingerprint,
                        idempotency_key_fingerprint,
                        receipt_id,
                    ),
                )
                return ReservationDisposition("reserved", None)
        except InertDeliveryReceiptStoreError:
            raise
        except Exception as error:
            raise InertDeliveryReceiptUnavailableError("store unavailable") from error

    def append(
        self,
        *,
        operator_id: str,
        stored: StoredInertDeliveryReceipt,
    ) -> StoredInertDeliveryReceipt:
        receipt_json = stored.receipt.model_dump_json()
        verification_json = stored.verification.model_dump_json()
        audit_json = stored.audit_evidence.model_dump_json()
        if (
            len(receipt_json.encode()) > MAX_RECEIPT_BYTES
            or len(verification_json.encode()) > MAX_VERIFICATION_BYTES
            or len(audit_json.encode()) > MAX_AUDIT_BYTES
        ):
            raise InertDeliveryReceiptUnavailableError("record exceeds bound")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                reservation = connection.execute(
                    """SELECT receipt_id FROM inert_delivery_receipt_reservations
                       WHERE operator_id = ? AND send_attempt_id = ?""",
                    (operator_id, stored.receipt.send_attempt_id),
                ).fetchone()
                if reservation is None or reservation["receipt_id"] != stored.receipt.receipt_id:
                    raise InertDeliveryReceiptUnavailableError(
                        "receipt has no exact permanent reservation"
                    )
                existing = self._get_with_connection(
                    connection,
                    operator_id=operator_id,
                    receipt_id=stored.receipt.receipt_id,
                )
                if existing is not None:
                    if existing != stored:
                        raise InertDeliveryReceiptConflictError("append conflict")
                    return existing
                connection.execute(
                    """INSERT INTO inert_delivery_receipts
                       (operator_id, receipt_id, send_attempt_id, receipt_json,
                        verification_json, audit_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        operator_id,
                        stored.receipt.receipt_id,
                        stored.receipt.send_attempt_id,
                        receipt_json,
                        verification_json,
                        audit_json,
                    ),
                )
                return stored
        except InertDeliveryReceiptStoreError:
            raise
        except Exception as error:
            raise InertDeliveryReceiptUnavailableError("append unavailable") from error

    def get_owned(
        self, *, operator_id: str, receipt_id: str
    ) -> StoredInertDeliveryReceipt | None:
        try:
            with self._connect() as connection:
                return self._get_with_connection(
                    connection, operator_id=operator_id, receipt_id=receipt_id
                )
        except InertDeliveryReceiptStoreError:
            raise
        except Exception as error:
            raise InertDeliveryReceiptUnavailableError("read unavailable") from error

    def list_owned(self, *, operator_id: str) -> tuple[StoredInertDeliveryReceipt, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT receipt_id FROM inert_delivery_receipts
                       WHERE operator_id = ? ORDER BY rowid""",
                    (operator_id,),
                ).fetchall()
                values = []
                for row in rows:
                    stored = self._get_with_connection(
                        connection,
                        operator_id=operator_id,
                        receipt_id=row["receipt_id"],
                    )
                    if stored is None:
                        raise InertDeliveryReceiptUnavailableError("record disappeared")
                    values.append(stored)
                return tuple(values)
        except InertDeliveryReceiptStoreError:
            raise
        except Exception as error:
            raise InertDeliveryReceiptUnavailableError("list unavailable") from error

    def _get_with_connection(
        self,
        connection: sqlite3.Connection,
        *,
        operator_id: str,
        receipt_id: str,
    ) -> StoredInertDeliveryReceipt | None:
        row = connection.execute(
            """SELECT receipt_json, verification_json, audit_json
               FROM inert_delivery_receipts
               WHERE operator_id = ? AND receipt_id = ?""",
            (operator_id, receipt_id),
        ).fetchone()
        if row is None:
            return None
        try:
            receipt = EndToEndInertDeliveryReceiptV1.model_validate_json(
                row["receipt_json"]
            )
            verification = EndToEndInertDeliveryVerificationV1.model_validate_json(
                row["verification_json"]
            )
            audit = EndToEndInertDeliveryAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            stored = StoredInertDeliveryReceipt(receipt, verification, audit)
            if receipt.verification != verification:
                raise ValueError("stored verification mismatch")
            if (
                audit.receipt_id != receipt.receipt_id
                or audit.receipt_fingerprint != receipt.receipt_fingerprint
                or audit.verification_fingerprint
                != verification.verification_fingerprint
            ):
                raise ValueError("stored audit mismatch")
            return stored
        except Exception as error:
            raise InertDeliveryReceiptUnavailableError("stored evidence corrupt") from error


def canonical_json(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")  # type: ignore[union-attr]
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
