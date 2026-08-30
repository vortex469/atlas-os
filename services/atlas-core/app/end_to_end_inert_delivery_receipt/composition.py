"""Explicit one-shot v0.33 composition; no route or production registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.dormant_agent_intake_delivery_wiring.contract import (
    DormantAgentIntakeEndpointV1,
    endpoint_fingerprint,
)
from app.live_delivery_send_boundary.contract import (
    LiveDeliverySendReceiptV1,
    LiveDeliveryTransportConfigurationV1,
)
from app.live_delivery_send_boundary.transport import (
    LiveDeliveryCredentialResolver,
    LiveDeliveryHttpsTransport,
)

from .contract import (
    MAX_AGENT_RESPONSE_BYTES,
    AgentAdmissionReceiptAuthenticityV1,
    AgentAdmissionReceiptCopyV1,
    AgentLiveIntakeResultCopyV1,
    EndToEndInertDeliveryRequestV1,
    EndToEndInertDeliveryResultV1,
    agent_receipt_copy_fingerprint,
    parse_agent_result_json,
)
from .service import (
    InertDeliveryReceiptAmbiguousError,
    InertDeliveryReceiptEvidence,
    InertDeliveryReceiptNotCurrentError,
    InertDeliveryReceiptRejectedError,
    InertDeliveryReceiptService,
)
from .store import InertDeliveryReceiptStore, canonical_json


class PriorLiveSendReceiptWriter(Protocol):
    """Append and return the same-attempt terminal v0.31 send receipt."""

    def record_admitted(
        self,
        *,
        operator_id: str,
        request: EndToEndInertDeliveryRequestV1,
        agent_result: AgentLiveIntakeResultCopyV1,
        completed_at: str,
        correlation_id: str,
    ) -> LiveDeliverySendReceiptV1: ...


@dataclass(frozen=True)
class _OperationEvidenceReader:
    configuration: LiveDeliveryTransportConfigurationV1
    authenticity: AgentAdmissionReceiptAuthenticityV1
    credential_resolver: LiveDeliveryCredentialResolver
    transport: LiveDeliveryHttpsTransport
    prior_receipt_writer: PriorLiveSendReceiptWriter
    clock: Callable[[], datetime]
    idempotency_key: str
    correlation_id: str

    def resolve(
        self, *, operator_id: str, request: EndToEndInertDeliveryRequestV1
    ) -> InertDeliveryReceiptEvidence:
        if not self.configuration.enabled:
            raise InertDeliveryReceiptNotCurrentError
        now = _server_now(self.clock)
        if not request.requested_at <= now < request.expires_at:
            raise ValueError("evidence is stale or expired")
        endpoint = DormantAgentIntakeEndpointV1.model_validate(
            self.configuration.endpoint.model_dump(mode="python")
        )
        if (
            endpoint_fingerprint(endpoint) != request.endpoint_fingerprint
            or self.authenticity.endpoint_fingerprint != request.endpoint_fingerprint
        ):
            raise ValueError("endpoint fingerprint mismatch")
        body = canonical_json(request.envelope)
        if not 0 < len(body) <= self.configuration.maximum_request_bytes:
            raise ValueError("Agent envelope exceeds transport bound")

        credential = self.credential_resolver.resolve_once(
            self.configuration.authentication
        )
        try:
            token = credential.value.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("credential material is invalid") from error
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Idempotency-Key": self.idempotency_key,
        }
        try:
            response = self.transport.transmit_once(
                endpoint=self.configuration.endpoint,
                body=body,
                headers=headers,
                connect_timeout_ms=self.configuration.endpoint.connect_timeout_ms,
                response_timeout_ms=self.configuration.endpoint.response_timeout_ms,
                maximum_response_bytes=self.configuration.maximum_response_bytes,
            )
        except Exception as error:
            raise InertDeliveryReceiptAmbiguousError from error
        finally:
            del token, credential, headers

        if len(response.body) > MAX_AGENT_RESPONSE_BYTES:
            raise InertDeliveryReceiptAmbiguousError
        if 500 <= response.status_code <= 599:
            raise InertDeliveryReceiptAmbiguousError
        if not 200 <= response.status_code <= 299:
            raise InertDeliveryReceiptRejectedError
        try:
            result = parse_agent_result_json(response.body)
        except Exception as error:
            raise InertDeliveryReceiptAmbiguousError from error
        if result.outcome != "admitted_for_evidence_only":
            raise InertDeliveryReceiptRejectedError
        try:
            admission = result.admission
            acknowledgement = result.acknowledgement
            if admission is None or acknowledgement is None or not (
                result.send_attempt_id == request.send_attempt_id
                and admission.operator_id == operator_id
                and admission.attempt_fingerprint == request.attempt_fingerprint
                and admission.envelope_fingerprint
                == request.envelope.envelope_fingerprint
                and admission.request_fingerprint
                == request.envelope.request_fingerprint
                and admission.linkage == request.envelope.send_attempt.linkage
                and admission.valid_until
                == acknowledgement.valid_until
                == request.expires_at
            ):
                raise ValueError("Agent result does not bind the reserved request")
            copy_seed = AgentAdmissionReceiptCopyV1.model_construct(
                result=result,
                authenticity=self.authenticity,
                copied_at=_server_now(self.clock),
                copy_fingerprint=request.attempt_fingerprint,
            )
            receipt_copy = AgentAdmissionReceiptCopyV1.model_validate(
                copy_seed.model_copy(
                    update={
                        "copy_fingerprint": agent_receipt_copy_fingerprint(copy_seed)
                    }
                )
            )
            prior_receipt = self.prior_receipt_writer.record_admitted(
                operator_id=operator_id,
                request=request,
                agent_result=result,
                completed_at=receipt_copy.copied_at,
                correlation_id=self.correlation_id,
            )
        except Exception as error:
            raise InertDeliveryReceiptAmbiguousError from error
        return InertDeliveryReceiptEvidence(
            prior_send_receipt=prior_receipt,
            agent_receipt_copy=receipt_copy,
            response_body=response.body,
        )


class EndToEndInertDeliveryComposition:
    """Compose one reserved inert send with one verified receipt append."""

    def __init__(
        self,
        *,
        configuration: LiveDeliveryTransportConfigurationV1,
        authenticity: AgentAdmissionReceiptAuthenticityV1,
        credential_resolver: LiveDeliveryCredentialResolver,
        transport: LiveDeliveryHttpsTransport,
        prior_receipt_writer: PriorLiveSendReceiptWriter,
        store: InertDeliveryReceiptStore,
        clock: Callable[[], datetime],
        receipt_id_factory: Callable[[], str],
    ) -> None:
        self._configuration = LiveDeliveryTransportConfigurationV1.model_validate(
            configuration.model_dump(mode="python")
        )
        self._authenticity = AgentAdmissionReceiptAuthenticityV1.model_validate(
            authenticity.model_dump(mode="python")
        )
        self._credential_resolver = credential_resolver
        self._transport = transport
        self._prior_receipt_writer = prior_receipt_writer
        self._store = store
        self._clock = clock
        self._receipt_id_factory = receipt_id_factory

    def compose_once(
        self,
        request: EndToEndInertDeliveryRequestV1,
        *,
        authenticated_operator_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> EndToEndInertDeliveryResultV1:
        reader = _OperationEvidenceReader(
            configuration=self._configuration,
            authenticity=self._authenticity,
            credential_resolver=self._credential_resolver,
            transport=self._transport,
            prior_receipt_writer=self._prior_receipt_writer,
            clock=self._clock,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        service = InertDeliveryReceiptService(
            evidence_reader=reader,
            store=self._store,
            clock=self._clock,
            receipt_id_factory=self._receipt_id_factory,
        )
        return service.verify(
            request,
            authenticated_operator_id=authenticated_operator_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )


def _server_now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if (
        value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
        or value.microsecond
    ):
        raise ValueError("trusted Core clock must return whole-second UTC")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["EndToEndInertDeliveryComposition", "PriorLiveSendReceiptWriter"]
