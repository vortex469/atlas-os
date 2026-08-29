"""Explicit, default-disabled v0.32 evidence-admission service."""

from __future__ import annotations

from typing import Protocol

from pydantic import TypeAdapter

from .contract import (
    AgentLiveIntakeAuthenticationContextV1,
    AgentLiveIntakeEnvelopeV1,
    AgentLiveIntakeLinkageV1,
    AgentLiveIntakeRedactedErrorV1,
    AgentLiveIntakeResultV1,
    AgentLiveIntakeSourceV1,
    CorrelationId,
    FingerprintV1,
    StrictContractError,
    parse_envelope_json,
    validate_admission_input,
)
from .store import AgentLiveIntakeAdmissionStore, AgentLiveIntakeStoreError


class AgentLiveIntakeEvidenceReader(Protocol):
    """Injected owner-scoped projection of the expected v0.20-v0.31 linkage."""

    def resolve(
        self, *, operator_id: str, linkage: AgentLiveIntakeLinkageV1
    ) -> AgentLiveIntakeLinkageV1: ...


class AgentLiveIntakeAdmissionService:
    """Validate and durably admit evidence only; never receive network I/O."""

    def __init__(
        self,
        *,
        store: AgentLiveIntakeAdmissionStore,
        evidence_reader: AgentLiveIntakeEvidenceReader,
        expected_source: AgentLiveIntakeSourceV1,
        endpoint_fingerprint: FingerprintV1,
        enabled: bool = False,
    ) -> None:
        self._store = store
        self._evidence_reader = evidence_reader
        self._expected_source = AgentLiveIntakeSourceV1.model_validate(
            expected_source.model_dump(mode="python")
        )
        self._endpoint_fingerprint = FingerprintV1.model_validate(
            endpoint_fingerprint.model_dump(mode="python")
        )
        self._enabled = enabled is True

    @staticmethod
    def _rejected(
        code: str,
        *,
        envelope: AgentLiveIntakeEnvelopeV1 | None = None,
    ) -> AgentLiveIntakeResultV1:
        allowed = {
            "unauthenticated",
            "unauthorized",
            "malformed",
            "not_current",
            "ownership_mismatch",
            "request_mismatch",
            "attempt_mismatch",
            "linkage_mismatch",
            "fingerprint_mismatch",
            "replay_conflict",
            "quota_exceeded",
            "unavailable",
        }
        safe = code if code in allowed else "unavailable"
        disclose = safe not in {"unauthenticated", "unauthorized"}
        return AgentLiveIntakeResultV1(
            send_attempt_id=(
                envelope.send_attempt.send_attempt_id
                if disclose and envelope is not None
                else None
            ),
            intake_request_id=(
                envelope.intake_request.intake_request_id
                if disclose and envelope is not None
                else None
            ),
            outcome="rejected",
            admission=None,
            acknowledgement=None,
            reason_code=safe,  # type: ignore[arg-type]
        )

    def admit(
        self,
        payload: bytes | str | AgentLiveIntakeEnvelopeV1,
        *,
        authentication: AgentLiveIntakeAuthenticationContextV1,
        idempotency_key: str,
        correlation_id: CorrelationId,
    ) -> AgentLiveIntakeResultV1:
        if not self._enabled:
            return self._rejected("unavailable")
        try:
            TypeAdapter(CorrelationId).validate_python(correlation_id, strict=True)
        except (TypeError, ValueError):
            return self._rejected("malformed")

        envelope: AgentLiveIntakeEnvelopeV1 | None = None
        try:
            auth = AgentLiveIntakeAuthenticationContextV1.model_validate(
                authentication.model_dump(mode="python")
            )
            if auth.source != self._expected_source:
                return self._rejected("unauthenticated")
        except (AttributeError, TypeError, ValueError):
            return self._rejected("unauthenticated")

        try:
            envelope = (
                payload
                if isinstance(payload, AgentLiveIntakeEnvelopeV1)
                else parse_envelope_json(payload)
            )
            operator_id = envelope.send_attempt.operator_id
            prior = self._store.replay(
                operator_id=operator_id,
                idempotency_key=idempotency_key,
                envelope=envelope,
            )
            if prior is not None:
                return prior[4]
            expected = self._evidence_reader.resolve(
                operator_id=operator_id,
                linkage=envelope.send_attempt.linkage,
            )
            exact_expected = AgentLiveIntakeLinkageV1.model_validate(
                expected.model_dump(mode="python")
            )
            if exact_expected != envelope.send_attempt.linkage:
                return self._rejected("linkage_mismatch", envelope=envelope)
            validate_admission_input(
                envelope,
                operator_id=operator_id,
                received_at=self._store.received_at(),
                endpoint_fingerprint_value=self._endpoint_fingerprint,
            )
            result, _created = self._store.preserve(
                operator_id=operator_id,
                idempotency_key=idempotency_key,
                envelope=envelope,
                authentication=auth,
                correlation_id=correlation_id,
            )
            return result
        except AgentLiveIntakeStoreError as error:
            return self._rejected(error.code, envelope=envelope)
        except StrictContractError:
            return self._rejected("malformed", envelope=envelope)
        except (TypeError, ValueError, AttributeError) as error:
            detail = str(error)
            if "stale" in detail or "expired" in detail or "freshness" in detail:
                return self._rejected("not_current", envelope=envelope)
            if "ownership" in detail:
                return self._rejected("ownership_mismatch", envelope=envelope)
            if "linkage" in detail:
                return self._rejected("linkage_mismatch", envelope=envelope)
            if "fingerprint" in detail or "endpoint" in detail:
                return self._rejected("fingerprint_mismatch", envelope=envelope)
            return self._rejected("malformed", envelope=envelope)
        except Exception:  # noqa: BLE001 - injected failures remain closed/redacted
            return self._rejected("unavailable", envelope=envelope)

    preserve = admit

    def get(self, *, operator_id: str, admission_id: str):
        return self._store.get(operator_id=operator_id, admission_id=admission_id)

    def get_audit(self, *, operator_id: str, admission_id: str):
        return self._store.get_audit(operator_id=operator_id, admission_id=admission_id)

    def status(self, *, operator_id: str, admission_id: str):
        return self._store.status(operator_id=operator_id, admission_id=admission_id)

    @staticmethod
    def redacted_error(
        *, code: str, correlation_id: str
    ) -> AgentLiveIntakeRedactedErrorV1:
        allowed = {
            "unauthenticated",
            "unauthorized",
            "malformed",
            "not_current",
            "ownership_mismatch",
            "request_mismatch",
            "attempt_mismatch",
            "linkage_mismatch",
            "fingerprint_mismatch",
            "replay_conflict",
            "quota_exceeded",
            "unavailable",
        }
        return AgentLiveIntakeRedactedErrorV1(
            error_code=code if code in allowed else "unavailable",  # type: ignore[arg-type]
            correlation_id=correlation_id,
        )
