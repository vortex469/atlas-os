from collections import deque
from threading import Lock

from app.actions.models import ProviderActionAuditEntry


class ProviderActionHistory:
    """Bounded, process-local history of provider action executions."""

    def __init__(self, max_entries: int = 500) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1.")

        self._entries: deque[ProviderActionAuditEntry] = deque(
            maxlen=max_entries,
        )
        self._lock = Lock()

    def append(self, entry: ProviderActionAuditEntry) -> None:
        with self._lock:
            self._entries.appendleft(entry)

    def list(
        self,
        *,
        limit: int = 50,
        provider_id: str | None = None,
        status: str | None = None,
    ) -> list[ProviderActionAuditEntry]:
        with self._lock:
            entries = tuple(self._entries)

        filtered = (
            entry
            for entry in entries
            if (
                provider_id is None
                or entry.provider_id == provider_id
            )
            and (
                status is None
                or entry.status == status
            )
        )

        return list(filtered)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


provider_action_history = ProviderActionHistory()
