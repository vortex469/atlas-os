"""Explicit no-network verifier for v0.33 inert delivery receipt evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.live_delivery_send_boundary.contract import LiveDeliverySendReceiptV1
from app.live_delivery_send_boundary.contract import (
    receipt_fingerprint as prior_receipt_fingerprint,
)

from .contract import (
    AgentAdmissionReceiptCopyV1,
    EndToEndInertDeliveryAuditEvidenceV1,
    EndToEndInertDeliveryLinkageV1,
    EndToEndInertDeliveryReceiptV1,
    EndToEndInertDeliveryRedactedErrorV1,
    EndToEndInertDeliveryRequestV1,
    EndToEndInertDeliveryResultV1,
    EndToEndInertDeliveryStatusV1,
    EndToEndInertDeliveryVerificationV1,
    agent_result_fingerprint,
    audit_evidence_fingerprint,
    idempotency_key_fingerprint,
    linkage_fingerprint,
    operator_fingerprint,
    receipt_fingerprint,
    response_body_fingerprint,
    verification_fingerprint,
)
from .store import (
    InertDeliveryReceiptConflictError,
    InertDeliveryReceiptQuotaError,
    InertDeliveryReceiptStore,
    StoredInertDeliveryReceipt,
    canonical_json,
)


@dataclass(frozen=True)
class InertDeliveryReceiptEvidence:
    prior_send_receipt: LiveDeliverySendReceiptV1
    agent_receipt_copy: AgentAdmissionReceiptCopyV1


class InertDeliveryReceiptEvidenceReader(Protocol):
    def resolve(
        self, *, operator_id: str, request: EndToEndInertDeliveryRequestV1
    ) -> InertDeliveryReceiptEvidence: ...


class InertDeliveryReceiptService:
    """Verify already-produced evidence; never transport or invoke Agent."""

    def __init__(
        self,
        *,
        evidence_reader: InertDeliveryReceiptEvidenceReader,
        store: InertDeliveryReceiptStore,
        clock: Callable[[], datetime],
        receipt_id_factory: Callable[[], str],
    ) -> None:
        self._reader = evidence_reader
        self._store = store
        self._clock = clock
        self._receipt_id_factory = receipt_id_factory

    def verify(
        self,
        request: EndToEndInertDeliveryRequestV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> EndToEndInertDeliveryResultV1:
        try:
            exact_request = EndToEndInertDeliveryRequestV1.model_validate(request)
            if exact_request.envelope.send_attempt.operator_id != authenticated_operator_id:
                raise ValueError("ownership mismatch")
            key_fingerprint = idempotency_key_fingerprint(
                authenticated_operator_id, idempotency_key
            )
            if exact_request.idempotency_key_fingerprint != key_fingerprint:
                raise ValueError("idempotency fingerprint mismatch")
            receipt_id = self._receipt_id_factory()
            reserved = self._store.reserve(
                operator_id=authenticated_operator_id,
                send_attempt_id=exact_request.send_attempt_id,
                request_fingerprint=exact_request.request_fingerprint.value,
                idempotency_key_fingerprint=key_fingerprint.value,
                receipt_id=receipt_id,
            )
            if reserved.stored is not None:
                return self._success(reserved.stored, disposition="exact_duplicate")
            evidence = self._reader.resolve(
                operator_id=authenticated_operator_id, request=exact_request
            )
            stored = self._verify_and_build(
                request=exact_request,
                evidence=evidence,
                operator_id=authenticated_operator_id,
                receipt_id=receipt_id,
                key_fingerprint=key_fingerprint,
                correlation_id=correlation_id,
            )
            return self._success(
                self._store.append(operator_id=authenticated_operator_id, stored=stored),
                disposition="verified_inert_receipt",
            )
        except InertDeliveryReceiptConflictError:
            return self._failure("already_reserved", correlation_id)
        except InertDeliveryReceiptQuotaError:
            return self._failure("quota_exceeded", correlation_id)
        except ValueError as error:
            return self._failure(_validation_code(error), correlation_id)
        except Exception:  # noqa: BLE001 - dependency failures are always redacted
            return self._failure("unavailable", correlation_id)

    def get(
        self, *, authenticated_operator_id: str, receipt_id: str, correlation_id: str
    ) -> EndToEndInertDeliveryResultV1:
        try:
            stored = self._store.get_owned(
                operator_id=authenticated_operator_id, receipt_id=receipt_id
            )
            if stored is None:
                return self._failure("not_found", correlation_id)
            return self._success(stored, disposition="exact_duplicate")
        except Exception:  # noqa: BLE001 - corrupt storage must fail closed
            return self._failure("unavailable", correlation_id)

    def list(
        self, *, authenticated_operator_id: str, correlation_id: str
    ) -> tuple[EndToEndInertDeliveryResultV1, ...] | EndToEndInertDeliveryResultV1:
        try:
            return tuple(
                self._success(value, disposition="exact_duplicate")
                for value in self._store.list_owned(operator_id=authenticated_operator_id)
            )
        except Exception:  # noqa: BLE001 - corrupt storage must fail closed
            return self._failure("unavailable", correlation_id)

    def _verify_and_build(
        self,
        *,
        request: EndToEndInertDeliveryRequestV1,
        evidence: InertDeliveryReceiptEvidence,
        operator_id: str,
        receipt_id: str,
        key_fingerprint,
        correlation_id: str,
    ) -> StoredInertDeliveryReceipt:
        prior = LiveDeliverySendReceiptV1.model_validate(evidence.prior_send_receipt)
        copy = AgentAdmissionReceiptCopyV1.model_validate(evidence.agent_receipt_copy)
        result = copy.result
        admission, acknowledgement = result.admission, result.acknowledgement
        if admission is None or acknowledgement is None:
            raise ValueError("Agent admission receipt is incomplete")
        attempt = request.envelope.send_attempt
        if operator_id != attempt.operator_id or operator_id != admission.operator_id:
            raise ValueError("ownership mismatch")
        if not (
            prior.send_attempt_id == request.send_attempt_id
            and _same_value(prior.attempt_fingerprint, request.attempt_fingerprint)
            and prior.lifecycle == "admitted_evidence_only"
            and prior.evidence_admitted
            and prior.receipt_fingerprint == prior_receipt_fingerprint(prior)
        ):
            raise ValueError("v0.31 send receipt mismatch")
        if not (
            copy.authenticity.endpoint_fingerprint == request.endpoint_fingerprint
            and result.send_attempt_id == request.send_attempt_id
            and admission.attempt_fingerprint == request.attempt_fingerprint
            and admission.envelope_fingerprint == request.envelope.envelope_fingerprint
            and admission.request_fingerprint == request.envelope.request_fingerprint
            and admission.linkage == attempt.linkage
        ):
            raise ValueError("Agent receipt authenticity or admission mismatch")
        now = self._now()
        if not (
            request.requested_at <= admission.received_at <= now < request.expires_at
            and request.expires_at
            == admission.valid_until
            == acknowledgement.valid_until
        ):
            raise ValueError("evidence is stale or expired")
        result_fingerprint = agent_result_fingerprint(result)
        linkage = EndToEndInertDeliveryLinkageV1(
            **attempt.linkage.model_dump(mode="python"),
            send_attempt_id=attempt.send_attempt_id,
            attempt_fingerprint=attempt.attempt_fingerprint,
            v031_send_receipt_fingerprint=prior.receipt_fingerprint,
            v032_envelope_fingerprint=request.envelope.envelope_fingerprint,
            v032_agent_result_fingerprint=result_fingerprint,
            v032_admission_id=admission.admission_id,
            v032_admission_fingerprint=admission.admission_fingerprint,
            v032_acknowledgement_id=acknowledgement.acknowledgement_id,
            v032_acknowledgement_fingerprint=(
                acknowledgement.acknowledgement_fingerprint
            ),
        )
        verification_raw = {
            "send_attempt_id": attempt.send_attempt_id,
            "attempt_fingerprint": attempt.attempt_fingerprint,
            "envelope_fingerprint": request.envelope.envelope_fingerprint,
            "request_fingerprint": request.request_fingerprint,
            "response_body_fingerprint": response_body_fingerprint(
                canonical_json(result)
            ),
            "agent_result_fingerprint": result_fingerprint,
            "admission_id": admission.admission_id,
            "admission_fingerprint": admission.admission_fingerprint,
            "acknowledgement_id": acknowledgement.acknowledgement_id,
            "acknowledgement_fingerprint": acknowledgement.acknowledgement_fingerprint,
            "intake_request_id": admission.intake_request_id,
            "operator_id": operator_id,
            "linkage_fingerprint": linkage_fingerprint(linkage),
            "verified_at": now,
            "valid_until": request.expires_at,
        }
        verification_seed = EndToEndInertDeliveryVerificationV1.model_construct(
            **verification_raw, verification_fingerprint=attempt.attempt_fingerprint
        )
        verification = EndToEndInertDeliveryVerificationV1.model_validate(
            verification_seed.model_copy(
                update={
                    "verification_fingerprint": verification_fingerprint(
                        verification_seed
                    )
                }
            )
        )
        receipt_seed = EndToEndInertDeliveryReceiptV1.model_construct(
            receipt_id=receipt_id,
            operator_id=operator_id,
            send_attempt_id=attempt.send_attempt_id,
            attempt_fingerprint=attempt.attempt_fingerprint,
            prior_send_receipt_fingerprint=prior.receipt_fingerprint,
            envelope_fingerprint=request.envelope.envelope_fingerprint,
            verification=verification,
            agent_receipt_copy=copy,
            linkage=linkage,
            received_at=admission.received_at,
            valid_until=request.expires_at,
            receipt_fingerprint=attempt.attempt_fingerprint,
        )
        receipt = EndToEndInertDeliveryReceiptV1.model_validate(
            receipt_seed.model_copy(
                update={"receipt_fingerprint": receipt_fingerprint(receipt_seed)}
            )
        )
        audit_seed = EndToEndInertDeliveryAuditEvidenceV1.model_construct(
            receipt_id=receipt.receipt_id,
            receipt_fingerprint=receipt.receipt_fingerprint,
            verification_fingerprint=verification.verification_fingerprint,
            send_attempt_id=attempt.send_attempt_id,
            attempt_fingerprint=attempt.attempt_fingerprint,
            prior_send_receipt_fingerprint=prior.receipt_fingerprint,
            envelope_fingerprint=request.envelope.envelope_fingerprint,
            agent_result_fingerprint=result_fingerprint,
            admission_fingerprint=admission.admission_fingerprint,
            acknowledgement_fingerprint=acknowledgement.acknowledgement_fingerprint,
            linkage_fingerprint=linkage_fingerprint(linkage),
            endpoint_fingerprint=request.endpoint_fingerprint,
            idempotency_key_fingerprint=key_fingerprint,
            operator_fingerprint=operator_fingerprint(operator_id),
            correlation_id=_safe_correlation(correlation_id),
            requested_at=request.requested_at,
            received_at=admission.received_at,
            completed_at=now,
            lifecycle="verified_inert_receipt",
            evidence_fingerprint=attempt.attempt_fingerprint,
        )
        audit = EndToEndInertDeliveryAuditEvidenceV1.model_validate(
            audit_seed.model_copy(
                update={"evidence_fingerprint": audit_evidence_fingerprint(audit_seed)}
            )
        )
        return StoredInertDeliveryReceipt(receipt, verification, audit)

    def _success(self, stored: StoredInertDeliveryReceipt, *, disposition: str):
        receipt = stored.receipt
        observed_at = self._now()
        status = EndToEndInertDeliveryStatusV1(
            receipt_id=receipt.receipt_id,
            send_attempt_id=receipt.send_attempt_id,
            operator_id=receipt.operator_id,
            observed_at=observed_at,
            valid_until=receipt.valid_until,
            lifecycle=(
                "verified_inert_receipt"
                if observed_at < receipt.valid_until
                else "expired"
            ),
        )
        return EndToEndInertDeliveryResultV1(
            disposition=disposition,
            receipt=receipt,
            verification=stored.verification,
            agent_receipt_copy=receipt.agent_receipt_copy,
            status=status,
            audit_evidence=stored.audit_evidence,
            error=None,
        )

    def _failure(self, code: str, correlation_id: str):
        return EndToEndInertDeliveryResultV1(
            disposition=("ambiguous" if code == "ambiguous" else "unavailable"),
            receipt=None,
            verification=None,
            agent_receipt_copy=None,
            status=None,
            audit_evidence=None,
            error=EndToEndInertDeliveryRedactedErrorV1(
                error_code=code, correlation_id=_safe_correlation(correlation_id)
            ),
        )

    def _now(self) -> str:
        value = self._clock().astimezone(UTC).replace(microsecond=0)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_correlation(value: str) -> str:
    try:
        EndToEndInertDeliveryRedactedErrorV1(
            error_code="unavailable", correlation_id=value
        )
        return value
    except Exception:  # noqa: BLE001 - malformed correlation values are redacted
        return "inert-receipt-redacted"


def _same_value(left: object, right: object) -> bool:
    """Compare versioned value objects by their closed JSON representation."""
    return canonical_json(left) == canonical_json(right)


def _validation_code(error: ValueError) -> str:
    message = str(error).lower()
    if "ownership" in message:
        return "ownership_mismatch"
    if "stale" in message or "expired" in message or "freshness" in message:
        return "expired"
    if "fingerprint" in message:
        return "fingerprint_mismatch"
    if "linkage" in message or "mismatch" in message:
        return "linkage_mismatch"
    return "response_invalid"
