"""Append-only durable store for v0.36 admission evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    InstallationExecutionAdmissionAuditEvidenceV1,
    InstallationExecutionAdmissionReservationV1,
    InstallationExecutionAdmissionV1,
)

MAX_RECORDS_PER_OPERATOR = 16


class InstallationExecutionAdmissionStoreError(RuntimeError):
    """Closed storage failure that discloses no record or database detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InstallationExecutionAdmissionStore:
    """SQLite append-only evidence with permanent key and grant reservations."""

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
                    CREATE TABLE IF NOT EXISTS installation_execution_admissions (
                        operator_id TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        v035_grant_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        admission_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        admission_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, admission_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (
                            operator_id, candidate_record_id,
                            v035_grant_fingerprint
                        ),
                        UNIQUE (operator_id, admission_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise InstallationExecutionAdmissionStoreError("unavailable") from error

    def resolve_reservation(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        idempotency_key_fingerprint: str,
        v035_grant_fingerprint: str,
        request_fingerprint: str,
    ) -> InstallationExecutionAdmissionV1 | None:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM installation_execution_admissions
                    WHERE operator_id = ? AND (
                        idempotency_key_fingerprint = ? OR
                        (candidate_record_id = ? AND v035_grant_fingerprint = ?)
                    )
                    """,
                    (
                        operator_id,
                        idempotency_key_fingerprint,
                        candidate_record_id,
                        v035_grant_fingerprint,
                    ),
                ).fetchall()
        except sqlite3.Error as error:
            raise InstallationExecutionAdmissionStoreError("unavailable") from error
        if not rows:
            return None
        if len(rows) != 1:
            raise InstallationExecutionAdmissionStoreError("unavailable")
        row = rows[0]
        if not (
            row["candidate_record_id"] == candidate_record_id
            and row["idempotency_key_fingerprint"] == idempotency_key_fingerprint
            and row["v035_grant_fingerprint"] == v035_grant_fingerprint
            and row["request_fingerprint"] == request_fingerprint
        ):
            raise InstallationExecutionAdmissionStoreError("conflict")
        return self._decode(row, operator_id=operator_id)

    def append(
        self,
        *,
        admission: InstallationExecutionAdmissionV1,
        reservation: InstallationExecutionAdmissionReservationV1,
        audit_evidence: InstallationExecutionAdmissionAuditEvidenceV1,
    ) -> tuple[InstallationExecutionAdmissionV1, bool]:
        admission_json = admission.model_dump_json()
        reservation_json = reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if max(
            len(admission_json.encode()),
            len(reservation_json.encode()),
            len(audit_json.encode()),
        ) > MAX_MODEL_BYTES:
            raise InstallationExecutionAdmissionStoreError("unavailable")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM installation_execution_admissions
                    WHERE operator_id = ? AND (
                        idempotency_key_fingerprint = ? OR
                        (candidate_record_id = ? AND v035_grant_fingerprint = ?) OR
                        admission_id = ? OR admission_fingerprint = ?
                    )
                    """,
                    (
                        admission.operator_id,
                        admission.idempotency_key_fingerprint.value,
                        admission.candidate_record_id,
                        admission.linkage.v035_grant_fingerprint.value,
                        admission.admission_id,
                        admission.admission_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._request_matches(
                        rows[0], admission, reservation
                    ):
                        raise InstallationExecutionAdmissionStoreError("conflict")
                    existing = self._decode(
                        rows[0], operator_id=admission.operator_id
                    )
                    connection.execute("COMMIT")
                    return existing, False
                count = connection.execute(
                    """SELECT COUNT(*) FROM installation_execution_admissions
                    WHERE operator_id = ?""",
                    (admission.operator_id,),
                ).fetchone()[0]
                if count >= MAX_RECORDS_PER_OPERATOR:
                    raise InstallationExecutionAdmissionStoreError("quota_exceeded")
                connection.execute(
                    """
                    INSERT INTO installation_execution_admissions (
                        operator_id, admission_id, candidate_record_id,
                        idempotency_key_fingerprint, v035_grant_fingerprint,
                        request_fingerprint, admission_fingerprint, recorded_at,
                        admission_json, reservation_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        admission.operator_id,
                        admission.admission_id,
                        admission.candidate_record_id,
                        admission.idempotency_key_fingerprint.value,
                        admission.linkage.v035_grant_fingerprint.value,
                        admission.request_fingerprint.value,
                        admission.admission_fingerprint.value,
                        admission.recorded_at,
                        admission_json,
                        reservation_json,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return admission, True
        except InstallationExecutionAdmissionStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise InstallationExecutionAdmissionStoreError("conflict") from error
        except sqlite3.Error as error:
            raise InstallationExecutionAdmissionStoreError("unavailable") from error

    def get(
        self, *, operator_id: str, admission_id: str
    ) -> InstallationExecutionAdmissionV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM installation_execution_admissions
                    WHERE operator_id = ? AND admission_id = ?""",
                    (operator_id, admission_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise InstallationExecutionAdmissionStoreError("unavailable") from error
        if row is None:
            raise InstallationExecutionAdmissionStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str
    ) -> tuple[InstallationExecutionAdmissionV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM installation_execution_admissions
                    WHERE operator_id = ?
                    ORDER BY recorded_at DESC, admission_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise InstallationExecutionAdmissionStoreError("unavailable") from error
        if len(rows) > MAX_RECORDS_PER_OPERATOR:
            raise InstallationExecutionAdmissionStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    @staticmethod
    def _request_matches(
        row: sqlite3.Row,
        admission: InstallationExecutionAdmissionV1,
        reservation: InstallationExecutionAdmissionReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == admission.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == admission.candidate_record_id
            == reservation.candidate_record_id
            and row["idempotency_key_fingerprint"]
            == admission.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["v035_grant_fingerprint"]
            == admission.linkage.v035_grant_fingerprint.value
            == reservation.v035_grant_fingerprint.value
            and row["request_fingerprint"]
            == admission.request_fingerprint.value
            == reservation.request_fingerprint.value
        )

    @staticmethod
    def _is_exact(
        row: sqlite3.Row,
        admission: InstallationExecutionAdmissionV1,
        reservation: InstallationExecutionAdmissionReservationV1,
    ) -> bool:
        return (
            InstallationExecutionAdmissionStore._request_matches(
                row, admission, reservation
            )
            and row["admission_id"]
            == admission.admission_id
            == reservation.admission_id
            and row["admission_fingerprint"]
            == admission.admission_fingerprint.value
            and row["admission_json"] == admission.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    @staticmethod
    def _decode(
        row: sqlite3.Row, *, operator_id: str
    ) -> InstallationExecutionAdmissionV1:
        try:
            if max(
                len(row["admission_json"].encode()),
                len(row["reservation_json"].encode()),
                len(row["audit_json"].encode()),
            ) > MAX_MODEL_BYTES:
                raise ValueError("persisted record exceeds bound")
            admission = InstallationExecutionAdmissionV1.model_validate_json(
                row["admission_json"]
            )
            reservation = InstallationExecutionAdmissionReservationV1.model_validate_json(
                row["reservation_json"]
            )
            audit = InstallationExecutionAdmissionAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                operator_id != row["operator_id"]
                or not InstallationExecutionAdmissionStore._is_exact(
                    row, admission, reservation
                )
                or audit.outcome != "recorded"
                or audit.admission_id != admission.admission_id
                or audit.candidate_record_id != admission.candidate_record_id
                or audit.request_fingerprint != admission.request_fingerprint
                or audit.idempotency_key_fingerprint
                != admission.idempotency_key_fingerprint
                or audit.v035_grant_fingerprint
                != admission.linkage.v035_grant_fingerprint
                or audit.linkage_fingerprint
                != admission.linkage.linkage_fingerprint
                or audit.eligibility_fingerprint
                != admission.runner_eligibility.eligibility_fingerprint
                or audit.admission_fingerprint != admission.admission_fingerprint
                or audit.occurred_at != admission.recorded_at
                or audit.blocker_codes != admission.blockers
            ):
                raise ValueError("persisted identity mismatch")
            return admission
        except Exception as error:
            raise InstallationExecutionAdmissionStoreError("unavailable") from error
