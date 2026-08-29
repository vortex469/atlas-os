"""Explicit one-shot v0.31 Core transport coordinator.

The module deliberately provides no concrete HTTP or credential implementation.
Production composition must inject both narrow boundaries explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from .contract import (
    MAX_RESPONSE_BYTES,
    LiveDeliveryAuthenticationReferenceV1,
    LiveDeliveryEndpointV1,
    LiveDeliverySendAuditEvidenceV1,
    LiveDeliverySendCreateV1,
    LiveDeliverySendReceiptV1,
    LiveDeliverySendRedactedErrorV1,
    LiveDeliverySendTransportResultV1,
    agent_audit_evidence_fingerprint,
    agent_result_fingerprint,
    audit_evidence_fingerprint,
    canonical_agent_request,
    parse_agent_result_json,
    receipt_fingerprint,
    validate_agent_result,
)
from .service import LiveDeliverySendService
from .store import LiveDeliverySendStore, LiveDeliverySendStoreError


@dataclass(frozen=True)
class ResolvedBearerCredential:
    """Ephemeral secret value. It is never a contract model or stored value."""

    value: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not 1 <= len(self.value) <= 4096
            or b"\x00" in self.value
            or b"\r" in self.value
            or b"\n" in self.value
        ):
            raise ValueError("credential material is invalid")


class LiveDeliveryCredentialResolver(Protocol):
    def resolve_once(
        self, reference: LiveDeliveryAuthenticationReferenceV1
    ) -> ResolvedBearerCredential: ...


@dataclass(frozen=True)
class LiveDeliveryHttpResponse:
    status_code: int
    body: bytes


class LiveDeliveryTransportUncertain(RuntimeError):
    """The caller cannot prove whether Agent committed the request."""


class LiveDeliveryHttpsTransport(Protocol):
    def transmit_once(
        self,
        *,
        endpoint: LiveDeliveryEndpointV1,
        body: bytes,
        headers: Mapping[str, str],
        connect_timeout_ms: int,
        response_timeout_ms: int,
        maximum_response_bytes: int,
    ) -> LiveDeliveryHttpResponse: ...


class LiveDeliverySendCoordinator:
    """Reserve permanently, then offer exactly one synchronous HTTPS POST."""

    def __init__(
        self,
        *,
        reservation_service: LiveDeliverySendService,
        store: LiveDeliverySendStore,
        credential_resolver: LiveDeliveryCredentialResolver,
        transport: LiveDeliveryHttpsTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self._service = reservation_service
        self._store = store
        self._credential_resolver = credential_resolver
        self._transport = transport
        self._clock = clock

    def send_once(
        self,
        create: LiveDeliverySendCreateV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> LiveDeliverySendTransportResultV1:
        reserved = self._service.create(
            create,
            authenticated_operator_id=authenticated_operator_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        if reserved.attempt is None:
            return self._unavailable(reserved.error)
        attempt = reserved.attempt
        try:
            stored = self._store.get(
                operator_id=authenticated_operator_id,
                send_attempt_id=attempt.send_attempt_id,
            )
            if stored.receipt is not None:
                return self._stored_result(stored, exact_replay=True)
            if reserved.disposition == "exact_replay":
                return self._close(
                    stored=stored,
                    correlation_id=correlation_id,
                    lifecycle="ambiguous",
                    status_class="none",
                    error_code="ambiguous",
                )
            configuration = self._service.configuration
            if not configuration.enabled:
                raise ValueError("transport is disabled")
            body = canonical_agent_request(stored.envelope.request)
            if len(body) != stored.envelope.content_length:
                raise ValueError("request body changed after reservation")
            credential = self._credential_resolver.resolve_once(
                configuration.authentication
            )
            try:
                token = credential.value.decode("ascii")
            except UnicodeDecodeError as error:
                raise ValueError("credential material is invalid") from error
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            }
            response = self._transport.transmit_once(
                endpoint=configuration.endpoint,
                body=body,
                headers=headers,
                connect_timeout_ms=configuration.endpoint.connect_timeout_ms,
                response_timeout_ms=configuration.endpoint.response_timeout_ms,
                maximum_response_bytes=configuration.maximum_response_bytes,
            )
            del token, credential, headers
            if len(response.body) > MAX_RESPONSE_BYTES:
                raise LiveDeliveryTransportUncertain("response exceeded bound")
            if 500 <= response.status_code <= 599:
                raise LiveDeliveryTransportUncertain("Agent result is uncertain")
            if not 200 <= response.status_code <= 299:
                return self._close(
                    stored=stored, correlation_id=correlation_id,
                    lifecycle="rejected", status_class=_status_class(response.status_code),
                    error_code="agent_rejected",
                )
            try:
                result = parse_agent_result_json(response.body)
                result, acknowledgement = validate_agent_result(
                    result=result,
                    delivery_preparation_id=attempt.linkage.delivery_preparation_id,
                    request=stored.envelope.request,
                    operator_id=authenticated_operator_id,
                    validated_at=self._now(),
                )
            except Exception as error:
                raise LiveDeliveryTransportUncertain("Agent response is invalid") from error
            if result.outcome == "rejected":
                return self._close(
                    stored=stored, correlation_id=correlation_id,
                    lifecycle="rejected", status_class="2xx",
                    error_code="agent_rejected", agent_result=result,
                )
            return self._close(
                stored=stored, correlation_id=correlation_id,
                lifecycle="admitted_evidence_only", status_class="2xx",
                agent_result=result, acknowledgement=acknowledgement,
            )
        except LiveDeliveryTransportUncertain:
            return self._close_after_failure(
                authenticated_operator_id, attempt.send_attempt_id,
                correlation_id, "ambiguous",
            )
        except Exception:  # noqa: BLE001 - every injected failure is redacted
            return self._close_after_failure(
                authenticated_operator_id, attempt.send_attempt_id,
                correlation_id, "ambiguous",
            )

    def _close_after_failure(
        self, operator_id: str, attempt_id: str, correlation_id: str, code: str
    ) -> LiveDeliverySendTransportResultV1:
        try:
            stored = self._store.get(
                operator_id=operator_id, send_attempt_id=attempt_id
            )
            if stored.receipt is not None:
                return self._stored_result(stored, exact_replay=False)
            return self._close(
                stored=stored, correlation_id=correlation_id,
                lifecycle="ambiguous", status_class="none", error_code=code,
            )
        except Exception:  # noqa: BLE001 - no transport detail may escape
            return self._unavailable(
                LiveDeliverySendRedactedErrorV1(
                    error_code="unavailable", correlation_id=_safe_correlation(correlation_id)
                )
            )

    def _close(
        self,
        *,
        stored,
        correlation_id: str,
        lifecycle: str,
        status_class: str,
        error_code: str | None = None,
        agent_result=None,
        acknowledgement=None,
    ) -> LiveDeliverySendTransportResultV1:
        completed_at = self._now()
        error = None
        if error_code is not None:
            error = LiveDeliverySendRedactedErrorV1(
                error_code=error_code,
                correlation_id=_safe_correlation(correlation_id),
                send_attempt_id=stored.attempt.send_attempt_id,
                attempt_fingerprint=stored.attempt.attempt_fingerprint,
            )
        response_fp = None if agent_result is None else agent_result_fingerprint(agent_result)
        admission = None if agent_result is None else agent_result.admission
        raw = {
            "schema": "live-delivery-send-receipt-v1",
            "send_attempt_id": stored.attempt.send_attempt_id,
            "attempt_fingerprint": stored.attempt.attempt_fingerprint.model_dump(mode="json"),
            "completed_at": completed_at,
            "lifecycle": lifecycle,
            "http_status_class": status_class,
            "response_fingerprint": None if response_fp is None else response_fp.model_dump(mode="json"),
            "admission_fingerprint": None if admission is None else admission.admission_fingerprint.model_dump(mode="json"),
            "acknowledgement_fingerprint": None if acknowledgement is None else acknowledgement.acknowledgement_fingerprint.model_dump(mode="json"),
            "agent_audit_evidence_fingerprint": None if admission is None else agent_audit_evidence_fingerprint(admission).model_dump(mode="json"),
            "redacted_error": None if error is None else error.model_dump(mode="json"),
            "agent_contacted": True,
            "evidence_admitted": lifecycle == "admitted_evidence_only",
            "execution_admission_granted": False,
            "execution_authorized": False,
            "installation_allowed": False,
            "worker_allowed": False,
            "workflow_allowed": False,
            "deployment_allowed": False,
            "mutation_allowed": False,
            "replay_allowed": False,
        }
        raw["receipt_fingerprint"] = receipt_fingerprint(raw).model_dump(mode="json")
        receipt = LiveDeliverySendReceiptV1.model_validate(raw)
        audit = _terminal_audit(
            stored.audit_evidence, receipt=receipt, completed_at=completed_at
        )
        closed = self._store.append_outcome(
            operator_id=stored.attempt.operator_id,
            receipt=receipt,
            agent_result=agent_result,
            acknowledgement=acknowledgement,
            audit_evidence=audit,
        )
        return self._stored_result(closed, exact_replay=False)

    @staticmethod
    def _stored_result(stored, *, exact_replay: bool):
        receipt = stored.receipt
        if receipt is None or stored.terminal_audit_evidence is None:
            raise LiveDeliverySendStoreError("unavailable")
        disposition = "exact_replay" if exact_replay else receipt.lifecycle
        return LiveDeliverySendTransportResultV1(
            disposition=disposition,
            attempt=stored.attempt,
            receipt=receipt,
            agent_result=stored.agent_result,
            acknowledgement=stored.acknowledgement,
            audit_evidence=stored.terminal_audit_evidence,
            error=receipt.redacted_error,
        )

    @staticmethod
    def _unavailable(error):
        return LiveDeliverySendTransportResultV1(
            disposition=(
                "unavailable"
                if error is None or error.error_code == "unavailable"
                else "rejected"
            ),
            attempt=None, receipt=None,
            agent_result=None, acknowledgement=None, audit_evidence=None,
            error=error or LiveDeliverySendRedactedErrorV1(
                error_code="unavailable", correlation_id="live-send-redacted"
            ),
        )

    def _now(self) -> str:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value) or value.microsecond:
            raise ValueError("trusted Core clock must return whole-second UTC")
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _terminal_audit(initial, *, receipt, completed_at: str):
    raw = initial.model_dump(mode="json")
    raw.update(
        receipt_fingerprint=receipt.receipt_fingerprint.model_dump(mode="json"),
        completed_at=completed_at,
        lifecycle=receipt.lifecycle,
        agent_disposition={
            "admitted_evidence_only": "admitted_for_evidence_only",
            "rejected": "rejected",
            "ambiguous": "unknown",
        }[receipt.lifecycle],
    )
    raw["evidence_fingerprint"] = audit_evidence_fingerprint(raw).model_dump(mode="json")
    return LiveDeliverySendAuditEvidenceV1.model_validate(raw)


def _status_class(status: int) -> str:
    if 400 <= status <= 499:
        return "4xx"
    if 500 <= status <= 599:
        return "5xx"
    return "none"


def _safe_correlation(value: str) -> str:
    candidate = value.encode("ascii", errors="ignore").decode("ascii")
    if not candidate or len(candidate) > 128 or any(
        not (character.isalnum() or character in "._:-") for character in candidate
    ):
        return "live-send-redacted"
    return candidate


__all__ = [
    "LiveDeliveryCredentialResolver", "LiveDeliveryHttpResponse",
    "LiveDeliveryHttpsTransport", "LiveDeliverySendCoordinator",
    "LiveDeliveryTransportUncertain", "ResolvedBearerCredential",
]
