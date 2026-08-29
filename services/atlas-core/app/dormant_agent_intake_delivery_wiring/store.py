"""Append-only evidence store for dormant no-send preparations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import CoreAgentIntakeDeliveryPreparationV1

MAX_RECORDS_PER_OPERATOR = 16
MAX_RECORD_BYTES = 96 * 1024


class DormantDeliveryStoreError(RuntimeError):
    """Closed store failure that reveals no record or filesystem detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DormantAgentIntakeDeliveryPreparationStore:
    """Small append-only SQLite store with permanent no-replay reservations."""

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
                    CREATE TABLE IF NOT EXISTS dormant_agent_intake_preparations (
                        operator_id TEXT NOT NULL,
                        delivery_preparation_id TEXT NOT NULL,
                        dispatch_envelope_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        preparation_json TEXT NOT NULL,
                        preparation_fingerprint TEXT NOT NULL,
                        PRIMARY KEY (operator_id, delivery_preparation_id),
                        UNIQUE (operator_id, dispatch_envelope_id),
                        UNIQUE (operator_id, idempotency_key)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise DormantDeliveryStoreError("unavailable") from error

    def reserve(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        preparation: CoreAgentIntakeDeliveryPreparationV1,
    ) -> tuple[CoreAgentIntakeDeliveryPreparationV1, bool]:
        encoded = preparation.model_dump_json()
        if len(encoded.encode()) > MAX_RECORD_BYTES:
            raise DormantDeliveryStoreError("unavailable")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT * FROM dormant_agent_intake_preparations
                    WHERE operator_id = ?
                      AND (idempotency_key = ? OR dispatch_envelope_id = ?)
                    """,
                    (
                        operator_id,
                        idempotency_key,
                        preparation.source.dispatch_envelope_id,
                    ),
                ).fetchone()
                if row is not None:
                    exact = self._decode(row)
                    if (
                        row["idempotency_key"] != idempotency_key
                        or row["create_fingerprint"] != create_fingerprint
                        or row["dispatch_envelope_id"]
                        != preparation.source.dispatch_envelope_id
                    ):
                        raise DormantDeliveryStoreError("replay_conflict")
                    connection.execute("COMMIT")
                    return exact, False
                count = connection.execute(
                    """
                    SELECT COUNT(*) FROM dormant_agent_intake_preparations
                    WHERE operator_id = ?
                    """,
                    (operator_id,),
                ).fetchone()[0]
                if count >= MAX_RECORDS_PER_OPERATOR:
                    raise DormantDeliveryStoreError("quota_exceeded")
                connection.execute(
                    """
                    INSERT INTO dormant_agent_intake_preparations (
                        operator_id, delivery_preparation_id,
                        dispatch_envelope_id, idempotency_key,
                        create_fingerprint, preparation_json,
                        preparation_fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operator_id,
                        preparation.delivery_preparation_id,
                        preparation.source.dispatch_envelope_id,
                        idempotency_key,
                        create_fingerprint,
                        encoded,
                        preparation.preparation_fingerprint.value,
                    ),
                )
                connection.execute("COMMIT")
                return preparation, True
        except DormantDeliveryStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise DormantDeliveryStoreError("replay_conflict") from error
        except sqlite3.Error as error:
            raise DormantDeliveryStoreError("unavailable") from error

    def resolve_reservation(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create_fingerprint: str,
        dispatch_envelope_id: str,
    ) -> CoreAgentIntakeDeliveryPreparationV1 | None:
        """Return an exact permanent reservation before rereading dependencies."""
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM dormant_agent_intake_preparations
                    WHERE operator_id = ?
                      AND (idempotency_key = ? OR dispatch_envelope_id = ?)
                    """,
                    (operator_id, idempotency_key, dispatch_envelope_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise DormantDeliveryStoreError("unavailable") from error
        if row is None:
            return None
        if (
            row["idempotency_key"] != idempotency_key
            or row["create_fingerprint"] != create_fingerprint
            or row["dispatch_envelope_id"] != dispatch_envelope_id
        ):
            raise DormantDeliveryStoreError("replay_conflict")
        return self._decode(row)

    def get(
        self, *, operator_id: str, delivery_preparation_id: str
    ) -> CoreAgentIntakeDeliveryPreparationV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM dormant_agent_intake_preparations
                    WHERE operator_id = ? AND delivery_preparation_id = ?
                    """,
                    (operator_id, delivery_preparation_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise DormantDeliveryStoreError("unavailable") from error
        if row is None:
            raise DormantDeliveryStoreError("unavailable")
        return self._decode(row)

    @staticmethod
    def _decode(row: sqlite3.Row) -> CoreAgentIntakeDeliveryPreparationV1:
        try:
            value = CoreAgentIntakeDeliveryPreparationV1.model_validate_json(
                row["preparation_json"]
            )
            if (
                value.delivery_preparation_id != row["delivery_preparation_id"]
                or value.source.dispatch_envelope_id != row["dispatch_envelope_id"]
                or value.preparation_fingerprint.value
                != row["preparation_fingerprint"]
            ):
                raise ValueError("persisted identity mismatch")
            return value
        except Exception as error:
            raise DormantDeliveryStoreError("unavailable") from error
