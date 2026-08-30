"""Append-only durable store for v0.37 runner binding plan evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    RunnerBindingPlanAuditEvidenceV1,
    RunnerBindingPlanReservationV1,
    RunnerBindingPlanV1,
    opaque_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class RunnerBindingPlanStoreError(RuntimeError):
    """Closed storage failure that discloses no record or database detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RunnerBindingPlanStore:
    """SQLite append-only evidence with permanent key and subject reservations."""

    def __init__(
        self, database_path: str | Path, *, max_records_per_operator: int = MAX_RECORDS_PER_OPERATOR
    ) -> None:
        self.database_path = Path(database_path)
        self.max_records_per_operator = max_records_per_operator
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
                    CREATE TABLE IF NOT EXISTS runner_binding_plans (
                        operator_id TEXT NOT NULL,
                        plan_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        admission_valid_until TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        execution_admission_fingerprint TEXT NOT NULL,
                        runner_reference_fingerprint TEXT NOT NULL,
                        limits_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        plan_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        plan_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, plan_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, plan_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise RunnerBindingPlanStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        admission_valid_until: str,
    ) -> RunnerBindingPlanV1 | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM runner_binding_plans
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
        except sqlite3.Error as error:
            raise RunnerBindingPlanStoreError("unavailable") from error
        if row is None:
            return None
        if row["admission_valid_until"] != admission_valid_until:
            raise RunnerBindingPlanStoreError("conflict")
        return self._decode(row, operator_id=operator_id)

    def append(
        self,
        *,
        plan: RunnerBindingPlanV1,
        reservation: RunnerBindingPlanReservationV1,
        audit_evidence: RunnerBindingPlanAuditEvidenceV1,
        admission_valid_until: str,
    ) -> tuple[RunnerBindingPlanV1, bool]:
        plan_json = plan.model_dump_json()
        reservation_json = reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if max(
            len(value.encode())
            for value in (plan_json, reservation_json, audit_json)
        ) > MAX_MODEL_BYTES:
            raise RunnerBindingPlanStoreError("unavailable")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM runner_binding_plans
                    WHERE operator_id = ? AND (
                        idempotency_key_fingerprint = ? OR subject_fingerprint = ? OR
                        plan_id = ? OR plan_fingerprint = ?)
                    """,
                    (
                        plan.operator_id,
                        plan.idempotency_key_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        plan.plan_id,
                        plan.plan_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact(rows[0], plan, reservation):
                        raise RunnerBindingPlanStoreError("conflict")
                    existing = self._decode(rows[0], operator_id=plan.operator_id)
                    connection.execute("COMMIT")
                    return existing, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM runner_binding_plans WHERE operator_id = ?",
                    (plan.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise RunnerBindingPlanStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO runner_binding_plans (
                        operator_id, plan_id, candidate_record_id,
                        admission_valid_until,
                        idempotency_key_fingerprint, execution_admission_fingerprint,
                        runner_reference_fingerprint, limits_fingerprint,
                        subject_fingerprint, request_fingerprint, plan_fingerprint,
                        recorded_at, plan_json, reservation_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        plan.operator_id, plan.plan_id, plan.candidate_record_id,
                        admission_valid_until,
                        plan.idempotency_key_fingerprint.value,
                        plan.linkage.execution_admission_fingerprint.value,
                        plan.linkage.runner_reference_fingerprint.value,
                        plan.linkage.limits_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        plan.request_fingerprint.value, plan.plan_fingerprint.value,
                        plan.recorded_at, plan_json, reservation_json, audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return plan, True
        except RunnerBindingPlanStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise RunnerBindingPlanStoreError("conflict") from error
        except sqlite3.Error as error:
            raise RunnerBindingPlanStoreError("unavailable") from error

    def get(self, *, operator_id: str, plan_id: str) -> RunnerBindingPlanV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM runner_binding_plans WHERE operator_id = ? AND plan_id = ?",
                    (operator_id, plan_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise RunnerBindingPlanStoreError("unavailable") from error
        if row is None:
            raise RunnerBindingPlanStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(self, *, operator_id: str) -> tuple[RunnerBindingPlanV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM runner_binding_plans WHERE operator_id = ?
                    ORDER BY recorded_at DESC, plan_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise RunnerBindingPlanStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise RunnerBindingPlanStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    @staticmethod
    def _is_exact(row: sqlite3.Row, plan: RunnerBindingPlanV1, reservation: RunnerBindingPlanReservationV1) -> bool:
        return (
            row["operator_id"] == plan.operator_id == reservation.operator_id
            and row["candidate_record_id"] == plan.candidate_record_id == reservation.candidate_record_id
            and row["plan_id"] == plan.plan_id == reservation.plan_id
            and row["idempotency_key_fingerprint"] == plan.idempotency_key_fingerprint.value == reservation.idempotency_key_fingerprint.value
            and row["execution_admission_fingerprint"] == plan.linkage.execution_admission_fingerprint.value == reservation.execution_admission_fingerprint.value
            and row["runner_reference_fingerprint"] == plan.linkage.runner_reference_fingerprint.value == reservation.runner_reference_fingerprint.value
            and row["limits_fingerprint"] == plan.linkage.limits_fingerprint.value == reservation.limits_fingerprint.value
            and row["subject_fingerprint"] == reservation.subject_fingerprint.value
            and row["request_fingerprint"] == plan.request_fingerprint.value == reservation.request_fingerprint.value
            and row["plan_fingerprint"] == plan.plan_fingerprint.value
            and row["plan_json"] == plan.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    @staticmethod
    def _decode(row: sqlite3.Row, *, operator_id: str) -> RunnerBindingPlanV1:
        try:
            payloads = (row["plan_json"], row["reservation_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > MAX_MODEL_BYTES:
                raise ValueError("persisted record exceeds bound")
            plan = RunnerBindingPlanV1.model_validate_json(row["plan_json"])
            reservation = RunnerBindingPlanReservationV1.model_validate_json(row["reservation_json"])
            audit = RunnerBindingPlanAuditEvidenceV1.model_validate_json(row["audit_json"])
            if (
                operator_id != row["operator_id"]
                or row["admission_valid_until"] < plan.valid_until
                or not RunnerBindingPlanStore._is_exact(row, plan, reservation)
                or audit.event != "runner_binding_plan_recorded"
                or audit.outcome != "recorded"
                or audit.operator_fingerprint
                != opaque_fingerprint(
                    "atlas:runner-binding-plan-operator:v1", plan.operator_id
                )
                or audit.candidate_record_fingerprint
                != opaque_fingerprint(
                    "atlas:runner-binding-plan-candidate:v1",
                    plan.candidate_record_id,
                )
                or audit.plan_fingerprint != plan.plan_fingerprint
                or audit.occurred_at != plan.recorded_at
            ):
                raise ValueError("persisted identity mismatch")
            return plan
        except Exception as error:
            raise RunnerBindingPlanStoreError("unavailable") from error
