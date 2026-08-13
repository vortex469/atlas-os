"""Thread-safe, non-durable request ledger for the S2 worker skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Literal

from app.execution.worker_contracts import WorkerExecutionRequest, WorkerExecutionResult

LedgerState = Literal["claimed", "completed"]


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One request identity and its current terminal evidence."""

    request_digest: str
    state: LedgerState
    result: WorkerExecutionResult | None = None


class RequestConflictError(ValueError):
    """The request ID was already used with different immutable evidence."""


class RequestLedger:
    """Small in-memory ledger with atomic ID claim and deterministic lookup."""

    def __init__(self) -> None:
        self._entries: dict[str, LedgerEntry] = {}
        self._lock = Lock()

    def claim(self, request: WorkerExecutionRequest) -> LedgerEntry:
        """Claim once, returning the existing entry for an identical request."""

        with self._lock:
            current = self._entries.get(request.execution_request_id)
            if current is not None:
                if current.request_digest != request.request_digest:
                    raise RequestConflictError("execution request ID has conflicting digest")
                return current
            entry = LedgerEntry(request_digest=request.request_digest, state="claimed")
            self._entries[request.execution_request_id] = entry
            return entry

    def complete(
        self,
        request: WorkerExecutionRequest,
        result: WorkerExecutionResult,
    ) -> LedgerEntry:
        """Store one terminal result without replacing another request."""

        result.validate(request)
        with self._lock:
            current = self._entries.get(request.execution_request_id)
            if current is None:
                raise KeyError(request.execution_request_id)
            if current.request_digest != request.request_digest:
                raise RequestConflictError("execution request ID has conflicting digest")
            if current.state == "completed":
                return current
            entry = LedgerEntry(
                request_digest=current.request_digest,
                state="completed",
                result=result,
            )
            self._entries[request.execution_request_id] = entry
            return entry

    def get(self, request_id: str) -> LedgerEntry | None:
        """Return a stable snapshot of one entry, without exposing the map."""

        with self._lock:
            return self._entries.get(request_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
