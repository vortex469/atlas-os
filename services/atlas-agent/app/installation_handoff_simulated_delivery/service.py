"""Explicit default-disabled in-process Agent simulated acknowledgement adapter."""

from __future__ import annotations

from app.agent_intake_simulation import (
    AgentInstallationIntakeSimulationCreateV1,
    AgentIntakeSimulationService,
)

from .models import (
    AgentInstallationHandoffSimulatedAcknowledgementErrorV1,
    AgentInstallationHandoffSimulatedAcknowledgementResultV1,
    CorrelationId,
    InstallationHandoffSimulatedDeliveryV1,
    derived_intake_idempotency_key,
)
from .store import (
    AgentSimulatedAcknowledgementStore,
    SimulatedAcknowledgementStoreError,
)


class AgentSimulatedAcknowledgementService:
    """Reuse v0.25 simulation and preserve inert acknowledgement evidence only."""

    def __init__(
        self,
        *,
        store: AgentSimulatedAcknowledgementStore,
        intake_service: AgentIntakeSimulationService,
        enabled: bool = False,
    ) -> None:
        self._store = store
        self._intake_service = intake_service
        self._enabled = enabled is True

    @staticmethod
    def _error(
        code: str,
        correlation_id: CorrelationId,
        delivery: InstallationHandoffSimulatedDeliveryV1 | None = None,
    ) -> AgentInstallationHandoffSimulatedAcknowledgementResultV1:
        allowed = {
            "malformed",
            "not_current",
            "ownership_mismatch",
            "delivery_mismatch",
            "envelope_mismatch",
            "linkage_mismatch",
            "recipient_mismatch",
            "intake_mismatch",
            "replay_conflict",
            "quota_exceeded",
            "unavailable",
        }
        safe = code if code in allowed else "unavailable"
        return AgentInstallationHandoffSimulatedAcknowledgementResultV1(
            disposition="unavailable" if safe == "unavailable" else "rejected",
            acknowledgement=None,
            error=AgentInstallationHandoffSimulatedAcknowledgementErrorV1(
                error_code=safe,  # type: ignore[arg-type]
                correlation_id=correlation_id,
                simulated_delivery_id=(
                    delivery.simulated_delivery_id if delivery is not None else None
                ),
            ),
        )

    def simulate(
        self,
        delivery: InstallationHandoffSimulatedDeliveryV1,
        *,
        operator_id: str,
        correlation_id: CorrelationId,
    ) -> AgentInstallationHandoffSimulatedAcknowledgementResultV1:
        if not self._enabled:
            return self._error("unavailable", correlation_id)
        exact: InstallationHandoffSimulatedDeliveryV1 | None = None
        try:
            exact = InstallationHandoffSimulatedDeliveryV1.model_validate(
                delivery.model_dump(mode="python")
            )
            prior = self._store.find_for_delivery(
                operator_id=operator_id, delivery=exact
            )
            if prior is not None:
                return AgentInstallationHandoffSimulatedAcknowledgementResultV1(
                    disposition="exact_replay", acknowledgement=prior, error=None
                )
            create = AgentInstallationIntakeSimulationCreateV1(
                simulation_request_id=exact.simulation_request_id,
                envelope=exact.envelope,
            )
            result = self._intake_service.simulate(
                create,
                operator_id=operator_id,
                idempotency_key=derived_intake_idempotency_key(exact),
                correlation_id=correlation_id,
            )
            if result.validation is None:
                return self._error(
                    result.error.error_code
                    if result.error is not None
                    else "unavailable",
                    correlation_id,
                    exact,
                )
            durable = self._intake_service.get(
                operator_id=operator_id,
                intake_record_id=result.validation.record.intake_record_id,
            )
            if durable != result.validation.record:
                return self._error("unavailable", correlation_id, exact)
            acknowledgement, created = self._store.preserve(
                operator_id=operator_id, delivery=exact, intake_record=durable
            )
            return AgentInstallationHandoffSimulatedAcknowledgementResultV1(
                disposition="simulated" if created else "exact_replay",
                acknowledgement=acknowledgement,
                error=None,
            )
        except SimulatedAcknowledgementStoreError as error:
            return self._error(error.code, correlation_id, exact)
        except (TypeError, ValueError, AttributeError):
            return self._error("malformed", correlation_id, exact)
        except Exception:  # noqa: BLE001 - all dependency failures are closed/redacted
            return self._error("unavailable", correlation_id, exact)

    acknowledge = simulate

    def get(self, *, operator_id: str, simulated_delivery_id: str):
        return self._store.get(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )

    def lifecycle(self, *, operator_id: str, simulated_delivery_id: str) -> str:
        return self._store.lifecycle(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )
