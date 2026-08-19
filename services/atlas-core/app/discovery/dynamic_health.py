"""Process-local observations for bounded dynamic Discovery sources."""

from __future__ import annotations

from threading import Lock

from app.discovery.dynamic_sources import DynamicSourceHealth


class DynamicSourceHealthRegistry:
    """Thread-safe last-observation registry with a pure read interface."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._observations: dict[str, DynamicSourceHealth] = {}

    def record(self, source_id: str, health: DynamicSourceHealth) -> None:
        if not isinstance(health, DynamicSourceHealth):
            raise TypeError("health must be a DynamicSourceHealth")
        with self._lock:
            self._observations[source_id] = health

    def read_health(self, source_id: str) -> DynamicSourceHealth | None:
        with self._lock:
            return self._observations.get(source_id)


dynamic_source_health_registry = DynamicSourceHealthRegistry()
