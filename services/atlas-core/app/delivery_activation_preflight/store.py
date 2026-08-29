"""Independent append-only durable store for v0.29 preflight evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_RESULT_BYTES,
    DeliveryActivationPreflightResultV1,
    validate_preflight_result,
)

MAX_RECORDS_PER_OPERATOR = 16


class DeliveryActivationPreflightStoreError(RuntimeError):
    """Closed store failure that exposes neither rows nor filesystem details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DeliveryActivationPreflightStore:
    """Small SQLite evidence store with permanent multi-identity reservations."""

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
                    CREATE TABLE IF NOT EXISTS delivery_activation_preflights (
                        operator_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        delivery_preparation_id TEXT NOT NULL,
                        preparation_fingerprint TEXT NOT NULL,
                        intake_request_id TEXT NOT NULL,
                        delivery_attempt_id TEXT NOT NULL,
                        preflight_id TEXT NOT NULL,
                        preflight_fingerprint TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, preflight_id),
                        UNIQUE (operator_id, idempotency_key),
                        UNIQUE (operator_id, delivery_preparation_id),
                        UNIQUE (operator_id, intake_request_id),
                        UNIQUE (operator_id, delivery_attempt_id),
                        UNIQUE (operator_id, preflight_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise DeliveryActivationPreflightStoreError("unavailable") from error

    def resolve_reservation(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        delivery_preparation_id: str,
        preparation_fingerprint: str,
    ) -> DeliveryActivationPreflightResultV1 | None:
        rows = self._reservation_rows(
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            delivery_preparation_id=delivery_preparation_id,
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise DeliveryActivationPreflightStoreError("unavailable")
        row = rows[0]
        if (
            row["idempotency_key"] != idempotency_key
            or row["create_fingerprint"] != create_fingerprint
            or row["delivery_preparation_id"] != delivery_preparation_id
            or row["preparation_fingerprint"] != preparation_fingerprint
        ):
            raise DeliveryActivationPreflightStoreError("replay_conflict")
        return self._decode(row, operator_id=operator_id)

    def reserve(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        result: DeliveryActivationPreflightResultV1,
    ) -> tuple[DeliveryActivationPreflightResultV1, bool]:
        encoded = result.model_dump_json()
        if len(encoded.encode()) > MAX_RESULT_BYTES:
            raise DeliveryActivationPreflightStoreError("unavailable")
        linkage = result.linkage
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM delivery_activation_preflights
                    WHERE operator_id = ? AND (
                        idempotency_key = ? OR delivery_preparation_id = ?
                        OR intake_request_id = ? OR delivery_attempt_id = ?
                        OR preflight_id = ? OR preflight_fingerprint = ?
                    )
                    """,
                    (
                        operator_id,
                        idempotency_key,
                        result.delivery_preparation_id,
                        linkage.intake_request_id,
                        linkage.delivery_attempt_id,
                        result.preflight_id,
                        result.preflight_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1:
                        raise DeliveryActivationPreflightStoreError("unavailable")
                    row = rows[0]
                    exact = self._decode(row, operator_id=operator_id)
                    if not self._is_exact(row, idempotency_key, create_fingerprint, result):
                        raise DeliveryActivationPreflightStoreError("replay_conflict")
                    connection.execute("COMMIT")
                    return exact, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM delivery_activation_preflights WHERE operator_id = ?",
                    (operator_id,),
                ).fetchone()[0]
                if count >= MAX_RECORDS_PER_OPERATOR:
                    raise DeliveryActivationPreflightStoreError("quota_exceeded")
                connection.execute(
                    """
                    INSERT INTO delivery_activation_preflights (
                        operator_id, idempotency_key, create_fingerprint,
                        delivery_preparation_id, preparation_fingerprint,
                        intake_request_id, delivery_attempt_id, preflight_id,
                        preflight_fingerprint, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operator_id,
                        idempotency_key,
                        create_fingerprint,
                        result.delivery_preparation_id,
                        result.preparation_fingerprint.value,
                        linkage.intake_request_id,
                        linkage.delivery_attempt_id,
                        result.preflight_id,
                        result.preflight_fingerprint.value,
                        encoded,
                    ),
                )
                connection.execute("COMMIT")
                return result, True
        except DeliveryActivationPreflightStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise DeliveryActivationPreflightStoreError("replay_conflict") from error
        except sqlite3.Error as error:
            raise DeliveryActivationPreflightStoreError("unavailable") from error

    def get(
        self, *, operator_id: str, preflight_id: str
    ) -> DeliveryActivationPreflightResultV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM delivery_activation_preflights
                    WHERE operator_id = ? AND preflight_id = ?
                    """,
                    (operator_id, preflight_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise DeliveryActivationPreflightStoreError("unavailable") from error
        if row is None:
            raise DeliveryActivationPreflightStoreError("unavailable")
        return self._decode(row, operator_id=operator_id)

    def list_owned(self, *, operator_id: str) -> tuple[DeliveryActivationPreflightResultV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM delivery_activation_preflights
                    WHERE operator_id = ?
                    ORDER BY json_extract(result_json, '$.evaluated_at') DESC,
                             preflight_id DESC
                    """,
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise DeliveryActivationPreflightStoreError("unavailable") from error
        if len(rows) > MAX_RECORDS_PER_OPERATOR:
            raise DeliveryActivationPreflightStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    def _reservation_rows(
        self, *, operator_id: str, idempotency_key: str, delivery_preparation_id: str
    ) -> list[sqlite3.Row]:
        try:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT * FROM delivery_activation_preflights
                    WHERE operator_id = ?
                      AND (idempotency_key = ? OR delivery_preparation_id = ?)
                    """,
                    (operator_id, idempotency_key, delivery_preparation_id),
                ).fetchall()
        except sqlite3.Error as error:
            raise DeliveryActivationPreflightStoreError("unavailable") from error

    @staticmethod
    def _is_exact(
        row: sqlite3.Row,
        idempotency_key: str,
        create_fingerprint: str,
        result: DeliveryActivationPreflightResultV1,
    ) -> bool:
        return (
            row["idempotency_key"] == idempotency_key
            and row["create_fingerprint"] == create_fingerprint
            and row["delivery_preparation_id"] == result.delivery_preparation_id
            and row["preparation_fingerprint"] == result.preparation_fingerprint.value
            and row["intake_request_id"] == result.linkage.intake_request_id
            and row["delivery_attempt_id"] == result.linkage.delivery_attempt_id
            and row["preflight_id"] == result.preflight_id
            and row["preflight_fingerprint"] == result.preflight_fingerprint.value
        )

    @staticmethod
    def _decode(
        row: sqlite3.Row, *, operator_id: str
    ) -> DeliveryActivationPreflightResultV1:
        try:
            if len(row["result_json"].encode()) > MAX_RESULT_BYTES:
                raise ValueError("persisted record exceeds bound")
            value = DeliveryActivationPreflightResultV1.model_validate_json(
                row["result_json"]
            )
            validate_preflight_result(value, operator_id=operator_id)
            linkage = value.linkage
            if (
                value.delivery_preparation_id != row["delivery_preparation_id"]
                or value.preparation_fingerprint.value != row["preparation_fingerprint"]
                or linkage.intake_request_id != row["intake_request_id"]
                or linkage.delivery_attempt_id != row["delivery_attempt_id"]
                or value.preflight_id != row["preflight_id"]
                or value.preflight_fingerprint.value != row["preflight_fingerprint"]
            ):
                raise ValueError("persisted identity mismatch")
            return value
        except Exception as error:
            raise DeliveryActivationPreflightStoreError("unavailable") from error
