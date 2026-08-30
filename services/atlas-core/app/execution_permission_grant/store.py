"""Append-only durable store for v0.35 execution-permission evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    ExecutionPermissionGrantAuditEvidenceV1,
    ExecutionPermissionGrantReservationV1,
    ExecutionPermissionGrantV1,
)

MAX_RECORDS_PER_OPERATOR = 16


class ExecutionPermissionGrantStoreError(RuntimeError):
    """Closed failure that never exposes database or record details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ExecutionPermissionGrantStore:
    """SQLite append-only grant store with two permanent subject reservations."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path, timeout=5, isolation_level=None
        )
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
                    CREATE TABLE IF NOT EXISTS execution_permission_grants (
                        operator_id TEXT NOT NULL,
                        grant_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        v034_review_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        grant_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        grant_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, grant_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, candidate_record_id, v034_review_fingerprint),
                        UNIQUE (operator_id, grant_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise ExecutionPermissionGrantStoreError("unavailable") from error

    def resolve_reservation(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        idempotency_key_fingerprint: str,
        v034_review_fingerprint: str,
        request_fingerprint: str,
    ) -> ExecutionPermissionGrantV1 | None:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM execution_permission_grants
                    WHERE operator_id = ? AND (
                        idempotency_key_fingerprint = ? OR
                        (candidate_record_id = ? AND v034_review_fingerprint = ?)
                    )
                    """,
                    (
                        operator_id,
                        idempotency_key_fingerprint,
                        candidate_record_id,
                        v034_review_fingerprint,
                    ),
                ).fetchall()
        except sqlite3.Error as error:
            raise ExecutionPermissionGrantStoreError("unavailable") from error
        if not rows:
            return None
        if len(rows) != 1:
            raise ExecutionPermissionGrantStoreError("unavailable")
        row = rows[0]
        if not (
            row["candidate_record_id"] == candidate_record_id
            and row["idempotency_key_fingerprint"] == idempotency_key_fingerprint
            and row["v034_review_fingerprint"] == v034_review_fingerprint
            and row["request_fingerprint"] == request_fingerprint
        ):
            raise ExecutionPermissionGrantStoreError("conflict")
        return self._decode(row, operator_id=operator_id)

    def append(
        self,
        *,
        grant: ExecutionPermissionGrantV1,
        reservation: ExecutionPermissionGrantReservationV1,
        audit_evidence: ExecutionPermissionGrantAuditEvidenceV1,
    ) -> tuple[ExecutionPermissionGrantV1, bool]:
        grant_json = grant.model_dump_json()
        reservation_json = reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if (
            max(
                len(grant_json.encode()),
                len(reservation_json.encode()),
                len(audit_json.encode()),
            )
            > MAX_MODEL_BYTES
        ):
            raise ExecutionPermissionGrantStoreError("unavailable")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM execution_permission_grants
                    WHERE operator_id = ? AND (
                        idempotency_key_fingerprint = ? OR
                        (candidate_record_id = ? AND v034_review_fingerprint = ?) OR
                        grant_id = ? OR grant_fingerprint = ?
                    )
                    """,
                    (
                        grant.operator_id,
                        grant.idempotency_key_fingerprint.value,
                        grant.candidate_record_id,
                        grant.linkage.v034_review_fingerprint.value,
                        grant.grant_id,
                        grant.grant_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._request_matches(
                        rows[0], grant, reservation
                    ):
                        raise ExecutionPermissionGrantStoreError("conflict")
                    existing = self._decode(rows[0], operator_id=grant.operator_id)
                    connection.execute("COMMIT")
                    return existing, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM execution_permission_grants WHERE operator_id = ?",
                    (grant.operator_id,),
                ).fetchone()[0]
                if count >= MAX_RECORDS_PER_OPERATOR:
                    raise ExecutionPermissionGrantStoreError("quota_exceeded")
                connection.execute(
                    """
                    INSERT INTO execution_permission_grants (
                        operator_id, grant_id, candidate_record_id,
                        idempotency_key_fingerprint, v034_review_fingerprint,
                        request_fingerprint, grant_fingerprint, recorded_at,
                        grant_json, reservation_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        grant.operator_id,
                        grant.grant_id,
                        grant.candidate_record_id,
                        grant.idempotency_key_fingerprint.value,
                        grant.linkage.v034_review_fingerprint.value,
                        grant.request_fingerprint.value,
                        grant.grant_fingerprint.value,
                        grant.recorded_at,
                        grant_json,
                        reservation_json,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return grant, True
        except ExecutionPermissionGrantStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise ExecutionPermissionGrantStoreError("conflict") from error
        except sqlite3.Error as error:
            raise ExecutionPermissionGrantStoreError("unavailable") from error

    def get(self, *, operator_id: str, grant_id: str) -> ExecutionPermissionGrantV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM execution_permission_grants
                    WHERE operator_id = ? AND grant_id = ?""",
                    (operator_id, grant_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise ExecutionPermissionGrantStoreError("unavailable") from error
        if row is None:
            raise ExecutionPermissionGrantStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(self, *, operator_id: str) -> tuple[ExecutionPermissionGrantV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM execution_permission_grants
                    WHERE operator_id = ? ORDER BY recorded_at DESC, grant_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise ExecutionPermissionGrantStoreError("unavailable") from error
        if len(rows) > MAX_RECORDS_PER_OPERATOR:
            raise ExecutionPermissionGrantStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    @staticmethod
    def _request_matches(
        row: sqlite3.Row,
        grant: ExecutionPermissionGrantV1,
        reservation: ExecutionPermissionGrantReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == grant.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == grant.candidate_record_id
            == reservation.candidate_record_id
            and row["idempotency_key_fingerprint"]
            == grant.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["v034_review_fingerprint"]
            == grant.linkage.v034_review_fingerprint.value
            == reservation.v034_review_fingerprint.value
            and row["request_fingerprint"]
            == grant.request_fingerprint.value
            == reservation.request_fingerprint.value
        )

    @staticmethod
    def _is_exact(
        row: sqlite3.Row,
        grant: ExecutionPermissionGrantV1,
        reservation: ExecutionPermissionGrantReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == grant.operator_id == reservation.operator_id
            and row["grant_id"] == grant.grant_id == reservation.grant_id
            and row["candidate_record_id"]
            == grant.candidate_record_id
            == reservation.candidate_record_id
            and row["idempotency_key_fingerprint"]
            == grant.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["v034_review_fingerprint"]
            == grant.linkage.v034_review_fingerprint.value
            == reservation.v034_review_fingerprint.value
            and row["request_fingerprint"]
            == grant.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["grant_fingerprint"] == grant.grant_fingerprint.value
            and row["grant_json"] == grant.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    @staticmethod
    def _decode(row: sqlite3.Row, *, operator_id: str) -> ExecutionPermissionGrantV1:
        try:
            if (
                max(
                    len(row["grant_json"].encode()),
                    len(row["reservation_json"].encode()),
                    len(row["audit_json"].encode()),
                )
                > MAX_MODEL_BYTES
            ):
                raise ValueError("persisted record exceeds bound")
            grant = ExecutionPermissionGrantV1.model_validate_json(row["grant_json"])
            reservation = ExecutionPermissionGrantReservationV1.model_validate_json(
                row["reservation_json"]
            )
            audit = ExecutionPermissionGrantAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                operator_id != row["operator_id"]
                or not ExecutionPermissionGrantStore._is_exact(row, grant, reservation)
                or audit.outcome != "recorded"
                or audit.grant_id != grant.grant_id
                or audit.candidate_record_id != grant.candidate_record_id
                or audit.request_fingerprint != grant.request_fingerprint
                or audit.grant_fingerprint != grant.grant_fingerprint
                or audit.occurred_at != grant.recorded_at
            ):
                raise ValueError("persisted identity mismatch")
            return grant
        except Exception as error:
            raise ExecutionPermissionGrantStoreError("unavailable") from error
