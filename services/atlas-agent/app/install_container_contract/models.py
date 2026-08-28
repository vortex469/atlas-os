"""Pure models and identities for the frozen install-container v1 contract.

This module deliberately has no service, transport, persistence, or runtime
dependencies.  A value accepted here is validation input, never authority to
dispatch or execute work.
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

MAX_REQUEST_BYTES = 32 * 1024

_ID = re.compile(r"[a-z0-9][a-z0-9._:-]*")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC_SECOND = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_REPO_PATH = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*\.(?:yaml|yml)"
)
_CONTAINER_NAME = re.compile(r"atlas-[0-9a-f]{16}")
_CORRELATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class StrictContractError(ValueError):
    """A wire value cannot be represented by the frozen closed contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _ascii(value: str) -> None:
    if not value.isascii():
        raise ValueError("ASCII required")


def _bounded_id(value: str, maximum: int) -> str:
    _ascii(value)
    if not 1 <= len(value) <= maximum or _ID.fullmatch(value) is None:
        raise ValueError("invalid bounded ID")
    return value


def _id64(value: str) -> str:
    return _bounded_id(value, 64)


def _id255(value: str) -> str:
    return _bounded_id(value, 255)


def _lowerhex64(value: str) -> str:
    _ascii(value)
    if _HEX_64.fullmatch(value) is None:
        raise ValueError("invalid lowerhex[64]")
    return value


def _digest(value: str) -> str:
    _ascii(value)
    if _DIGEST.fullmatch(value) is None:
        raise ValueError("invalid Sha256Digest")
    return value


def _uuid4(value: str) -> str:
    _ascii(value)
    if _UUID4.fullmatch(value) is None:
        raise ValueError("invalid canonical UUIDv4")
    return value


def _utc_second(value: str) -> str:
    _ascii(value)
    if _UTC_SECOND.fullmatch(value) is None:
        raise ValueError("invalid UtcSecond")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("invalid UtcSecond") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("invalid UtcSecond")
    return value


def _repo_path(value: str) -> str:
    _ascii(value)
    if (
        not 1 <= len(value) <= 512
        or len(value.split("/")) > 32
        or _REPO_PATH.fullmatch(value) is None
    ):
        raise ValueError("invalid RepoPath")
    return value


def _oci_repository(value: str) -> str:
    normalized, digest, mutable = _normalize_oci_reference(value)
    if (normalized, digest, mutable) != (value, None, False):
        raise ValueError("OCI repository must be canonical")
    return value


def _normalize_oci_reference(value: str) -> tuple[str, str | None, bool]:
    """The exact v0.16 RepoPath companion OCI normalization rules."""
    _ascii(value)
    if (
        not 1 <= len(value) <= 512
        or any(character.isspace() or ord(character) < 32 for character in value)
        or any(token in value for token in ("://", "@/", "?", "#", "%"))
    ):
        raise ValueError("invalid OCI reference")
    digest = None
    if "@" in value:
        if value.count("@") != 1:
            raise ValueError("invalid OCI reference")
        value, digest = value.split("@")
        _digest(digest)
    slash = value.rfind("/")
    colon = value.rfind(":")
    mutable = colon > slash
    if mutable:
        tag = value[colon + 1 :]
        if not tag or re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag) is None:
            raise ValueError("invalid OCI tag")
        value = value[:colon]
    parts = value.split("/")
    if any(not part for part in parts):
        raise ValueError("invalid OCI reference")
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
    result = "/".join([registry, *repositories])
    if len(result) > 512:
        raise ValueError("invalid OCI reference")
    return result, digest, mutable


def _container_name(value: str) -> str:
    _ascii(value)
    if _CONTAINER_NAME.fullmatch(value) is None:
        raise ValueError("invalid container name")
    return value


def _correlation_id(value: str) -> str:
    _ascii(value)
    if _CORRELATION_ID.fullmatch(value) is None:
        raise ValueError("invalid correlation ID")
    return value


Id64 = Annotated[str, AfterValidator(_id64)]
Id255 = Annotated[str, AfterValidator(_id255)]
LowerHex64 = Annotated[str, AfterValidator(_lowerhex64)]
Sha256Digest = Annotated[str, AfterValidator(_digest)]
CanonicalUuid4 = Annotated[str, AfterValidator(_uuid4)]
UtcSecond = Annotated[str, AfterValidator(_utc_second)]
RepoPath = Annotated[str, AfterValidator(_repo_path)]
OciRepository = Annotated[str, AfterValidator(_oci_repository)]
ContainerName = Annotated[str, AfterValidator(_container_name)]
CorrelationId = Annotated[str, AfterValidator(_correlation_id)]


def _json_array(value: object) -> object:
    # JSON has arrays, while the in-memory contract uses immutable tuples.
    return tuple(value) if isinstance(value, list) else value


EmptyArray = Annotated[tuple[()], BeforeValidator(_json_array)]
CapabilityDropArray = Annotated[
    tuple[Literal["ALL"], ...], BeforeValidator(_json_array)
]


