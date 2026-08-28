"""Explicit, default-disabled in-process simulated handoff coordinator."""

from __future__ import annotations

from typing import Protocol

from app.installation_handoff_simulated_delivery.contract import (
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    CorrelationId,
    InstallationHandoffSimulatedDeliveryErrorV1,
    InstallationHandoffSimulatedDeliveryResultV1,
    InstallationHandoffSimulatedDeliveryV1,
    StrictContractError,
    parse_delivery_json,
)
from app.installation_handoff_simulated_delivery.store import (
    InstallationHandoffSimulatedDeliveryStore,
    SimulatedHandoffNotCurrentError,
    SimulatedHandoffStoreError,
    SimulatedHandoffUnavailableError,
)


class SimulatedHandoffAgentPort(Protocol):
    """Narrow in-process simulation port; it has no endpoint or transport."""

    def simulate(
        self,
        delivery: InstallationHandoffSimulatedDeliveryV1,
        *,
        operator_id: str,
        correlation_id: CorrelationId,
    ) -> AgentInstallationHandoffSimulatedAcknowledgementV1: ...


class InstallationHandoffSimulatedDeliveryService:
    """Reserve an inert attempt, invoke an injected simulator, preserve evidence."""

    def __init__(
        self,
        *,
        store: InstallationHandoffSimulatedDeliveryStore,
        agent_port: SimulatedHandoffAgentPort,
        enabled: bool = False,
    ) -> None:
        self._store = store
        self._agent_port = agent_port
        self._enabled = enabled is True

    @staticmethod
    def _error(
        code: str,
        correlation_id: CorrelationId,
        delivery: InstallationHandoffSimulatedDeliveryV1 | None = None,
    ) -> InstallationHandoffSimulatedDeliveryResultV1:
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
        safe_code = code if code in allowed else "unavailable"
        return InstallationHandoffSimulatedDeliveryResultV1(
            disposition="unavailable" if safe_code == "unavailable" else "rejected",
            record=None,
            acknowledgement=None,
            error=InstallationHandoffSimulatedDeliveryErrorV1(
                error_code=safe_code,  # type: ignore[arg-type]
                correlation_id=correlation_id,
                simulated_delivery_id=(
                    delivery.simulated_delivery_id if delivery is not None else None
                ),
                simulation_request_id=(
                    delivery.simulation_request_id if delivery is not None else None
                ),
                dispatch_envelope_id=(
                    delivery.envelope.dispatch_envelope_id
                    if delivery is not None
                    else None
                ),
            ),
        )

    def simulate(
        self,
        payload: bytes | str | InstallationHandoffSimulatedDeliveryV1,
        *,
        operator_id: str,
        idempotency_key: str,
        correlation_id: CorrelationId,
    ) -> InstallationHandoffSimulatedDeliveryResultV1:
        if not self._enabled:
            return self._error("unavailable", correlation_id)
        delivery: InstallationHandoffSimulatedDeliveryV1 | None = None
        try:
            delivery = (
                payload
                if isinstance(payload, InstallationHandoffSimulatedDeliveryV1)
                else parse_delivery_json(payload)
            )
            record, created = self._store.reserve_attempt(
                operator_id=operator_id,
                idempotency_key=idempotency_key,
                delivery=delivery,
            )
            acknowledgement = self._store.get_acknowledgement(
                operator_id=operator_id,
                simulated_delivery_id=delivery.simulated_delivery_id,
            )
            if acknowledgement is not None:
                return InstallationHandoffSimulatedDeliveryResultV1(
                    disposition="exact_replay",
                    record=record,
                    acknowledgement=acknowledgement,
                    error=None,
                )
            if not created and self._store.lifecycle(
                operator_id=operator_id,
                simulated_delivery_id=delivery.simulated_delivery_id,
            ) == "expired_unacknowledged":
                raise SimulatedHandoffNotCurrentError()
            returned = self._agent_port.simulate(
                delivery,
                operator_id=operator_id,
                correlation_id=correlation_id,
            )
            acknowledgement = getattr(returned, "acknowledgement", returned)
            if not isinstance(
                acknowledgement, AgentInstallationHandoffSimulatedAcknowledgementV1
            ):
                raise SimulatedHandoffUnavailableError()
            acknowledgement, acknowledgement_created = (
                self._store.preserve_acknowledgement(
                    operator_id=operator_id,
                    delivery=delivery,
                    acknowledgement=acknowledgement,
                )
            )
            return InstallationHandoffSimulatedDeliveryResultV1(
                disposition=(
                    "simulated" if created and acknowledgement_created else "exact_replay"
                ),
                record=record,
                acknowledgement=acknowledgement,
                error=None,
            )
        except SimulatedHandoffStoreError as error:
            return self._error(error.code, correlation_id, delivery)
        except (StrictContractError, TypeError, ValueError):
            return self._error("malformed", correlation_id, delivery)
        except Exception:  # noqa: BLE001 - injected failures are always closed/redacted
            return self._error("unavailable", correlation_id, delivery)

    deliver = simulate

    def get_attempt(self, *, operator_id: str, simulated_delivery_id: str):
        return self._store.get_attempt(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )

    def get_acknowledgement(self, *, operator_id: str, simulated_delivery_id: str):
        return self._store.get_acknowledgement(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )

    def lifecycle(self, *, operator_id: str, simulated_delivery_id: str) -> str:
        return self._store.lifecycle(
            operator_id=operator_id, simulated_delivery_id=simulated_delivery_id
        )
