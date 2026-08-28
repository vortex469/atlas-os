"""Closed Agent acknowledgement adapter for simulated handoff delivery."""

from .models import *
from .service import (
    AgentSimulatedAcknowledgementService as AgentSimulatedAcknowledgementService,
)
from .store import (  # noqa: F401
    MAX_RETAINED_RECORDS_PER_OPERATOR,
    AgentSimulatedAcknowledgementStore,
    SimulatedAcknowledgementDeliveryMismatchError,
    SimulatedAcknowledgementIntakeMismatchError,
    SimulatedAcknowledgementMalformedError,
    SimulatedAcknowledgementNotCurrentError,
    SimulatedAcknowledgementOwnershipError,
    SimulatedAcknowledgementQuotaError,
    SimulatedAcknowledgementReplayConflictError,
    SimulatedAcknowledgementStoreError,
    SimulatedAcknowledgementUnavailableError,
)
