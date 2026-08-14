from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from threading import Lock


class OperatorRateLimiter:
    """Bounded per-process defense-in-depth limiter; never an authorization control."""

    def __init__(self, limit: int, window_seconds: int, max_keys: int = 2048) -> None:
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self.max_keys = max_keys
        self._events: dict[str, deque[datetime]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        cutoff = current - self.window
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            if len(self._events) > self.max_keys:
                empty_or_old = [
                    item_key for item_key, values in self._events.items()
                    if not values or values[-1] <= cutoff
                ]
                for item_key in empty_or_old[: len(self._events) - self.max_keys]:
                    self._events.pop(item_key, None)
                overflow = len(self._events) - self.max_keys
                if overflow > 0:
                    oldest = sorted(
                        (item_key for item_key in self._events if item_key != key),
                        key=lambda item_key: self._events[item_key][-1],
                    )
                    for item_key in oldest[:overflow]:
                        self._events.pop(item_key, None)
            return True
