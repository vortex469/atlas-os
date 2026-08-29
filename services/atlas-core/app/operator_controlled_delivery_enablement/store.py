"""Independent append-only durable store for v0.30 enablement evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_RECORD_BYTES,
    OperatorControlledDeliveryEnablementRecordV1,
    validate_enablement_record,
)

MAX_RECORDS_PER_OPERATOR = 16


class OperatorControlledDeliveryEnablementStoreError(RuntimeError):
    """Closed store failure that exposes no row or filesystem detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OperatorControlledDeliveryEnablementStore:
    """Small SQLite store with permanent multi-identity reservations."""

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
                    CREATE TABLE IF NOT EXISTS operator_delivery_enablements (
                        operator_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        preflight_id TEXT NOT NULL,
                        preflight_fingerprint TEXT NOT NULL,
                        delivery_preparation_id TEXT NOT NULL,
                        preparation_fingerprint TEXT NOT NULL,
                        enablement_id TEXT NOT NULL,
                        enablement_fingerprint TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, enablement_id),
                        UNIQUE (operator_id, idempotency_key),
                        UNIQUE (operator_id, preflight_id),
                        UNIQUE (operator_id, preflight_fingerprint),
                        UNIQUE (operator_id, delivery_preparation_id),
                        UNIQUE (operator_id, preparation_fingerprint),
                        UNIQUE (operator_id, enablement_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable") from error

    def resolve_reservation(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        preflight_id: str,
        preflight_fingerprint: str,
    ) -> OperatorControlledDeliveryEnablementRecordV1 | None:
        rows = self._reservation_rows(
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            preflight_id=preflight_id,
            preflight_fingerprint=preflight_fingerprint,
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable")
        row = rows[0]
        if (
            row["idempotency_key"] != idempotency_key
            or row["create_fingerprint"] != create_fingerprint
            or row["preflight_id"] != preflight_id
            or row["preflight_fingerprint"] != preflight_fingerprint
        ):
            raise OperatorControlledDeliveryEnablementStoreError("replay_conflict")
        return self._decode(row, operator_id=operator_id)

    def reserve(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        record: OperatorControlledDeliveryEnablementRecordV1,
    ) -> tuple[OperatorControlledDeliveryEnablementRecordV1, bool]:
        encoded = record.model_dump_json()
        if len(encoded.encode()) > MAX_RECORD_BYTES:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM operator_delivery_enablements
                    WHERE operator_id = ? AND (
                        idempotency_key = ? OR preflight_id = ?
                        OR preflight_fingerprint = ?
                        OR delivery_preparation_id = ?
                        OR preparation_fingerprint = ?
                        OR enablement_id = ? OR enablement_fingerprint = ?
                    )
                    """,
                    (
                        operator_id, idempotency_key, record.preflight_id,
                        record.preflight_fingerprint.value,
                        record.delivery_preparation_id,
                        record.preparation_fingerprint.value,
                        record.enablement_id, record.enablement_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1:
                        raise OperatorControlledDeliveryEnablementStoreError("unavailable")
                    exact = self._decode(rows[0], operator_id=operator_id)
                    if not self._is_exact(
                        rows[0], idempotency_key, create_fingerprint, record
                    ):
                        raise OperatorControlledDeliveryEnablementStoreError(
                            "replay_conflict"
                        )
                    connection.execute("COMMIT")
                    return exact, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM operator_delivery_enablements WHERE operator_id = ?",
                    (operator_id,),
                ).fetchone()[0]
                if count >= MAX_RECORDS_PER_OPERATOR:
                    raise OperatorControlledDeliveryEnablementStoreError("quota_exceeded")
                connection.execute(
                    """
                    INSERT INTO operator_delivery_enablements (
                        operator_id, idempotency_key, create_fingerprint,
                        preflight_id, preflight_fingerprint,
                        delivery_preparation_id, preparation_fingerprint,
                        enablement_id, enablement_fingerprint, record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operator_id, idempotency_key, create_fingerprint,
                        record.preflight_id, record.preflight_fingerprint.value,
                        record.delivery_preparation_id,
                        record.preparation_fingerprint.value, record.enablement_id,
                        record.enablement_fingerprint.value, encoded,
                    ),
                )
                connection.execute("COMMIT")
                return record, True
        except OperatorControlledDeliveryEnablementStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OperatorControlledDeliveryEnablementStoreError(
                "replay_conflict"
            ) from error
        except sqlite3.Error as error:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable") from error

    def get(
        self, *, operator_id: str, enablement_id: str
    ) -> OperatorControlledDeliveryEnablementRecordV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM operator_delivery_enablements
                    WHERE operator_id = ? AND enablement_id = ?""",
                    (operator_id, enablement_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable") from error
        if row is None:
            raise OperatorControlledDeliveryEnablementStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str
    ) -> tuple[OperatorControlledDeliveryEnablementRecordV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM operator_delivery_enablements
                    WHERE operator_id = ?
                    ORDER BY json_extract(record_json, '$.enabled_at') DESC,
                             enablement_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable") from error
        if len(rows) > MAX_RECORDS_PER_OPERATOR:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    def _reservation_rows(
        self, *, operator_id: str, idempotency_key: str,
        preflight_id: str, preflight_fingerprint: str,
    ) -> list[sqlite3.Row]:
        try:
            with self._connect() as connection:
                return connection.execute(
                    """SELECT * FROM operator_delivery_enablements
                    WHERE operator_id = ? AND (
                        idempotency_key = ? OR preflight_id = ?
                        OR preflight_fingerprint = ?
                    )""",
                    (operator_id, idempotency_key, preflight_id, preflight_fingerprint),
                ).fetchall()
        except sqlite3.Error as error:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable") from error

    @staticmethod
    def _is_exact(row, idempotency_key, create_fingerprint, record) -> bool:
        return (
            row["idempotency_key"] == idempotency_key
            and row["create_fingerprint"] == create_fingerprint
            and row["preflight_id"] == record.preflight_id
            and row["preflight_fingerprint"] == record.preflight_fingerprint.value
            and row["delivery_preparation_id"] == record.delivery_preparation_id
            and row["preparation_fingerprint"] == record.preparation_fingerprint.value
        )

    @staticmethod
    def _decode(row, *, operator_id: str):
        try:
            if len(row["record_json"].encode()) > MAX_RECORD_BYTES:
                raise ValueError("persisted record exceeds bound")
            record = OperatorControlledDeliveryEnablementRecordV1.model_validate_json(
                row["record_json"]
            )
            validate_enablement_record(record, operator_id=operator_id)
            if (
                record.preflight_id != row["preflight_id"]
                or record.preflight_fingerprint.value != row["preflight_fingerprint"]
                or record.delivery_preparation_id != row["delivery_preparation_id"]
                or record.preparation_fingerprint.value != row["preparation_fingerprint"]
                or record.enablement_id != row["enablement_id"]
                or record.enablement_fingerprint.value != row["enablement_fingerprint"]
            ):
                raise ValueError("persisted identity mismatch")
            return record
        except Exception as error:
            raise OperatorControlledDeliveryEnablementStoreError("unavailable") from error
