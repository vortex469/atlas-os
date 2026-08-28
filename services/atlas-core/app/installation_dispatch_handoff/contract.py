"""Closed, pure models for the frozen Installation Dispatch Handoff v1.

These values describe preparation evidence only.  Nothing in this module performs
I/O, delivers an envelope, invokes Agent, admits work, or authorizes execution.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    TypeAdapter,
    model_validator,
)

from app.installation_approval_intent.contract import InstallationApprovalIntentV1
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    OwnerId,
    candidate_record_state,
)
from app.installation_execution_request.contract import (
    FingerprintV1,
    InstallationExecutionRequestV1,
    execution_request_fingerprint,
    execution_request_state,
)
from app.installation_plan.contract import LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 1024
MAX_ENVELOPE_BYTES = 32 * 1024


class StrictContractError(ValueError):
    """A wire value is outside the closed contract."""


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


EmptyArray = Annotated[tuple[()], BeforeValidator(_tuple)]


class InstallationDispatchHandoffCreateV1(_Closed):
    schema: Literal["installation-dispatch-handoff-create-v1"] = (
        "installation-dispatch-handoff-create-v1"
    )
    execution_request_id: CanonicalUuid4

    @model_validator(mode="after")
    def bounded_body(self) -> InstallationDispatchHandoffCreateV1:
        if len(_canonical(self.model_dump(mode="json"))) > MAX_CREATE_BYTES:
            raise ValueError("create body exceeds 1 KiB")
        return self


class InstallationDispatchRecipientV1(_Closed):
    service: Literal["atlas-agent"] = "atlas-agent"
    intake_contract: Literal["agent-installation-dispatch-intake-v1"] = (
        "agent-installation-dispatch-intake-v1"
    )


class InstallationDispatchLinkageV1(_Closed):
    candidate_record_id: CanonicalUuid4
    candidate_envelope_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    approval_intent_id: CanonicalUuid4
    approval_intent_fingerprint: FingerprintV1
    agent_request_id: CanonicalUuid4
    agent_request_fingerprint: FingerprintV1
    agent_validation_fingerprint: FingerprintV1
    agent_evidence_fingerprint: FingerprintV1
    destination_fingerprint: LowerHex64
    source_plan_fingerprint: FingerprintV1
    artifact_policy_fingerprint: FingerprintV1
    execution_request_id: CanonicalUuid4
    execution_request_fingerprint: FingerprintV1


class InstallationDispatchEnvelopeV1(_Closed):
    schema: Literal["installation-dispatch-envelope-v1"] = (
        "installation-dispatch-envelope-v1"
    )
    dispatch_envelope_id: CanonicalUuid4
    prepared_at: UtcSecond
    valid_until: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["handoff-only"] = "handoff-only"
    recipient: InstallationDispatchRecipientV1
    linkage: InstallationDispatchLinkageV1
    statement: Literal["core_prepared_non_executing_agent_handoff"] = (
        "core_prepared_non_executing_agent_handoff"
    )
    delivery_authorized: Literal[False] = False
    agent_admission_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False
    dispatch_envelope_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def bounded_envelope(self) -> InstallationDispatchEnvelopeV1:
        prepared = _instant(self.prepared_at)
        valid_until = _instant(self.valid_until)
        if valid_until <= prepared:
            raise ValueError("dispatch envelope has no validity window")
        if valid_until > prepared + timedelta(seconds=60):
            raise ValueError("dispatch envelope exceeds 60-second lifetime")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_ENVELOPE_BYTES:
            raise ValueError("dispatch envelope exceeds 32 KiB")
        return self


DispatchEnvelopeState = Literal["prepared", "expired"]


class AgentInstallationDispatchIntakeV1(_Closed):
    schema: Literal["agent-installation-dispatch-intake-v1"] = (
        "agent-installation-dispatch-intake-v1"
    )
    envelope: InstallationDispatchEnvelopeV1


class AgentInstallationDispatchAdmissionV1(_Closed):
    schema: Literal["agent-installation-dispatch-admission-v1"] = (
        "agent-installation-dispatch-admission-v1"
    )
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    evaluated_at: UtcSecond
    status: Literal["valid_but_not_admitted"] = "valid_but_not_admitted"
    reason_codes: EmptyArray
    delivery_accepted: Literal[False] = False
    execution_admitted: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    dispatch_admission_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_admission(self) -> AgentInstallationDispatchAdmissionV1:
        expected = _fingerprint(
            "atlas:agent-installation-dispatch-admission:v1",
            self.model_dump(mode="json", exclude={"dispatch_admission_fingerprint"}),
        )
        if self.dispatch_admission_fingerprint != expected:
            raise ValueError("dispatch admission fingerprint mismatch")
        return self


InstallationDispatchErrorCode = Literal[
    "malformed",
    "not_found",
    "not_current",
    "ownership_mismatch",
    "proof_mismatch",
    "evidence_unavailable",
    "replay_conflict",
    "quota_exceeded",
    "unavailable",
]


def _correlation(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value) <= 128
        or not value[0].isalnum()
        or any(character not in "._:-" and not character.isalnum() for character in value)
    ):
        raise ValueError("invalid correlation ID")
    return value


class InstallationDispatchErrorV1(_Closed):
    schema: Literal["installation-dispatch-error-v1"] = (
        "installation-dispatch-error-v1"
    )
    error_code: InstallationDispatchErrorCode
    correlation_id: Annotated[str, AfterValidator(_correlation)]
    dispatch_envelope_id: CanonicalUuid4 | None = None
    dispatch_envelope_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True


class InstallationDispatchAuditEvidenceV1(_Closed):
    """Safe projection proving preparation, never delivery or admission."""

    schema: Literal["installation-dispatch-audit-evidence-v1"] = (
        "installation-dispatch-audit-evidence-v1"
    )
    dispatch_envelope_id: CanonicalUuid4
    dispatch_envelope_fingerprint: FingerprintV1
    prepared_at: UtcSecond
    valid_until: UtcSecond
    lifecycle: DispatchEnvelopeState
    evidence_provenance: Literal["core_prepared_not_delivered"] = (
        "core_prepared_not_delivered"
    )
    delivered: Literal[False] = False
    agent_admitted: Literal[False] = False
    work_started: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False


def _visible_ascii(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value.encode()) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("idempotency key is out of bounds")
    return value


class InstallationDispatchIdempotencyV1(_Closed):
    """Operator-scoped reservation identity; it conveys no replay authority."""

    owner_id: OwnerId
    operation: Literal["create-installation-dispatch-handoff"] = (
        "create-installation-dispatch-handoff"
    )
    key: Annotated[str, AfterValidator(_visible_ascii)]
    create_fingerprint: FingerprintV1
    execution_request_id: CanonicalUuid4
    replay_allowed: Literal[False] = False


class InstallationDispatchResultV1(_Closed):
    disposition: Literal["created", "exact_replay", "unavailable"]
    envelope: InstallationDispatchEnvelopeV1 | None
    error: InstallationDispatchErrorV1 | None
    delivery_attempted: Literal[False] = False
    agent_invoked: Literal[False] = False

    @model_validator(mode="after")
    def exact_result(self) -> InstallationDispatchResultV1:
        success = self.disposition in ("created", "exact_replay")
        if success != (self.envelope is not None and self.error is None):
            raise ValueError("result disposition and value disagree")
        if not success and (
            self.envelope is not None
            or self.error is None
            or self.error.error_code != "unavailable"
        ):
            raise ValueError("unavailable result must contain only unavailable error")
        return self


def build_dispatch_envelope(
    *,
    owner_id: str,
    dispatch_envelope_id: str,
    prepared_at: str,
    create: InstallationDispatchHandoffCreateV1,
    candidate_envelope: InstallationCandidateRecordEnvelopeV1,
    approval_intent: InstallationApprovalIntentV1,
    execution_request: InstallationExecutionRequestV1,
) -> InstallationDispatchEnvelopeV1:
    """Validate the injected four-release chain and prepare inert evidence."""
    exact_create = InstallationDispatchHandoffCreateV1.model_validate(
        create.model_dump(mode="python")
    )
    candidate = InstallationCandidateRecordEnvelopeV1.model_validate(
        candidate_envelope.model_dump(mode="python")
    )
    intent = InstallationApprovalIntentV1.model_validate(
        approval_intent.model_dump(mode="python")
    )
    request = InstallationExecutionRequestV1.model_validate(
        execution_request.model_dump(mode="python")
    )
    TypeAdapter(OwnerId).validate_python(owner_id, strict=True)
    now = _instant(prepared_at)
    if candidate.owner_id != owner_id or intent.operator_id != owner_id:
        raise ValueError("ownership mismatch")
    if request.execution_request_fingerprint != execution_request_fingerprint(
        owner_id=owner_id, record=request
    ):
        raise ValueError("execution request fingerprint mismatch")
    if exact_create.execution_request_id != request.execution_request_id:
        raise ValueError("create linkage mismatch")
    if now < _instant(request.recorded_at):
        raise ValueError("handoff time precedes execution request")
    if candidate_record_state(candidate, now=prepared_at) != "active":
        raise ValueError("candidate record is not current")
    if execution_request_state(request, now=prepared_at) != "recorded":
        raise ValueError("execution request is not current")
    if _instant(intent.recorded_at) > now:
        raise ValueError("approval intent is from the future")

    record = candidate.candidate_record
    subject = intent.approved_subject
    if (
        subject.candidate_record_id,
        subject.candidate_envelope_fingerprint,
        subject.admission_fingerprint,
        subject.candidate_record_fingerprint,
    ) != (
        candidate.candidate_record_id,
        candidate.envelope_fingerprint,
        candidate.admission_fingerprint,
        record.record_fingerprint,
    ):
        raise ValueError("approval linkage mismatch")

    source = request.linkage
    expected_source = (
        candidate.candidate_record_id,
        candidate.envelope_fingerprint,
        candidate.admission_fingerprint,
        record.record_fingerprint,
        intent.approval_intent_id,
        intent.intent_fingerprint,
    )
    actual_source = (
        source.candidate_record_id,
        source.candidate_envelope_fingerprint.value,
        source.admission_fingerprint.value,
        source.candidate_record_fingerprint.value,
        source.approval_intent_id,
        source.approval_intent_fingerprint.value,
    )
    if actual_source != expected_source:
        raise ValueError("execution request linkage mismatch")

    valid_until = min(
        _instant(record.valid_until),
        _instant(request.valid_until),
        now + timedelta(seconds=60),
    )
    if valid_until <= now:
        raise ValueError("dispatch envelope has no validity window")
    linkage = InstallationDispatchLinkageV1(
        **source.model_dump(mode="python"),
        execution_request_id=request.execution_request_id,
        execution_request_fingerprint=request.execution_request_fingerprint,
    )
    raw: dict[str, Any] = {
        "schema": "installation-dispatch-envelope-v1",
        "dispatch_envelope_id": dispatch_envelope_id,
        "prepared_at": prepared_at,
        "valid_until": _format(valid_until),
        "operation": "install-container",
        "mode": "handoff-only",
        "recipient": InstallationDispatchRecipientV1().model_dump(mode="json"),
        "linkage": linkage.model_dump(mode="json"),
        "statement": "core_prepared_non_executing_agent_handoff",
        "delivery_authorized": False,
        "agent_admission_authorized": False,
        "execution_authorized": False,
        "mutation_authorized": False,
        "replay_allowed": False,
    }
    raw["dispatch_envelope_fingerprint"] = dispatch_envelope_fingerprint(
        owner_id=owner_id, envelope=raw
    )
    return InstallationDispatchEnvelopeV1.model_validate(raw)


def validate_agent_intake(
    intake: AgentInstallationDispatchIntakeV1, *, owner_id: str, evaluated_at: str
) -> AgentInstallationDispatchAdmissionV1:
    """Parse an injected envelope into a non-admission result, without I/O."""
    exact = AgentInstallationDispatchIntakeV1.model_validate(
        intake.model_dump(mode="python")
    )
    envelope = exact.envelope
    if envelope.dispatch_envelope_fingerprint != dispatch_envelope_fingerprint(
        owner_id=owner_id, envelope=envelope
    ):
        raise ValueError("dispatch envelope fingerprint mismatch")
    if dispatch_envelope_state(envelope, now=evaluated_at) != "prepared":
        raise ValueError("dispatch envelope is not current")
    raw: dict[str, Any] = {
        "schema": "agent-installation-dispatch-admission-v1",
        "dispatch_envelope_id": envelope.dispatch_envelope_id,
        "dispatch_envelope_fingerprint": envelope.dispatch_envelope_fingerprint.model_dump(
            mode="json"
        ),
        "evaluated_at": evaluated_at,
        "status": "valid_but_not_admitted",
        "reason_codes": [],
        "delivery_accepted": False,
        "execution_admitted": False,
        "worker_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["dispatch_admission_fingerprint"] = _fingerprint(
        "atlas:agent-installation-dispatch-admission:v1", raw
    )
    return AgentInstallationDispatchAdmissionV1.model_validate(raw)


def dispatch_envelope_state(
    envelope: InstallationDispatchEnvelopeV1, *, now: str
) -> DispatchEnvelopeState:
    exact = InstallationDispatchEnvelopeV1.model_validate(
        envelope.model_dump(mode="python")
    )
    instant = _instant(now)
    if instant < _instant(exact.prepared_at):
        raise ValueError("lifecycle instant precedes preparation")
    return "prepared" if instant < _instant(exact.valid_until) else "expired"


def dispatch_envelope_fingerprint(
    *, owner_id: str, envelope: InstallationDispatchEnvelopeV1 | dict[str, Any]
) -> FingerprintV1:
    raw = (
        envelope.model_dump(mode="json")
        if isinstance(envelope, BaseModel)
        else dict(envelope)
    )
    raw.pop("dispatch_envelope_fingerprint", None)
    return _fingerprint(
        "atlas:installation-dispatch-envelope:v1",
        {"owner_id": owner_id, "envelope": raw},
    )


def create_fingerprint(create: InstallationDispatchHandoffCreateV1) -> FingerprintV1:
    return _fingerprint(
        "atlas:installation-dispatch-handoff-create:v1",
        create.model_dump(mode="json"),
    )


def parse_create_json(payload: bytes | str) -> InstallationDispatchHandoffCreateV1:
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > MAX_CREATE_BYTES:
        raise StrictContractError("malformed")

    def closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StrictContractError("malformed")
            result[key] = value
        return result

    try:
        value = json.loads(encoded.decode(), object_pairs_hook=closed_object)
        if not isinstance(value, dict):
            raise StrictContractError("malformed")
        return InstallationDispatchHandoffCreateV1.model_validate(value)
    except StrictContractError:
        raise
    except Exception as error:
        raise StrictContractError("malformed") from error


def _canonical(value: object) -> bytes:
    def validate(item: object) -> None:
        if isinstance(item, str):
            if item != unicodedata.normalize("NFC", item):
                raise ValueError("strings must be NFC")
        elif isinstance(item, bool) or item is None:
            return
        elif isinstance(item, int | float):
            raise TypeError("JSON numbers are prohibited")
        elif isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON keys must be strings")
                validate(key)
                validate(child)
        elif isinstance(item, list | tuple):
            for child in item:
                validate(child)
        else:
            raise TypeError("value is outside canonical domain")

    validate(value)
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _format(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
