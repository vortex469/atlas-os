"""Explicit, default-disabled in-process real-intake evidence service."""

from __future__ import annotations

from typing import Protocol

from pydantic import TypeAdapter

from .models import (
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeEvidenceContextV1,
    AgentInstallationIntakePriorEvidenceV1,
    AgentInstallationIntakeRequestV1,
    AgentInstallationIntakeResultV1,
    CorrelationId,
    StrictContractError,
    parse_intake_request_json,
)
from .store import AgentRealIntakeEvidenceStore, RealIntakeStoreError


class RealIntakeEvidenceReader(Protocol):
    """Injected, operator-scoped reader for exact local prior evidence."""

    def resolve(
        self,
        *,
        operator_id: str,
        prior_evidence: AgentInstallationIntakePriorEvidenceV1,
    ) -> AgentInstallationIntakeEvidenceContextV1: ...


class AgentRealIntakeEvidenceService:
    """Validate and preserve evidence only; never receive production transport."""

    def __init__(
        self,
        *,
        store: AgentRealIntakeEvidenceStore,
        evidence_reader: RealIntakeEvidenceReader,
        enabled: bool = False,
    ) -> None:
        self._store = store
        self._evidence_reader = evidence_reader
        self._enabled = enabled is True

    @staticmethod
    def _result(
        *,
        code: str | None,
        request: AgentInstallationIntakeRequestV1 | None = None,
        admission=None,
    ) -> AgentInstallationIntakeResultV1:
        if admission is not None:
            return AgentInstallationIntakeResultV1(
                intake_request_id=admission.intake_request_id,
                outcome="admitted_for_evidence_only",
                admission=admission,
                reason_code=None,
            )
        allowed = {
            "unauthenticated",
            "unauthorized",
            "malformed",
            "not_current",
            "ownership_mismatch",
            "request_mismatch",
            "envelope_mismatch",
            "linkage_mismatch",
            "simulation_evidence_mismatch",
            "delivery_evidence_mismatch",
            "recipient_mismatch",
            "replay_conflict",
            "quota_exceeded",
            "unavailable",
        }
        safe = code if code in allowed else "unavailable"
        disclose_id = safe not in ("unauthenticated", "unauthorized")
        return AgentInstallationIntakeResultV1(
            intake_request_id=(
                request.intake_request_id if disclose_id and request is not None else None
            ),
            outcome="rejected",
            admission=None,
            reason_code=safe,  # type: ignore[arg-type]
        )

    def preserve(
        self,
        payload: bytes | str | AgentInstallationIntakeRequestV1,
        *,
        authentication: AgentInstallationIntakeAuthenticationContextV1,
        idempotency_key: str,
        correlation_id: CorrelationId,
    ) -> AgentInstallationIntakeResultV1:
        """Preserve one admission using only injected, already-authenticated inputs."""
        if not self._enabled:
            return self._result(code="unavailable")
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
        except (TypeError, ValueError):
            return self._result(code="malformed")
        request: AgentInstallationIntakeRequestV1 | None = None
        try:
            auth = AgentInstallationIntakeAuthenticationContextV1.model_validate(
                authentication.model_dump(mode="python")
            )
        except (AttributeError, TypeError, ValueError):
            return self._result(code="unauthenticated")
        try:
            request = (
                payload
                if isinstance(payload, AgentInstallationIntakeRequestV1)
                else parse_intake_request_json(payload)
            )
            operator_id = request.operator_assertion.operator_id
            prior = self._store.replay(
                operator_id=operator_id,
                idempotency_key=idempotency_key,
                request=request,
            )
            if prior is not None:
                return self._result(code=None, admission=prior)
            evidence = self._evidence_reader.resolve(
                operator_id=operator_id,
                prior_evidence=request.prior_evidence,
            )
            exact_evidence = AgentInstallationIntakeEvidenceContextV1.model_validate(
                evidence.model_dump(mode="python")
            )
            admission, _created = self._store.preserve(
                operator_id=operator_id,
                idempotency_key=idempotency_key,
                request=request,
                authentication=auth,
                evidence=exact_evidence,
            )
            return self._result(code=None, admission=admission)
        except RealIntakeStoreError as error:
            return self._result(code=error.code, request=request)
        except (StrictContractError, TypeError, ValueError, AttributeError):
            return self._result(code="malformed", request=request)
        except Exception:  # noqa: BLE001 - dependency failures remain redacted
            return self._result(code="unavailable", request=request)

    admit = preserve

    def get(self, *, operator_id: str, admission_id: str):
        return self._store.get(operator_id=operator_id, admission_id=admission_id)

    def get_acknowledgement(self, *, operator_id: str, admission_id: str):
        return self._store.get_acknowledgement(
            operator_id=operator_id, admission_id=admission_id
        )

    def lifecycle(self, *, operator_id: str, admission_id: str) -> str:
        return self._store.lifecycle(
            operator_id=operator_id, admission_id=admission_id
        )
