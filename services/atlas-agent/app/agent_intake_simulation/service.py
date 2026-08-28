"""Explicit, default-disabled in-process Agent intake simulation service."""

from __future__ import annotations

from .models import (
    AgentInstallationIntakeSimulationCreateV1,
    AgentInstallationIntakeSimulationErrorV1,
    AgentInstallationIntakeSimulationResultV1,
    CorrelationId,
    StrictContractError,
    parse_simulation_create_json,
)
from .store import (
    AgentIntakeSimulationStore,
    IntakeSimulationStoreError,
)


class AgentIntakeSimulationService:
    """Preserve injected evidence only; never receive, admit, or execute it."""

    def __init__(self, *, store: AgentIntakeSimulationStore, enabled: bool = False) -> None:
        self._store = store
        self._enabled = enabled is True

    @staticmethod
    def _error(
        code: str, correlation_id: CorrelationId
    ) -> AgentInstallationIntakeSimulationResultV1:
        safe_code = code if code in {
            "malformed", "not_current", "ownership_mismatch", "envelope_mismatch",
            "linkage_mismatch", "recipient_mismatch", "replay_conflict",
            "quota_exceeded", "unavailable",
        } else "unavailable"
        return AgentInstallationIntakeSimulationResultV1(
            disposition="unavailable" if safe_code == "unavailable" else "rejected",
            validation=None,
            error=AgentInstallationIntakeSimulationErrorV1(
                error_code=safe_code,  # type: ignore[arg-type]
                correlation_id=correlation_id,
            ),
        )

    def simulate(
        self,
        payload: bytes | str | AgentInstallationIntakeSimulationCreateV1,
        *,
        operator_id: str,
        idempotency_key: str,
        correlation_id: CorrelationId,
    ) -> AgentInstallationIntakeSimulationResultV1:
        if not self._enabled:
            return self._error("unavailable", correlation_id)
        try:
            create = (
                payload
                if isinstance(payload, AgentInstallationIntakeSimulationCreateV1)
                else parse_simulation_create_json(payload)
            )
            validation, created = self._store.create(
                operator_id=operator_id,
                idempotency_key=idempotency_key,
                create=create,
            )
            return AgentInstallationIntakeSimulationResultV1(
                disposition="simulated" if created else "exact_replay",
                validation=validation,
                error=None,
            )
        except IntakeSimulationStoreError as error:
            return self._error(error.code, correlation_id)
        except (StrictContractError, TypeError, ValueError):
            return self._error("malformed", correlation_id)

    def get(self, *, operator_id: str, intake_record_id: str):
        """Return an immutable owned record; absence and corruption stay closed."""
        return self._store.get(operator_id=operator_id, intake_record_id=intake_record_id)

    def lifecycle(self, *, operator_id: str, intake_record_id: str) -> str:
        return self._store.lifecycle(
            operator_id=operator_id, intake_record_id=intake_record_id
        )