class FingerprintV1(ContractModel):
    algorithm: Literal["sha256"]
    canonicalization: Literal["atlas-jcs-nfc-v1"]
    value: LowerHex64


class InstallationSubjectV1(ContractModel):
    provider: Literal["proxmox"]
    resource_type: Literal["qemu"]
    placement_kind: Literal["existing-guest"]
    resource_id: Id64
    destination_fingerprint: LowerHex64


class ApprovedCandidateProofV1(ContractModel):
    candidate_record_id: CanonicalUuid4
    candidate_envelope_fingerprint: FingerprintV1
    admission_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    approval_intent_id: CanonicalUuid4
    approval_intent_fingerprint: FingerprintV1


class TmpfsV1(ContractModel):
    container_path: Literal["/tmp"]
    size_bytes: Literal["67108864"]
    options: Annotated[
        tuple[Literal["nodev", "noexec", "nosuid"], ...], BeforeValidator(_json_array)
    ]

    @model_validator(mode="after")
    def exact_options(self) -> TmpfsV1:
        if self.options != ("nodev", "noexec", "nosuid"):
            raise ValueError("tmpfs options must be the exact closed policy")
        return self


class InstallContainerArtifactV1(ContractModel):
    kind: Literal["single-oci-container-v1"]
    source_plan_fingerprint: FingerprintV1
    source_repository_path: RepoPath
    source_service: Id255
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
    capabilities_drop: CapabilityDropArray
    no_new_privileges: Literal[True]
    tmpfs: Annotated[tuple[TmpfsV1, ...], BeforeValidator(_json_array)]
    restart_policy: Literal["no"]

    @model_validator(mode="after")
    def exact_boundary(self) -> InstallContainerArtifactV1:
        if self.capabilities_drop != ("ALL",):
            raise ValueError("capabilities_drop must contain only ALL")
        if len(self.tmpfs) != 1:
            raise ValueError("exactly one bounded tmpfs is required")
        repository, separator, digest = self.image.partition("@")
        if not separator or "@" in digest:
            raise ValueError("image must be digest-pinned")
        _oci_repository(repository)
        _digest(digest)
        return self

    @property
    def image_digest(self) -> str:
        return self.image.partition("@")[2]


class InstallContainerLimitsV1(ContractModel):
    cpu_count: Literal["1"]
    memory_bytes: Literal["536870912"]
    pids: Literal["128"]
    tmpfs_bytes: Literal["67108864"]


