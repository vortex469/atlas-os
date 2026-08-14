"""Static operational handler registry with an empty production instance."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.operational_dispatch.models import (
    OperationalDispatchRequest,
    OperationalDispatchResult,
)
from app.services.provider_resources import ResolvedOperationalTarget

OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})

OperationalHandler = Callable[
    [OperationalDispatchRequest, ResolvedOperationalTarget],
    Awaitable[OperationalDispatchResult],
]


@dataclass(frozen=True, slots=True)
class OperationalHandlerRegistration:
    operation_intent: str
    provider_id: str
    resource_type: str
    handler: OperationalHandler


class OperationalHandlerRegistry:
    """Exact-key registry; registration never grants semantic authorization."""

    def __init__(
        self, registrations: tuple[OperationalHandlerRegistration, ...] = ()
    ) -> None:
        self._handlers: dict[tuple[str, str, str], OperationalHandler] = {}
        for registration in registrations:
            key = (
                registration.operation_intent,
                registration.provider_id,
                registration.resource_type,
            )
            if key in self._handlers:
                raise ValueError("duplicate operational handler registration")
            self._handlers[key] = registration.handler

    def resolve(
        self, operation_intent: str, provider_id: str, resource_type: str
    ) -> OperationalHandler | None:
        return self._handlers.get((operation_intent, provider_id, resource_type))

    def __len__(self) -> int:
        return len(self._handlers)


production_operational_handler_registry = OperationalHandlerRegistry()
