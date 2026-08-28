"""Closed, pure models for the frozen Installation Execution Request v1 boundary.

Accepted values are immutable evidence records.  They never authorize dispatch,
Agent invocation, mutation, replay, or execution.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    model_validator,
)

from app.installation_approval_intent.contract import InstallationApprovalIntentV1
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    OwnerId,
    candidate_record_state,
)
from app.installation_plan.contract import Id64, LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_AGENT_REQUEST_BYTES = 32 * 1024
MAX_CREATE_BYTES = 96 * 1024
MAX_RECORD_BYTES = 64 * 1024

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PATH = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*\.(?:yaml|yml)"
)
_CONTAINER = re.compile(r"atlas-[0-9a-f]{16}")
_CORRELATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class StrictContractError(ValueError):
    """A wire value is outside the closed contract."""


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _ascii_match(value: str, pattern: re.Pattern[str], message: str) -> str:
    if not value.isascii() or pattern.fullmatch(value) is None:
        raise ValueError(message)
    return value


def _digest(value: str) -> str:
    return _ascii_match(value, _DIGEST, "invalid sha256 digest")


def _path(value: str) -> str:
    if not 1 <= len(value) <= 512 or len(value.split("/")) > 32:
        raise ValueError("invalid repository path")
    return _ascii_match(value, _PATH, "invalid repository path")


def _container(value: str) -> str:
    return _ascii_match(value, _CONTAINER, "invalid container name")


def _service_id(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value) <= 255
        or re.fullmatch(r"[a-z0-9][a-z0-9._:-]*", value) is None
    ):
        raise ValueError("invalid service ID")
    return value


Sha256Digest = Annotated[str, AfterValidator(_digest)]
RepoPath = Annotated[str, AfterValidator(_path)]
ContainerName = Annotated[str, AfterValidator(_container)]
ServiceId = Annotated[str, AfterValidator(_service_id)]


def _tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


EmptyArray = Annotated[tuple[()], BeforeValidator(_tuple)]


class FingerprintV1(_Closed):
    algorithm: Literal["sha256"]
    canonicalization: Literal["atlas-jcs-nfc-v1"]
    value: LowerHex64


class InstallationRequestSubjectV1(_Closed):
    provider: Literal["proxmox"]
    resource_type: Literal["qemu"]
    placement_kind: Literal["existing-guest"]
    resource_id: Id64
    destination_fingerprint: LowerHex64


# Retain the exact v0.22 public model name while keeping the Core-specific name
# descriptive at the v0.23 boundary.
InstallationSubjectV1 = InstallationRequestSubjectV1


class ApprovedCandidateProofV1(_Closed):
    candidate_record_id: CanonicalUuid4
    candidate_envelope_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    approval_intent_id: CanonicalUuid4
    approval_intent_fingerprint: FingerprintV1


class TmpfsV1(_Closed):
    container_path: Literal["/tmp"]
    size_bytes: Literal["67108864"]
    options: Annotated[
        tuple[Literal["nodev", "noexec", "nosuid"], ...], BeforeValidator(_tuple)
    ]

    @model_validator(mode="after")
    def exact_options(self) -> TmpfsV1:
        if self.options != ("nodev", "noexec", "nosuid"):
            raise ValueError("tmpfs options do not match closed policy")
        return self


class InstallContainerArtifactV1(_Closed):
    kind: Literal["single-oci-container-v1"]
    source_plan_fingerprint: FingerprintV1
    source_repository_path: RepoPath
    source_service: ServiceId
    source_content_digest: Sha256Digest
    image: str
    runtime: Literal["rootless-podman"]
    container_name: ContainerName
    command: None
    entrypoint: None
    environment: EmptyArray
    secrets: EmptyArray
    host_mounts: EmptyArray
    devices: EmptyArray
    published_ports: EmptyArray
    network_mode: Literal["none"]
    privileged: Literal[False]
    read_only_root_filesystem: Literal[True]
    capabilities_add: EmptyArray
    capabilities_drop: Annotated[tuple[Literal["ALL"], ...], BeforeValidator(_tuple)]
    no_new_privileges: Literal[True]
    tmpfs: Annotated[tuple[TmpfsV1, ...], BeforeValidator(_tuple)]
    restart_policy: Literal["no"]

    @model_validator(mode="after")
    def exact_boundary(self) -> InstallContainerArtifactV1:
        if self.capabilities_drop != ("ALL",) or len(self.tmpfs) != 1:
            raise ValueError("runtime policy is not exact")
        repository, separator, digest = self.image.partition("@")
        if not separator or "@" in digest:
            raise ValueError("image must be a digest-pinned repository")
        if _normalize_oci_repository(repository) != repository:
            raise ValueError("image repository must be canonical")
        _digest(digest)
        return self

    @property
    def image_digest(self) -> str:
        return self.image.partition("@")[2]


class InstallContainerLimitsV1(_Closed):
    cpu_count: Literal["1"]
    memory_bytes: Literal["536870912"]
    pids: Literal["128"]
    tmpfs_bytes: Literal["67108864"]


class AgentInstallContainerRequestV1(_Closed):
    schema: Literal["agent-install-container-request-v1"]
    operation: Literal["install-container"]
    mode: Literal["validate-only"]
    request_id: CanonicalUuid4
    issued_at: UtcSecond
    expires_at: UtcSecond
    subject: InstallationRequestSubjectV1
    approval: ApprovedCandidateProofV1
    artifact: InstallContainerArtifactV1
    limits: InstallContainerLimitsV1
    request_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_request(self) -> AgentInstallContainerRequestV1:
        if _instant(self.expires_at) != _instant(self.issued_at) + timedelta(minutes=5):
            raise ValueError("Agent request window must be exactly five minutes")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_AGENT_REQUEST_BYTES:
            raise ValueError("Agent request exceeds 32 KiB")
        if self.request_fingerprint != _fingerprint(
            "atlas:agent-install-container-request:v1",
            self.model_dump(mode="json", exclude={"request_fingerprint"}),
        ):
            raise ValueError("Agent request fingerprint mismatch")
        return self


class AgentReasonCode(StrEnum):
    CONTRACT_MALFORMED = "contract_malformed"
    CONTRACT_UNKNOWN_FIELD = "contract_unknown_field"
    CONTRACT_OUT_OF_BOUNDS = "contract_out_of_bounds"
    REQUEST_FINGERPRINT_MISMATCH = "request_fingerprint_mismatch"
    REQUEST_NOT_CURRENT = "request_not_current"
    REQUEST_REPLAY_OR_DUPLICATE = "request_replay_or_duplicate"
    CANDIDATE_PROOF_MISSING = "candidate_proof_missing"
    CANDIDATE_PROOF_MISMATCH = "candidate_proof_mismatch"
    CANDIDATE_NOT_ACTIVE = "candidate_not_active"
    APPROVAL_PROOF_MISSING = "approval_proof_missing"
    APPROVAL_PROOF_MISMATCH = "approval_proof_mismatch"
    SUBJECT_UNSUPPORTED = "subject_unsupported"
    DESTINATION_IDENTITY_MISMATCH = "destination_identity_mismatch"
    ARTIFACT_UNSUPPORTED = "artifact_unsupported"
    ARTIFACT_SOURCE_MISMATCH = "artifact_source_mismatch"
    IMAGE_NOT_DIGEST_PINNED = "image_not_digest_pinned"
    RUNTIME_BOUNDARY_VIOLATED = "runtime_boundary_violated"
    FILESYSTEM_BOUNDARY_VIOLATED = "filesystem_boundary_violated"
    NETWORK_BOUNDARY_VIOLATED = "network_boundary_violated"
    VALIDATION_DEPENDENCY_UNAVAILABLE = "validation_dependency_unavailable"
    VALIDATION_CONTRACT_FAILURE = "validation_contract_failure"


_REASON_ORDER = {reason: index for index, reason in enumerate(AgentReasonCode)}


class AgentInstallContainerAuditEvidenceV1(_Closed):
    evidence_schema: Literal["agent-install-container-audit-evidence-v1"]
    request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    approval: ApprovedCandidateProofV1
    subject: InstallationRequestSubjectV1
    artifact_kind: Literal["single-oci-container-v1"]
    source_plan_fingerprint: FingerprintV1
    source_repository_path: RepoPath
    source_service: ServiceId
    source_content_digest: Sha256Digest
    image_digest: Sha256Digest
    runtime_limit_policy_fingerprint: FingerprintV1
    validated_at: UtcSecond
    status: Literal["valid_but_unsupported", "rejected"]
    reason_codes: Annotated[tuple[AgentReasonCode, ...], BeforeValidator(_tuple)]
    execution_supported: Literal[False]
    dispatch_allowed: Literal[False]
    mutation_allowed: Literal[False]
    replay_allowed: Literal[False]
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evidence(self) -> AgentInstallContainerAuditEvidenceV1:
        _status_reasons(self.status, self.reason_codes)
        expected = _fingerprint(
            "atlas:agent-install-container-audit-evidence:v1",
            self.model_dump(mode="json", exclude={"evidence_fingerprint"}),
        )
        if self.evidence_fingerprint != expected:
            raise ValueError("Agent evidence fingerprint mismatch")
        return self


class AgentInstallContainerValidationV1(_Closed):
    schema: Literal["agent-install-container-validation-v1"]
    request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    validated_at: UtcSecond
    status: Literal["valid_but_unsupported", "rejected"]
    reason_codes: Annotated[tuple[AgentReasonCode, ...], BeforeValidator(_tuple)]
    execution_supported: Literal[False]
    dispatch_allowed: Literal[False]
    mutation_allowed: Literal[False]
    replay_allowed: Literal[False]
    evidence: AgentInstallContainerAuditEvidenceV1
    validation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_validation(self) -> AgentInstallContainerValidationV1:
        _status_reasons(self.status, self.reason_codes)
        for name in (
            "request_id",
            "request_fingerprint",
            "validated_at",
            "status",
            "reason_codes",
            "execution_supported",
            "dispatch_allowed",
            "mutation_allowed",
            "replay_allowed",
        ):
            if getattr(self, name) != getattr(self.evidence, name):
                raise ValueError("Agent validation and evidence mismatch")
        expected = _fingerprint(
            "atlas:agent-install-container-validation:v1",
            self.model_dump(mode="json", exclude={"validation_fingerprint"}),
        )
        if self.validation_fingerprint != expected:
            raise ValueError("Agent validation fingerprint mismatch")
        return self


class InstallationExecutionRequestCreateV1(_Closed):
    schema: Literal["installation-execution-request-create-v1"] = (
        "installation-execution-request-create-v1"
    )
    candidate_record_id: CanonicalUuid4
    approval_intent_id: CanonicalUuid4
    agent_request: AgentInstallContainerRequestV1
    agent_validation: AgentInstallContainerValidationV1

    @model_validator(mode="after")
    def bounded_body(self) -> InstallationExecutionRequestCreateV1:
        if len(_canonical(self.model_dump(mode="json"))) > MAX_CREATE_BYTES:
            raise ValueError("create body exceeds 96 KiB")
        return self


class InstallationExecutionRequestLinkageV1(_Closed):
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


class InstallationExecutionRequestV1(_Closed):
    schema: Literal["installation-execution-request-v1"] = (
        "installation-execution-request-v1"
    )
    execution_request_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    operation: Literal["install-container"] = "install-container"
    mode: Literal["record-only"] = "record-only"
    linkage: InstallationExecutionRequestLinkageV1
    statement: Literal[
        "operator_requested_future_execution_of_exact_validated_candidate"
    ] = "operator_requested_future_execution_of_exact_validated_candidate"
    execution_authorized: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    execution_request_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def bounded_record(self) -> InstallationExecutionRequestV1:
        if _instant(self.valid_until) <= _instant(self.recorded_at):
            raise ValueError("execution request has no validity window")
        if _instant(self.valid_until) > _instant(self.recorded_at) + timedelta(
            minutes=5
        ):
            raise ValueError("execution request exceeds five-minute lifetime")
        if len(_canonical(self.model_dump(mode="json"))) > MAX_RECORD_BYTES:
            raise ValueError("execution request exceeds 64 KiB")
        return self


ExecutionRequestState = Literal["recorded", "expired"]


InstallationExecutionRequestErrorCode = Literal[
    "malformed",
    "not_found",
    "not_current",
    "ownership_mismatch",
    "proof_mismatch",
    "evidence_rejected",
    "replay_conflict",
    "quota_exceeded",
    "unavailable",
]


class InstallationExecutionRequestErrorV1(_Closed):
    schema: Literal["installation-execution-request-error-v1"] = (
        "installation-execution-request-error-v1"
    )
    error_code: InstallationExecutionRequestErrorCode
    correlation_id: Annotated[
        str,
        AfterValidator(
            lambda value: _ascii_match(value, _CORRELATION, "invalid correlation ID")
        ),
    ]
    execution_request_id: CanonicalUuid4 | None = None
    execution_request_fingerprint: FingerprintV1 | None = None
    redacted: Literal[True] = True


class InstallationExecutionRequestIdempotencyV1(_Closed):
    """Closed reservation identity; the key itself is never durable evidence."""

    owner_id: OwnerId
    operation: Literal["create-installation-execution-request"] = (
        "create-installation-execution-request"
    )
    key: Annotated[str, AfterValidator(lambda value: _visible_ascii(value, 128))]
    create_fingerprint: FingerprintV1


class InstallationExecutionRequestResultV1(_Closed):
    disposition: Literal["created", "exact_replay", "unavailable"]
    request: InstallationExecutionRequestV1 | None
    error: InstallationExecutionRequestErrorV1 | None

    @model_validator(mode="after")
    def exact_result(self) -> InstallationExecutionRequestResultV1:
        success = self.disposition in ("created", "exact_replay")
        if success != (self.request is not None and self.error is None):
            raise ValueError("result disposition and value disagree")
        if not success and (
            self.request is not None
            or self.error is None
            or self.error.error_code != "unavailable"
        ):
            raise ValueError("unavailable result must contain only unavailable error")
        return self


def build_execution_request(
    *,
    owner_id: str,
    execution_request_id: str,
    recorded_at: str,
    envelope: InstallationCandidateRecordEnvelopeV1,
    approval_intent: InstallationApprovalIntentV1,
    create: InstallationExecutionRequestCreateV1,
) -> InstallationExecutionRequestV1:
    """Purely validate the injected three-release chain and build inert evidence."""
    exact_envelope = InstallationCandidateRecordEnvelopeV1.model_validate(
        envelope.model_dump(mode="python")
    )
    exact_intent = InstallationApprovalIntentV1.model_validate(
        approval_intent.model_dump(mode="python")
    )
    exact_create = InstallationExecutionRequestCreateV1.model_validate(
        create.model_dump(mode="python")
    )
    _visible_ascii(owner_id, 200)
    now = _instant(recorded_at)
    if exact_envelope.owner_id != owner_id or exact_intent.operator_id != owner_id:
        raise ValueError("ownership mismatch")
    if candidate_record_state(exact_envelope, now=recorded_at) != "active":
        raise ValueError("candidate record is not current")
    record = exact_envelope.candidate_record
    subject = exact_intent.approved_subject
    expected_subject = (
        exact_envelope.candidate_record_id,
        exact_envelope.envelope_fingerprint,
        exact_envelope.admission_fingerprint,
        record.record_fingerprint,
    )
    if (
        subject.candidate_record_id,
        subject.candidate_envelope_fingerprint,
        subject.admission_fingerprint,
        subject.candidate_record_fingerprint,
    ) != expected_subject:
        raise ValueError("approval subject mismatch")
    if (
        exact_create.candidate_record_id != exact_envelope.candidate_record_id
        or exact_create.approval_intent_id != exact_intent.approval_intent_id
    ):
        raise ValueError("create linkage mismatch")
    request, validation = exact_create.agent_request, exact_create.agent_validation
    expected_proof = (
        exact_envelope.candidate_record_id,
        exact_envelope.envelope_fingerprint,
        exact_envelope.admission_fingerprint,
        record.record_fingerprint,
        exact_intent.approval_intent_id,
        exact_intent.intent_fingerprint,
    )
    proof = request.approval
    actual_proof = (
        proof.candidate_record_id,
        proof.candidate_envelope_fingerprint.value,
        proof.admission_fingerprint.value,
        proof.candidate_record_fingerprint.value,
        proof.approval_intent_id,
        proof.approval_intent_fingerprint.value,
    )
    if actual_proof != expected_proof or validation.evidence.approval != proof:
        raise ValueError("Agent approval proof mismatch")
    if (
        request.subject.destination_fingerprint
        != record.current_destination_fingerprint
        or validation.evidence.subject != request.subject
    ):
        raise ValueError("destination linkage mismatch")
    if request.artifact.source_plan_fingerprint.value != record.plan_fingerprint:
        raise ValueError("source plan mismatch")
    _validate_agent_pair(request, validation)
    if not (
        _instant(request.issued_at)
        <= _instant(validation.validated_at)
        < _instant(request.expires_at)
    ):
        raise ValueError("Agent validation is outside request window")
    validated = _instant(validation.validated_at)
    if (
        validated > now
        or now - validated > timedelta(seconds=60)
        or now >= _instant(request.expires_at)
    ):
        raise ValueError("Agent validation is not fresh")
    valid_until = min(
        _instant(record.valid_until),
        _instant(request.expires_at),
        now + timedelta(minutes=5),
    )
    linkage = InstallationExecutionRequestLinkageV1(
        candidate_record_id=exact_envelope.candidate_record_id,
        candidate_envelope_fingerprint=_wrap(exact_envelope.envelope_fingerprint),
        admission_fingerprint=_wrap(exact_envelope.admission_fingerprint),
        candidate_record_fingerprint=_wrap(record.record_fingerprint),
        approval_intent_id=exact_intent.approval_intent_id,
        approval_intent_fingerprint=_wrap(exact_intent.intent_fingerprint),
        agent_request_id=request.request_id,
        agent_request_fingerprint=request.request_fingerprint,
        agent_validation_fingerprint=validation.validation_fingerprint,
        agent_evidence_fingerprint=validation.evidence.evidence_fingerprint,
        destination_fingerprint=request.subject.destination_fingerprint,
        source_plan_fingerprint=request.artifact.source_plan_fingerprint,
        artifact_policy_fingerprint=validation.evidence.runtime_limit_policy_fingerprint,
    )
    raw: dict[str, Any] = {
        "schema": "installation-execution-request-v1",
        "execution_request_id": execution_request_id,
        "recorded_at": recorded_at,
        "valid_until": _format(valid_until),
        "operation": "install-container",
        "mode": "record-only",
        "linkage": linkage.model_dump(mode="json"),
        "statement": "operator_requested_future_execution_of_exact_validated_candidate",
        "execution_authorized": False,
        "dispatch_allowed": False,
        "agent_invocation_allowed": False,
        "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["execution_request_fingerprint"] = execution_request_fingerprint(
        owner_id=owner_id, record=raw
    )
    return InstallationExecutionRequestV1.model_validate(raw)


def _validate_agent_pair(
    request: AgentInstallContainerRequestV1,
    validation: AgentInstallContainerValidationV1,
) -> None:
    evidence = validation.evidence
    if validation.status != "valid_but_unsupported" or validation.reason_codes:
        raise ValueError("Agent evidence was rejected")
    if (
        validation.request_id != request.request_id
        or validation.request_fingerprint != request.request_fingerprint
    ):
        raise ValueError("Agent request identity mismatch")
    artifact = request.artifact
    if (
        evidence.artifact_kind,
        evidence.source_plan_fingerprint,
        evidence.source_repository_path,
        evidence.source_service,
        evidence.source_content_digest,
        evidence.image_digest,
    ) != (
        artifact.kind,
        artifact.source_plan_fingerprint,
        artifact.source_repository_path,
        artifact.source_service,
        artifact.source_content_digest,
        artifact.image_digest,
    ):
        raise ValueError("Agent artifact evidence mismatch")
    expected_policy = _runtime_policy_fingerprint(artifact, request.limits)
    if evidence.runtime_limit_policy_fingerprint != expected_policy:
        raise ValueError("Agent policy fingerprint mismatch")


def execution_request_state(
    request: InstallationExecutionRequestV1, *, now: str
) -> ExecutionRequestState:
    exact = InstallationExecutionRequestV1.model_validate(
        request.model_dump(mode="python")
    )
    instant = _instant(now)
    if instant < _instant(exact.recorded_at):
        raise ValueError("lifecycle instant precedes recording")
    return "recorded" if instant < _instant(exact.valid_until) else "expired"


def execution_request_fingerprint(
    *, owner_id: str, record: InstallationExecutionRequestV1 | dict[str, Any]
) -> FingerprintV1:
    raw = (
        record.model_dump(mode="json")
        if isinstance(record, BaseModel)
        else dict(record)
    )
    raw.pop("execution_request_fingerprint", None)
    return _fingerprint(
        "atlas:installation-execution-request:v1", {"owner_id": owner_id, "record": raw}
    )


def create_fingerprint(create: InstallationExecutionRequestCreateV1) -> FingerprintV1:
    return _fingerprint(
        "atlas:installation-execution-request-create:v1", create.model_dump(mode="json")
    )


def parse_create_json(payload: bytes | str) -> InstallationExecutionRequestCreateV1:
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
        return InstallationExecutionRequestCreateV1.model_validate(value)
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


def _runtime_policy_fingerprint(
    artifact: InstallContainerArtifactV1, limits: InstallContainerLimitsV1
) -> FingerprintV1:
    excluded = {
        "source_plan_fingerprint",
        "source_repository_path",
        "source_service",
        "source_content_digest",
        "image",
        "container_name",
    }
    policy = {
        key: value
        for key, value in artifact.model_dump(mode="json").items()
        if key not in excluded
    }
    return _fingerprint(
        "atlas:agent-install-container-runtime-limit-policy:v1",
        {"artifact_policy": policy, "limits": limits.model_dump(mode="json")},
    )


def _status_reasons(status: str, reasons: tuple[AgentReasonCode, ...]) -> None:
    if (
        len(reasons) > 32
        or len(set(reasons)) != len(reasons)
        or tuple(sorted(reasons, key=_REASON_ORDER.__getitem__)) != reasons
    ):
        raise ValueError("Agent reasons are not closed and ordered")
    if (status == "valid_but_unsupported") != (not reasons):
        raise ValueError("Agent status and reasons disagree")


def _wrap(value: str) -> FingerprintV1:
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=value
    )


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _format(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _visible_ascii(value: str, maximum: int) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value.encode()) <= maximum
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("visible ASCII value is out of bounds")
    return value


def _normalize_oci_repository(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value) <= 512
        or any(character.isspace() or ord(character) < 32 for character in value)
        or any(token in value for token in ("://", "@", "?", "#", "%"))
    ):
        raise ValueError("invalid OCI repository")
    slash = value.rfind("/")
    colon = value.rfind(":")
    if colon > slash:
        raise ValueError("mutable OCI tag is prohibited")
    parts = value.split("/")
    if any(not part for part in parts):
        raise ValueError("invalid OCI repository")
    first = parts[0]
    if "." not in first and ":" not in first and first != "localhost":
        parts.insert(0, "docker.io")
    registry = parts[0].lower()
    host, separator, port = registry.partition(":")
    if separator and (not port.isdecimal() or not 1 <= int(port) <= 65535):
        raise ValueError("invalid OCI registry port")
    if host != "localhost" and (
        len(host) > 253
        or any(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
            for label in host.split(".")
        )
    ):
        raise ValueError("invalid OCI registry")
    repositories = parts[1:]
    if registry == "docker.io" and len(repositories) == 1:
        repositories.insert(0, "library")
    if any(
        re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", part) is None
        for part in repositories
    ):
        raise ValueError("invalid OCI repository")
    return "/".join([registry, *repositories])