class AgentInstallContainerRequestV1(ContractModel):
    schema: Literal["agent-install-container-request-v1"]
    operation: Literal["install-container"]
    mode: Literal["validate-only"]
    request_id: CanonicalUuid4
    issued_at: UtcSecond
    expires_at: UtcSecond
    subject: InstallationSubjectV1
    approval: ApprovedCandidateProofV1
    artifact: InstallContainerArtifactV1
    limits: InstallContainerLimitsV1
    request_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_request(self) -> AgentInstallContainerRequestV1:
        issued = datetime.strptime(self.issued_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        expires = datetime.strptime(self.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if expires != issued + timedelta(minutes=5):
            raise ValueError("request validity window must be exactly five minutes")
        if len(_canonical_json_value(self.model_dump(mode="json"))) > MAX_REQUEST_BYTES:
            raise ValueError("request exceeds 32 KiB")
        if self.request_fingerprint != request_fingerprint(self):
            raise ValueError("request fingerprint mismatch")
        return self


class ReasonCode(StrEnum):
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


_REASON_ORDER = {reason: index for index, reason in enumerate(ReasonCode)}


class AgentInstallContainerAuditEvidenceV1(ContractModel):
    evidence_schema: Literal["agent-install-container-audit-evidence-v1"]
    request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    approval: ApprovedCandidateProofV1
    subject: InstallationSubjectV1
    artifact_kind: Literal["single-oci-container-v1"]
    source_plan_fingerprint: FingerprintV1
    source_repository_path: RepoPath
    source_service: Id255
    source_content_digest: Sha256Digest
    image_digest: Sha256Digest
    runtime_limit_policy_fingerprint: FingerprintV1
    validated_at: UtcSecond
    status: Literal["valid_but_unsupported", "rejected"]
    reason_codes: tuple[ReasonCode, ...]
    execution_supported: Literal[False]
    dispatch_allowed: Literal[False]
    mutation_allowed: Literal[False]
    replay_allowed: Literal[False]
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_evidence(self) -> AgentInstallContainerAuditEvidenceV1:
        _validate_status_reasons(self.status, self.reason_codes)
        if len(self.reason_codes) > 32 or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason codes must be unique and bounded")
        if self.evidence_fingerprint != evidence_fingerprint(self):
            raise ValueError("evidence fingerprint mismatch")
        return self


class AgentInstallContainerValidationV1(ContractModel):
    schema: Literal["agent-install-container-validation-v1"]
    request_id: CanonicalUuid4
    request_fingerprint: FingerprintV1
    validated_at: UtcSecond
    status: Literal["valid_but_unsupported", "rejected"]
    reason_codes: tuple[ReasonCode, ...]
    execution_supported: Literal[False]
    dispatch_allowed: Literal[False]
    mutation_allowed: Literal[False]
    replay_allowed: Literal[False]
    evidence: AgentInstallContainerAuditEvidenceV1
    validation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_validation(self) -> AgentInstallContainerValidationV1:
        _validate_status_reasons(self.status, self.reason_codes)
        if len(self.reason_codes) > 32 or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason codes must be unique and bounded")
        for field in ("request_id", "request_fingerprint", "validated_at", "status", "reason_codes"):
            if getattr(self, field) != getattr(self.evidence, field):
                raise ValueError("validation and evidence mismatch")
        if self.validation_fingerprint != validation_fingerprint(self):
            raise ValueError("validation fingerprint mismatch")
        return self


class AgentInstallContainerErrorV1(ContractModel):
    """The complete sanitized error vocabulary safe for logs and metrics."""

    schema: Literal["agent-install-container-error-v1"]
    reason_code: ReasonCode
    request_id: CanonicalUuid4 | None
    request_fingerprint: FingerprintV1 | None
    correlation_id: CorrelationId
    redacted: Literal[True]


def _validate_status_reasons(status: str, reasons: tuple[ReasonCode, ...]) -> None:
    if (status == "valid_but_unsupported") != (not reasons):
        raise ValueError("valid_but_unsupported requires no reasons; rejected requires reasons")
    if tuple(sorted(reasons, key=_REASON_ORDER.__getitem__)) != reasons:
        raise ValueError("reason codes must follow first-applicable group order")


def _canonical_json_value(value: object) -> bytes:
    def validate(item: object) -> None:
        if isinstance(item, str):
            if item != unicodedata.normalize("NFC", item):
                raise ValueError("canonical strings must be NFC")
        elif isinstance(item, bool) or item is None:
            return
        elif isinstance(item, int | float):
            raise TypeError("JSON numbers are outside the restricted canonical domain")
        elif isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                validate(key)
                validate(child)
        elif isinstance(item, list | tuple):
            for child in item:
                validate(child)
        else:
            raise TypeError("value is outside the restricted canonical domain")

    validate(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def canonical_json(value: ContractModel) -> bytes:
    if not isinstance(value, ContractModel):
        raise TypeError("canonicalization requires a closed ContractModel")
    return _canonical_json_value(value.model_dump(mode="json"))


def _fingerprint(domain: str, value: object) -> FingerprintV1:
    if not domain.isascii() or "\0" in domain:
        raise ValueError("invalid fingerprint domain")
    digest = hashlib.sha256(domain.encode() + b"\0" + _canonical_json_value(value)).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest)


def request_fingerprint(request: AgentInstallContainerRequestV1 | dict[str, Any]) -> FingerprintV1:
    raw = request.model_dump(mode="json") if isinstance(request, BaseModel) else dict(request)
    raw.pop("request_fingerprint", None)
    return _fingerprint("atlas:agent-install-container-request:v1", raw)


def runtime_limit_policy_fingerprint(
    artifact: InstallContainerArtifactV1, limits: InstallContainerLimitsV1
) -> FingerprintV1:
    policy_fields = {
        key: value
        for key, value in artifact.model_dump(mode="json").items()
        if key not in {
            "source_plan_fingerprint", "source_repository_path", "source_service",
            "source_content_digest", "image", "container_name",
        }
    }
    return _fingerprint(
        "atlas:agent-install-container-runtime-limit-policy:v1",
        {"artifact_policy": policy_fields, "limits": limits.model_dump(mode="json")},
    )


def evidence_fingerprint(
    evidence: AgentInstallContainerAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    raw = evidence.model_dump(mode="json") if isinstance(evidence, BaseModel) else dict(evidence)
    raw.pop("evidence_fingerprint", None)
    return _fingerprint("atlas:agent-install-container-audit-evidence:v1", raw)


def validation_fingerprint(
    validation: AgentInstallContainerValidationV1 | dict[str, Any],
) -> FingerprintV1:
    raw = validation.model_dump(mode="json") if isinstance(validation, BaseModel) else dict(validation)
    raw.pop("validation_fingerprint", None)
    return _fingerprint("atlas:agent-install-container-validation:v1", raw)


def parse_request_json(payload: bytes | str) -> AgentInstallContainerRequestV1:
    """Parse a bounded JSON object while rejecting duplicate keys and trailing data."""
    encoded = payload.encode() if isinstance(payload, str) else payload
    if len(encoded) > MAX_REQUEST_BYTES:
        raise StrictContractError("contract_out_of_bounds")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StrictContractError("contract_unknown_field")
            result[key] = value
        return result

    try:
        decoded = json.loads(encoded.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except StrictContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StrictContractError("contract_malformed") from error
    if not isinstance(decoded, dict):
        raise StrictContractError("contract_malformed")
    try:
        return AgentInstallContainerRequestV1.model_validate(decoded)
    except Exception as error:
        raise StrictContractError("contract_malformed") from error
