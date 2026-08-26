"""Strict InstallationPlan v1 wire contract and identity primitives."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ContractError(ValueError):
    """A required input cannot be represented by the frozen contract."""


_ID = re.compile(r"[a-z0-9][a-z0-9._:-]*")
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HEX = re.compile(r"[0-9a-f]{64}")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_REPO_PATH = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*\.(?:yaml|yml)"
)
_FORBIDDEN = (
    set(range(0x20))
    | set(range(0x7F, 0xA0))
    | {0x2028, 0x2029, 0x061C, 0x200E, 0x200F}
    | set(range(0x202A, 0x202F))
    | set(range(0x2066, 0x206A))
)
_WHITE_SPACE = " \t\n\r\v\f\x85\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


def _ascii(value: str) -> None:
    if not value.isascii():
        raise ValueError("ASCII required")


def bounded_id(value: str, minimum: int = 1, maximum: int = 128) -> str:
    _ascii(value)
    if not minimum <= len(value) <= maximum or not _ID.fullmatch(value):
        raise ValueError("invalid bounded ID")
    return value


def _id64(value: str) -> str:
    return bounded_id(value, 1, 64)


def _id128(value: str) -> str:
    return bounded_id(value, 1, 128)


def _source(value: str) -> str:
    return bounded_id(value, 1, 256)


def _version(value: str) -> str:
    _ascii(value)
    match = _VERSION.fullmatch(value)
    if match is None or any(int(part) > 2147483647 for part in match.groups()):
        raise ValueError("invalid Version")
    return value


def version_components(value: str) -> tuple[int, int, int]:
    """Return the exact numeric components of a validated Version."""
    return tuple(int(part) for part in _version(value).split("."))  # type: ignore[return-value]


def _decimal(value: str) -> str:
    _ascii(value)
    if not 1 <= len(value) <= 32 or not _DECIMAL.fullmatch(value):
        raise ValueError("invalid DecimalString")
    return value


def _digest(value: str) -> str:
    _ascii(value)
    if not _DIGEST.fullmatch(value):
        raise ValueError("invalid Sha256Digest")
    return value


def _hex(value: str) -> str:
    _ascii(value)
    if not _HEX.fullmatch(value):
        raise ValueError("invalid lowerhex[64]")
    return value


def _utc(value: str) -> str:
    _ascii(value)
    if not _UTC.fullmatch(value):
        raise ValueError("invalid UtcSecond")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("invalid UtcSecond") from error
    rendered = (
        f"{parsed.year:04d}-{parsed.month:02d}-{parsed.day:02d}T"
        f"{parsed.hour:02d}:{parsed.minute:02d}:{parsed.second:02d}Z"
    )
    if rendered != value:
        raise ValueError("invalid UtcSecond")
    return value


def _repo_path(value: str) -> str:
    _ascii(value)
    if (
        not 1 <= len(value) <= 512
        or len(value.split("/")) > 32
        or not _REPO_PATH.fullmatch(value)
    ):
        raise ValueError("invalid RepoPath")
    return value


def plain_text(value: str, minimum: int = 1, maximum: int = 256) -> str:
    if (
        value != unicodedata.normalize("NFC", value)
        or not minimum <= len(value.encode("utf-8")) <= maximum
    ):
        raise ValueError("invalid PlainText")
    if value[0] in _WHITE_SPACE or value[-1] in _WHITE_SPACE:
        raise ValueError("invalid PlainText")
    for character in value:
        point = ord(character)
        if (
            point in _FORBIDDEN
            or 0xD800 <= point <= 0xDFFF
            or point & 0xFFFF in {0xFFFE, 0xFFFF}
            or 0xFDD0 <= point <= 0xFDEF
        ):
            raise ValueError("invalid PlainText")
    return value


Id64 = Annotated[str, AfterValidator(_id64)]
Id128 = Annotated[str, AfterValidator(_id128)]
SafeSourceId = Annotated[str, AfterValidator(_source)]
Version = Annotated[str, AfterValidator(_version)]
DecimalString = Annotated[str, AfterValidator(_decimal)]
Sha256Digest = Annotated[str, AfterValidator(_digest)]
LowerHex64 = Annotated[str, AfterValidator(_hex)]
UtcSecond = Annotated[str, AfterValidator(_utc)]
RepoPath = Annotated[str, AfterValidator(_repo_path)]
OciRepository = Annotated[
    str,
    AfterValidator(
        lambda value: (
            normalize_oci_reference(value)[0]
            if normalize_oci_reference(value) == (value, None, False)
            else (_ for _ in ()).throw(ValueError("repository must be canonical"))
        )
    ),
]
PlainText128 = Annotated[str, AfterValidator(lambda value: plain_text(value, 1, 128))]
PlainText256 = Annotated[str, AfterValidator(plain_text)]
SourceClass = Literal["curated", "registry_attested", "upstream_signed"]
ProvenanceSourceClass = Literal[
    "curated_catalog",
    "deployment_binding",
    "repository_observation",
    "image_release_evidence",
    "compatibility_evaluation",
    "prerequisite_source",
    "policy_evaluation",
]
ArtifactState = Literal["present", "missing", "invalid", "unsafe", "unknown"]
ArtifactReasonCode = Literal[
    "content_size",
    "non_utf8",
    "invalid_yaml",
    "ambiguous_service",
    "containment_escape",
    "symlink",
    "non_regular",
    "observation_unknown",
]
BlockerCode = Literal[
    "missing_deployment_binding",
    "missing_deployment_artifact",
    "invalid_deployment_artifact",
    "unsafe_deployment_artifact",
    "unknown_deployment_artifact",
    "missing_immutable_image_identity",
    "mutable_image_reference",
    "untrusted_evidence",
    "image_conflict",
    "image_mismatch",
    "unknown_image_state",
    "missing_accepted_evidence",
    "stale_evidence",
    "malformed_evidence",
    "provenance_conflict",
    "incompatible_application_environment",
    "unknown_compatibility",
    "missing_prerequisite",
    "missing_prerequisite_fact",
    "missing_target_identity",
    "required_operator_confirmation",
    "malformed_source_fact",
]

_RELATIONSHIP_RANK = {
    value: rank
    for rank, value in enumerate(
        ("depends_on", "provides", "consumes", "requires", "integrates_with",
         "conflicts_with", "runs_on", "deployed_by", "compatible_with",
         "incompatible_with")
    )
}
_SOURCE_CLASS_RANK = {v: i for i, v in enumerate(("curated", "registry_attested", "upstream_signed", "unknown"))}
_PROVENANCE_RANK = {v: i for i, v in enumerate((
    "curated_catalog", "deployment_binding", "repository_observation",
    "image_release_evidence", "compatibility_evaluation", "prerequisite_source",
    "policy_evaluation",
))}
_BLOCKER_RANK = {v: i for i, v in enumerate((
    "missing_deployment_binding", "missing_deployment_artifact",
    "invalid_deployment_artifact", "unsafe_deployment_artifact",
    "unknown_deployment_artifact", "missing_immutable_image_identity",
    "mutable_image_reference", "untrusted_evidence", "image_conflict",
    "image_mismatch", "unknown_image_state", "missing_accepted_evidence",
    "stale_evidence", "malformed_evidence", "provenance_conflict",
    "incompatible_application_environment", "unknown_compatibility",
    "missing_prerequisite", "missing_prerequisite_fact", "missing_target_identity",
    "required_operator_confirmation", "malformed_source_fact",
))}
_RISK_RANK = {"evidence_approaching_expiry": 0, "compatibility_warning": 1}
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_MISSING_RANK = {v: i for i, v in enumerate((
    "deployment_binding", "deployment_artifact", "immutable_image_identity",
    "accepted_evidence", "prerequisite_fact", "target_identity",
    "compatibility_fact", "source_fact",
))}
_ABSENCE_RANK = {v: i for i, v in enumerate((
    "deployment_binding", "deployment_artifact", "evidence_record",
    "compatibility_fact", "prerequisite_fact",
))}
_CONFLICT_RANK = {v: i for i, v in enumerate((
    "image_claim", "provenance_identity", "immutable_identity",
))}
_DISPOSITION_RANK = {v: i for i, v in enumerate((
    "accepted", "missing", "untrusted", "unsupported", "malformed",
    "unavailable", "conflicted", "mismatched",
))}
_ELIGIBILITY_RANK = {"eligible": 0, "ineligible": 1}
_EVIDENCE_REASON_RANK = {v: i for i, v in enumerate((
    "accepted_fresh", "accepted_stale", "record_missing",
    "source_class_untrusted", "source_class_unsupported", "record_malformed",
    "timestamp_malformed", "digest_or_identity_malformed",
    "accepted_claim_conflict", "immutable_identity_conflict",
    "release_identity_mismatch", "source_unavailable",
))}
_COMPAT_RESULT_RANK = {v: i for i, v in enumerate((
    "compatible", "compatible_with_warnings", "incompatible", "unknown",
))}
_COMPAT_REASON_RANK = {v: i for i, v in enumerate((
    "target_free_catalog_compatible", "target_free_catalog_warning",
    "target_free_catalog_incompatible", "target_required",
    "compatibility_fact_missing", "compatibility_fact_malformed",
))}
_PREREQUISITE_KIND_RANK = {v: i for i, v in enumerate((
    "storage", "network", "platform", "application", "operator",
))}
_PREREQUISITE_STATE_RANK = {v: i for i, v in enumerate((
    "satisfied", "missing", "unknown",
))}
_ASSUMPTION_KIND_RANK = {v: i for i, v in enumerate((
    "catalog", "environment", "operator",
))}
_CONFIRMATION_RANK = {v: i for i, v in enumerate((
    "accept_assumption", "confirm_prerequisite", "confirm_risk",
))}
_FRESHNESS_RANK = {"fresh": 0, "stale": 1}


def _ordered_unique(keys: tuple[tuple[object, ...], ...], name: str) -> None:
    if tuple(sorted(keys)) != keys or len(set(keys)) != len(keys):
        raise ValueError(f"{name} must be sorted and unique")


def _nullable(value: str | None) -> tuple[int, str]:
    return (0, "") if value is None else (1, value)


def canonical_json(value: ContractModel) -> bytes:
    """Serialize only an already validated, closed contract object."""
    if not isinstance(value, ContractModel):
        raise TypeError("canonicalization requires a closed ContractModel")
    raw = value.model_dump(mode="json")

    def validate(item: object) -> None:
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("non-finite JSON number")
            raise TypeError("floats are outside the restricted canonical domain")
        if isinstance(item, str) and item != unicodedata.normalize("NFC", item):
            raise ValueError("canonical strings must be NFC")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                validate(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                validate(child)

    validate(raw)
    return json.dumps(
        raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def compound_hash(domain: str, value: ContractModel) -> str:
    if not domain.isascii() or "\0" in domain:
        raise ValueError("invalid identity domain")
    return hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()


def content_digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def normalize_oci_reference(value: str) -> tuple[str, str | None, bool]:
    _ascii(value)
    if (
        not 1 <= len(value) <= 512
        or any(c.isspace() or ord(c) < 32 for c in value)
        or any(x in value for x in ("://", "@/", "?", "#", "%"))
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
        if not tag or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag):
            raise ValueError("invalid OCI tag")
        value = value[:colon]
    parts = value.split("/")
    if any(not part for part in parts):
        raise ValueError("invalid OCI reference")
    first = parts[0]
    if "." not in first and ":" not in first and first != "localhost":
        parts.insert(0, "docker.io")
    registry = parts[0].lower()
    host, sep, port = registry.partition(":")
    if sep and (not port.isdecimal() or not 1 <= int(port) <= 65535):
        raise ValueError("invalid OCI port")
    if host != "localhost" and (
        len(host) > 253
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        )
    ):
        raise ValueError("invalid OCI registry")
    repos = parts[1:]
    if registry == "docker.io" and len(repos) == 1:
        repos.insert(0, "library")
    if any(not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", part) for part in repos):
        raise ValueError("invalid OCI repository")
    result = "/".join([registry, *repos])
    if len(result) > 512:
        raise ValueError("invalid OCI reference")
    return result, digest, mutable


class Fingerprint(ContractModel):
    algorithm: Literal["sha256"] = "sha256"
    canonicalization: Literal["atlas-jcs-nfc-v1"] = "atlas-jcs-nfc-v1"
    value: LowerHex64


class Application(ContractModel):
    item_id: Id64
    catalog_entry_id: Id64
    display_name: PlainText128
    release_version: Version | None


class DeploymentArtifact(ContractModel):
    state: ArtifactState
    kind: Literal["docker-compose"] = "docker-compose"
    repository_path: RepoPath | None
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))] | None
    content_digest: Sha256Digest | None

    @model_validator(mode="after")
    def relation(self) -> DeploymentArtifact:
        if self.state == "present":
            valid = all(
                value is not None
                for value in (self.repository_path, self.service, self.content_digest)
            )
        elif self.state in {"missing", "invalid", "unsafe"}:
            valid = (
                self.repository_path is not None
                and self.service is not None
                and self.content_digest is None
            )
        else:
            valid = (
                self.content_digest is None
                and (self.repository_path is None) == (self.service is None)
            )
        if not valid:
            raise ValueError("invalid deployment artifact relation")
        return self


class Image(ContractModel):
    state: Literal[
        "grounded",
        "missing",
        "mutable",
        "untrusted",
        "conflicted",
        "mismatched",
        "unknown",
    ]
    reference: OciRepository | None
    digest: Sha256Digest | None
    release_version: Version | None

    @model_validator(mode="after")
    def relation(self) -> Image:
        if self.state == "grounded":
            valid = all(
                value is not None
                for value in (self.reference, self.digest, self.release_version)
            )
        elif self.state == "conflicted":
            valid = (
                self.reference is None
                and self.digest is None
                and self.release_version is not None
            )
        elif self.state == "missing":
            valid = self.digest is None
        elif self.state == "mutable":
            valid = self.reference is not None and self.digest is None
        elif self.state == "untrusted":
            valid = all(
                value is not None
                for value in (self.reference, self.digest, self.release_version)
            )
        elif self.state in {"mismatched", "unknown"}:
            valid = (self.reference is None) == (self.digest is None)
        else:
            valid = True
        if not valid:
            raise ValueError("invalid image relation")
        return self


class Evidence(ContractModel):
    evidence_id: LowerHex64
    source_class: SourceClass
    source_id: SafeSourceId
    subject: Id128
    claim: Id128
    immutable_identity: LowerHex64
    observed_at: None = None
    attested_at: UtcSecond
    freshness_window_seconds: Annotated[StrictInt, Field(ge=60, le=31536000)]
    trust: Literal["accepted"] = "accepted"


class Provenance(ContractModel):
    claim: Id128
    source_class: ProvenanceSourceClass
    source_id: SafeSourceId
    immutable_identity: LowerHex64
    observed_at: UtcSecond | None
    attested_at: UtcSecond | None


class Compatibility(ContractModel):
    environment: Literal["item-scoped"] = "item-scoped"
    result: Literal["compatible", "compatible_with_warnings", "incompatible", "unknown"]
    reason_code: Literal[
        "target_free_catalog_compatible",
        "target_free_catalog_warning",
        "target_free_catalog_incompatible",
        "target_required",
        "compatibility_fact_missing",
        "compatibility_fact_malformed",
    ]

    @model_validator(mode="after")
    def relation(self) -> Compatibility:
        allowed = {
            ("compatible", "target_free_catalog_compatible"),
            ("compatible_with_warnings", "target_free_catalog_warning"),
            ("incompatible", "target_free_catalog_incompatible"),
            ("unknown", "target_required"),
            ("unknown", "compatibility_fact_missing"),
            ("unknown", "compatibility_fact_malformed"),
        }
        if (self.result, self.reason_code) not in allowed:
            raise ValueError("invalid compatibility relation")
        return self


class Prerequisite(ContractModel):
    prerequisite_id: Id64
    kind: Literal["storage", "network", "platform", "application", "operator"]
    state: Literal["satisfied", "missing", "unknown"]
    description: PlainText256


class Relationship(ContractModel):
    kind: Literal[
        "depends_on",
        "provides",
        "consumes",
        "requires",
        "integrates_with",
        "conflicts_with",
        "runs_on",
        "deployed_by",
        "compatible_with",
        "incompatible_with",
    ]
    item_id: Id64
    required: StrictBool
    minimum_version: Version | None
    maximum_version: Version | None

    @model_validator(mode="after")
    def bounds(self) -> Relationship:
        if (
            self.minimum_version is not None
            and self.maximum_version is not None
            and version_components(self.minimum_version)
            > version_components(self.maximum_version)
        ):
            raise ValueError("minimum version exceeds maximum version")
        return self


class Assumption(ContractModel):
    assumption_id: Id64
    kind: Literal["catalog", "environment", "operator"]
    statement: PlainText256


class Blocker(ContractModel):
    code: BlockerCode
    subject: Id128


class Risk(ContractModel):
    code: Literal["evidence_approaching_expiry", "compatibility_warning"]
    severity: Literal["low", "medium", "high", "critical"]
    subject: Id128


class MissingFact(ContractModel):
    code: Literal[
        "deployment_binding",
        "deployment_artifact",
        "immutable_image_identity",
        "accepted_evidence",
        "prerequisite_fact",
        "target_identity",
        "compatibility_fact",
        "source_fact",
    ]
    subject: Id128


class Confirmation(ContractModel):
    code: Literal["accept_assumption", "confirm_prerequisite", "confirm_risk"]
    subject: Id128
    prompt: PlainText256


class InstallationPlan(ContractModel):
    schema_version: Literal["installation-plan-v1"] = "installation-plan-v1"
    fingerprint: Fingerprint
    application: Application
    status: Literal[
        "conflicted",
        "missing_deployment_artifact",
        "incompatible",
        "stale_evidence",
        "insufficient_information",
        "plan_ready_for_review",
    ]
    deployment_artifact: DeploymentArtifact
    image: Image
    accepted_evidence: tuple[Evidence, ...] = Field(max_length=32)
    provenance: tuple[Provenance, ...] = Field(min_length=1, max_length=256)
    compatibility: tuple[Compatibility, ...] = Field(min_length=1, max_length=1)
    prerequisites: tuple[Prerequisite, ...] = Field(max_length=64)
    relationships: tuple[Relationship, ...] = Field(max_length=64)
    assumptions: tuple[Assumption, ...] = Field(max_length=32)
    blockers: tuple[Blocker, ...] = Field(max_length=64)
    risks: tuple[Risk, ...] = Field(max_length=32)
    missing_facts: tuple[MissingFact, ...] = Field(max_length=64)
    required_operator_confirmations: tuple[Confirmation, ...] = Field(max_length=32)

    @model_validator(mode="after")
    def normalized_arrays(self) -> InstallationPlan:
        arrays = (
            (tuple((e.subject, e.claim, _SOURCE_CLASS_RANK[e.source_class], e.source_id,
                    e.immutable_identity, e.evidence_id, e.attested_at) for e in self.accepted_evidence), "evidence"),
            (tuple((p.claim, _PROVENANCE_RANK[p.source_class], p.source_id,
                    p.immutable_identity, _nullable(p.observed_at), _nullable(p.attested_at)) for p in self.provenance), "provenance"),
            (tuple((p.prerequisite_id, p.kind, p.state) for p in self.prerequisites), "prerequisites"),
            (tuple((_RELATIONSHIP_RANK[r.kind], r.item_id, r.required,
                    _nullable(r.minimum_version), _nullable(r.maximum_version)) for r in self.relationships), "relationships"),
            (tuple((a.assumption_id, a.kind) for a in self.assumptions), "assumptions"),
            (tuple((_BLOCKER_RANK[b.code], b.subject) for b in self.blockers), "blockers"),
            (tuple((_SEVERITY_RANK[r.severity], _RISK_RANK[r.code], r.subject) for r in self.risks), "risks"),
            (tuple((_MISSING_RANK[m.code], m.subject) for m in self.missing_facts), "missing facts"),
            (tuple((c.code, c.subject) for c in self.required_operator_confirmations), "confirmations"),
        )
        for keys, name in arrays:
            _ordered_unique(keys, name)
        blocker_codes = {blocker.code for blocker in self.blockers}
        if blocker_codes & {"provenance_conflict", "image_conflict"}:
            expected_status = "conflicted"
        elif "missing_deployment_artifact" in blocker_codes:
            expected_status = "missing_deployment_artifact"
        elif "incompatible_application_environment" in blocker_codes:
            expected_status = "incompatible"
        elif "stale_evidence" in blocker_codes:
            expected_status = "stale_evidence"
        elif blocker_codes:
            expected_status = "insufficient_information"
        else:
            expected_status = "plan_ready_for_review"
        if self.status != expected_status:
            raise ValueError("plan status does not match blockers")

        provenance_rows = {
            (
                row.source_class,
                row.claim,
                row.source_id,
                row.immutable_identity,
                row.attested_at,
            )
            for row in self.provenance
        }
        for evidence in self.accepted_evidence:
            if (
                "image_release_evidence",
                evidence.claim,
                evidence.source_id,
                evidence.immutable_identity,
                evidence.attested_at,
            ) not in provenance_rows:
                raise ValueError("accepted evidence lacks provenance")
        # Evidence intentionally has no public image/release values, so the
        # stronger value match remains enforced by FingerprintInputV1.
        if self.image.state == "grounded" and not self.accepted_evidence:
            raise ValueError("grounded image lacks accepted evidence")
        consequences = {
            "missing": ("missing_immutable_image_identity", "immutable_image_identity"),
            "mutable": ("mutable_image_reference", "immutable_image_identity"),
            "untrusted": ("untrusted_evidence", "accepted_evidence"),
            "conflicted": ("image_conflict", "source_fact"),
            "mismatched": ("image_mismatch", "accepted_evidence"),
            "unknown": ("unknown_image_state", "immutable_image_identity"),
        }
        image_subject = self.application.item_id
        if self.image.state in consequences:
            blocker, missing_fact = consequences[self.image.state]
            blocker_subject = (
                image_subject
                if self.image.state in {"missing", "mutable", "conflicted", "unknown"}
                else None
            )
            if not any(
                row.code == blocker
                and (blocker_subject is None or row.subject == blocker_subject)
                for row in self.blockers
            ) or not any(
                fact.code == missing_fact
                and (blocker_subject is None or fact.subject == blocker_subject)
                for fact in self.missing_facts
            ):
                raise ValueError("image state lacks mandatory consequence")
        deterministic_image_blockers = {
            "missing_immutable_image_identity": "missing",
            "mutable_image_reference": "mutable",
            "image_conflict": "conflicted",
            "image_mismatch": "mismatched",
            "unknown_image_state": "unknown",
        }
        if any(
            blocker.code in deterministic_image_blockers
            and (
                (
                    blocker.code != "image_mismatch"
                    and blocker.subject != image_subject
                )
                or self.image.state != deterministic_image_blockers[blocker.code]
            )
            for blocker in self.blockers
        ):
            raise ValueError("image blocker contradicts image state")
        artifact_consequences = {
            "missing": ("missing_deployment_artifact", "deployment_artifact"),
            "invalid": ("invalid_deployment_artifact", "source_fact"),
            "unsafe": ("unsafe_deployment_artifact", "source_fact"),
            "unknown": ("unknown_deployment_artifact", "deployment_artifact"),
        }
        artifact_subject = self.deployment_artifact.service
        if self.deployment_artifact.state in artifact_consequences:
            blocker, missing_fact = artifact_consequences[
                self.deployment_artifact.state
            ]
            if not any(
                row.code == blocker
                and (artifact_subject is None or row.subject == artifact_subject)
                for row in self.blockers
            ) or not any(
                fact.code == missing_fact
                and (artifact_subject is None or fact.subject == artifact_subject)
                for fact in self.missing_facts
            ):
                raise ValueError("artifact state lacks mandatory consequence")
        deterministic_artifact_blockers = {
            "missing_deployment_artifact": "missing",
            "invalid_deployment_artifact": "invalid",
            "unsafe_deployment_artifact": "unsafe",
            "unknown_deployment_artifact": "unknown",
        }
        if any(
            blocker.code in deterministic_artifact_blockers
            and (
                (artifact_subject is not None and blocker.subject != artifact_subject)
                or self.deployment_artifact.state
                != deterministic_artifact_blockers[blocker.code]
            )
            for blocker in self.blockers
        ):
            raise ValueError("artifact blocker contradicts artifact state")
        compatibility = self.compatibility[0]
        if compatibility.result == "incompatible" and not any(
            blocker.code == "incompatible_application_environment"
            and blocker.subject == image_subject
            for blocker in self.blockers
        ):
            raise ValueError("incompatible result lacks blocker")
        if compatibility.result == "unknown" and not (
            any(
                blocker.code == "unknown_compatibility"
                and blocker.subject == image_subject
                for blocker in self.blockers
            )
            and any(
                fact.code == "compatibility_fact"
                and fact.subject == image_subject
                for fact in self.missing_facts
            )
        ):
            raise ValueError("unknown compatibility lacks mandatory consequence")
        if compatibility.reason_code == "target_required" and not (
            any(
                blocker.code == "missing_target_identity"
                and blocker.subject == image_subject
                for blocker in self.blockers
            )
            and any(
                fact.code == "target_identity" and fact.subject == image_subject
                for fact in self.missing_facts
            )
        ):
            raise ValueError("target-required result lacks mandatory consequence")
        if any(
            blocker.subject != image_subject
            or compatibility.result != "incompatible"
            for blocker in self.blockers
            if blocker.code == "incompatible_application_environment"
        ):
            raise ValueError("incompatible blocker contradicts compatibility")
        if any(
            blocker.subject != image_subject or compatibility.result != "unknown"
            for blocker in self.blockers
            if blocker.code == "unknown_compatibility"
        ):
            raise ValueError("unknown blocker contradicts compatibility")
        if any(
            blocker.subject != image_subject
            or compatibility.reason_code != "target_required"
            for blocker in self.blockers
            if blocker.code == "missing_target_identity"
        ) or any(
            fact.subject != image_subject
            or compatibility.reason_code != "target_required"
            for fact in self.missing_facts
            if fact.code == "target_identity"
        ):
            raise ValueError("target identity consequence contradicts compatibility")
        if any(
            not any(
                blocker.code == "required_operator_confirmation"
                and blocker.subject == confirmation.subject
                for blocker in self.blockers
            )
            for confirmation in self.required_operator_confirmations
        ):
            raise ValueError("confirmation lacks mandatory blocker")
        return self


class RawEvidenceObservation(ContractModel):
    observation_kind: Literal[
        "present",
        "absent",
        "parse_failure",
        "schema_failure",
        "unsupported_source_class",
        "missing_required_field",
        "malformed_timestamp",
        "malformed_identity",
        "malformed_digest",
        "source_unavailable",
    ]
    expected_source_id: SafeSourceId
    source_class: SourceClass | Literal["unknown"] | None
    subject: Id128 | None
    release_version: Version | None
    image_reference: OciRepository | None
    image_digest: Sha256Digest | None
    released_source_id: SafeSourceId | None
    attested_at: UtcSecond | None
    adapter_reason: (
        Literal[
            "record_absent",
            "record_parse_failure",
            "record_schema_failure",
            "source_class_unsupported",
            "required_field_missing",
            "timestamp_malformed",
            "identity_malformed",
            "digest_malformed",
            "source_read_unavailable",
        ]
        | None
    )

    @model_validator(mode="after")
    def relation(self) -> RawEvidenceObservation:
        released = (
            self.source_class,
            self.subject,
            self.release_version,
            self.image_reference,
            self.image_digest,
            self.released_source_id,
            self.attested_at,
        )
        reasons = {
            "absent": "record_absent",
            "parse_failure": "record_parse_failure",
            "schema_failure": "record_schema_failure",
            "unsupported_source_class": "source_class_unsupported",
            "missing_required_field": "required_field_missing",
            "malformed_timestamp": "timestamp_malformed",
            "malformed_identity": "identity_malformed",
            "malformed_digest": "digest_malformed",
            "source_unavailable": "source_read_unavailable",
        }
        if self.observation_kind == "present":
            if (
                self.adapter_reason is not None
                or any(x is None for x in released)
                or self.source_class == "unknown"
            ):
                raise ValueError("invalid observation relation")
        elif self.adapter_reason != reasons[self.observation_kind]:
            raise ValueError("invalid observation reason")
        elif self.observation_kind in {
            "absent",
            "parse_failure",
            "source_unavailable",
        } and any(x is not None for x in released):
            raise ValueError("invalid observation null relation")
        elif self.observation_kind == "unsupported_source_class" and (
            self.source_class != "unknown"
            or any(x is not None for x in released[1:5] + released[6:])
        ):
            raise ValueError("invalid unsupported relation")
        elif self.observation_kind == "missing_required_field" and all(
            x is not None for x in released
        ):
            raise ValueError("invalid missing relation")
        elif self.observation_kind == "malformed_timestamp" and (
            self.attested_at is not None or any(x is None for x in released[:-1])
        ):
            raise ValueError("invalid timestamp relation")
        elif self.observation_kind == "malformed_identity" and (
            self.released_source_id is not None
            or any(x is None for x in released[:5])
            or self.attested_at is None
        ):
            raise ValueError("invalid identity relation")
        elif self.observation_kind == "malformed_digest" and (
            self.image_digest is not None
            or any(x is None for i, x in enumerate(released) if i != 4)
        ):
            raise ValueError("invalid digest relation")
        return self


class EvidenceDecisionInput(ContractModel):
    record_type: Literal["image_release_evidence_decision_v1"] = (
        "image_release_evidence_decision_v1"
    )
    expected_source_id: SafeSourceId
    source_class: SourceClass | Literal["unknown"]
    subject: Id128 | None
    claim: Literal["immutable_image_release"] = "immutable_image_release"
    release_version: Version | None
    image_reference: OciRepository | None
    image_digest: Sha256Digest | None
    source_id: SafeSourceId | None
    immutable_identity: LowerHex64 | None
    evidence_id: LowerHex64 | None
    attested_at: UtcSecond | None
    freshness_window_seconds: Annotated[StrictInt, Field(ge=60, le=31536000)] | None
    disposition: Literal[
        "accepted",
        "missing",
        "untrusted",
        "unsupported",
        "malformed",
        "unavailable",
        "conflicted",
        "mismatched",
    ]
    eligibility: Literal["eligible", "ineligible"]
    reason_code: Literal[
        "accepted_fresh",
        "accepted_stale",
        "record_missing",
        "source_class_untrusted",
        "source_class_unsupported",
        "record_malformed",
        "timestamp_malformed",
        "digest_or_identity_malformed",
        "accepted_claim_conflict",
        "immutable_identity_conflict",
        "release_identity_mismatch",
        "source_unavailable",
    ]

    @model_validator(mode="after")
    def triple(self) -> EvidenceDecisionInput:
        allowed = {
            ("accepted", "eligible", "accepted_fresh"),
            ("accepted", "ineligible", "accepted_stale"),
            ("missing", "ineligible", "record_missing"),
            ("untrusted", "ineligible", "source_class_untrusted"),
            ("unsupported", "ineligible", "source_class_unsupported"),
            ("malformed", "ineligible", "record_malformed"),
            ("malformed", "ineligible", "timestamp_malformed"),
            ("malformed", "ineligible", "digest_or_identity_malformed"),
            ("conflicted", "ineligible", "accepted_claim_conflict"),
            ("conflicted", "ineligible", "immutable_identity_conflict"),
            ("mismatched", "ineligible", "release_identity_mismatch"),
            ("unavailable", "ineligible", "source_unavailable"),
        }
        if (self.disposition, self.eligibility, self.reason_code) not in allowed:
            raise ValueError("invalid evidence decision relation")
        complete = all(
            value is not None
            for value in (
                self.subject,
                self.release_version,
                self.image_reference,
                self.image_digest,
                self.source_id,
                self.attested_at,
            )
        )
        identity_input_complete = complete and self.source_class != "unknown"
        identities_complete = (
            self.immutable_identity is not None and self.evidence_id is not None
        )
        if identities_complete != identity_input_complete:
            raise ValueError("invalid evidence identity relation")
        if self.freshness_window_seconds is not None and (
            self.attested_at is None or self.source_class == "unknown"
        ):
            raise ValueError("invalid freshness relation")
        if self.eligibility == "eligible" and not complete:
            raise ValueError("eligible evidence must be complete")
        if self.disposition == "accepted" and (
            not identity_input_complete
            or self.freshness_window_seconds is None
        ):
            raise ValueError("accepted evidence must be complete")
        return self


class EvidenceImmutableIdentityInputV1(ContractModel):
    catalog_item_id: Id128
    release_version: Version
    image_reference: OciRepository
    image_digest: Sha256Digest
    source_class: SourceClass
    source_id: SafeSourceId
    attested_at: UtcSecond


class EvidenceIdInputV1(ContractModel):
    source_class: SourceClass
    source_id: SafeSourceId
    immutable_identity: LowerHex64


class CatalogReleaseClaimDecisionInputV1(ContractModel):
    version: Version
    published_at: UtcSecond


class DeploymentBindingDecisionInputV1(ContractModel):
    kind: Literal["docker-compose"] = "docker-compose"
    repository_path: RepoPath
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))]


class RequirementPortDecisionInputV1(ContractModel):
    port: Annotated[StrictInt, Field(ge=1, le=65535)]
    protocol: Literal["tcp", "udp"]
    direction: Literal["inbound", "outbound"]
    required: StrictBool


class RelationshipDecisionInputV1(ContractModel):
    kind: Literal[
        "depends_on",
        "provides",
        "consumes",
        "requires",
        "integrates_with",
        "conflicts_with",
        "runs_on",
        "deployed_by",
        "compatible_with",
        "incompatible_with",
    ]
    item_id: Id64
    required: StrictBool
    minimum_version: Version | None
    maximum_version: Version | None

    @model_validator(mode="after")
    def bounds(self) -> RelationshipDecisionInputV1:
        if (
            self.minimum_version is not None
            and self.maximum_version is not None
            and version_components(self.minimum_version)
            > version_components(self.maximum_version)
        ):
            raise ValueError("minimum version exceeds maximum version")
        return self


class RequirementDecisionInputV1(ContractModel):
    capability_ids: tuple[Id64, ...] = Field(max_length=64)
    cpu_cores_min: DecimalString | None
    memory_mb_min: Annotated[StrictInt, Field(ge=0, le=2147483647)] | None
    storage_gb_min: DecimalString | None
    gpu_required: StrictBool
    gpu_memory_gb_min: DecimalString | None
    architectures: tuple[Id64, ...] = Field(max_length=32)
    operating_systems: tuple[Id64, ...] = Field(max_length=32)
    runtimes: tuple[Id64, ...] = Field(max_length=32)
    devices: tuple[Id64, ...] = Field(max_length=32)
    ports: tuple[RequirementPortDecisionInputV1, ...] = Field(max_length=64)
    requires_internet: StrictBool
    requires_lan: StrictBool

    @model_validator(mode="after")
    def normalized_arrays(self) -> RequirementDecisionInputV1:
        for values in (
            self.capability_ids, self.architectures, self.operating_systems,
            self.runtimes, self.devices,
        ):
            if tuple(sorted(values)) != values or len(set(values)) != len(values):
                raise ValueError("requirement IDs must be sorted and unique")
        port_keys = tuple(
            (p.port, p.protocol, p.direction, p.required) for p in self.ports
        )
        if tuple(sorted(port_keys)) != port_keys or len(set(port_keys)) != len(port_keys):
            raise ValueError("ports must be sorted and unique")
        return self


class CatalogDecisionInputV1(ContractModel):
    schema_version: Literal[1] = 1
    catalog_entry_id: Id64
    item_id: Id64
    item_type: Literal[
        "application",
        "service",
        "container_image",
        "ai_model",
        "integration",
        "hardware_device",
        "deployment_method",
    ]
    item_status: Literal["active", "deprecated", "experimental", "unknown"]
    item_version: Version | None
    release_claim: CatalogReleaseClaimDecisionInputV1 | None
    release_version: Version | None
    provenance_source_type: Literal["curated", "private", "community", "dynamic"]
    provenance_source_id: SafeSourceId
    provenance_entry_id: Id64 | None
    provenance_version: (
        Annotated[str, AfterValidator(lambda v: plain_text(v, 1, 64))] | None
    )
    provenance_trust_level: Literal[
        "curated", "verified", "community", "private", "dynamic"
    ]
    deployment_binding: DeploymentBindingDecisionInputV1 | None
    requirements: RequirementDecisionInputV1
    relationships: tuple[RelationshipDecisionInputV1, ...] = Field(max_length=64)
    reviewed_content_digest: Sha256Digest

    @model_validator(mode="after")
    def relation(self) -> CatalogDecisionInputV1:
        selected = self.release_claim.version if self.release_claim else self.item_version
        if self.release_claim and self.item_version and self.release_claim.version != self.item_version:
            raise ValueError("catalog release conflict")
        if self.release_version != selected:
            raise ValueError("invalid selected release")
        keys = tuple(
            (_RELATIONSHIP_RANK[r.kind], r.item_id, r.required,
             _nullable(r.minimum_version), _nullable(r.maximum_version))
            for r in self.relationships
        )
        if tuple(sorted(keys)) != keys or len(set(keys)) != len(keys):
            raise ValueError("relationships must be sorted and unique")
        return self


class CatalogSourceIdentityInputV1(ContractModel):
    catalog_entry_id: Id64
    item_id: Id64
    provenance_source_type: Literal["curated", "private", "community", "dynamic"]
    provenance_source_id: SafeSourceId
    provenance_entry_id: Id64 | None
    provenance_version: (
        Annotated[str, AfterValidator(lambda v: plain_text(v, 1, 64))] | None
    )
    reviewed_content_digest: Sha256Digest


class BindingIdentityInputV1(ContractModel):
    catalog_entry_id: Id64
    binding: DeploymentBindingDecisionInputV1


class BindingAbsentIdentityInputV1(ContractModel):
    catalog_entry_id: Id64
    state: Literal["absent"] = "absent"


class ArtifactContentIdentityInputV1(ContractModel):
    repository_path: RepoPath
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))]
    content_digest: Sha256Digest


class ArtifactAbsentIdentityInputV1(ContractModel):
    repository_path: RepoPath
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))]
    state: Literal["missing"] = "missing"


class ArtifactRejectedIdentityInputV1(ContractModel):
    repository_path: RepoPath | None
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))] | None
    state: Literal["invalid", "unsafe", "unknown"]
    reason_code: ArtifactReasonCode


class ArtifactUnboundIdentityInputV1(ContractModel):
    catalog_entry_id: Id64
    state: Literal["unknown"] = "unknown"


class ApplicationDecisionInputV1(ContractModel):
    item_id: Id64
    catalog_entry_id: Id64
    release_version: Version | None


class CatalogDecisionFingerprintInputV1(ContractModel):
    catalog_identity: LowerHex64
    catalog_source_identity: LowerHex64
    decision: CatalogDecisionInputV1


class BindingDecisionInputV1(ContractModel):
    state: Literal["present", "absent"]
    repository_path: RepoPath | None
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))] | None
    identity: LowerHex64

    @model_validator(mode="after")
    def relation(self) -> BindingDecisionInputV1:
        if (self.state == "present") != (
            self.repository_path is not None and self.service is not None
        ):
            raise ValueError("invalid binding relation")
        return self


class ArtifactDecisionInputV1(ContractModel):
    state: ArtifactState
    repository_path: RepoPath | None
    service: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 255))] | None
    content_digest: Sha256Digest | None
    reason_code: ArtifactReasonCode | None
    identity: LowerHex64

    @model_validator(mode="after")
    def relation(self) -> ArtifactDecisionInputV1:
        allowed = {
            "present": {None},
            "missing": {None},
            "invalid": {
                "content_size",
                "non_utf8",
                "invalid_yaml",
                "ambiguous_service",
            },
            "unsafe": {"containment_escape", "symlink", "non_regular"},
            "unknown": {"observation_unknown"},
        }
        if self.reason_code not in allowed[self.state]:
            raise ValueError("invalid artifact state/reason")
        if self.state == "present" and (
            self.repository_path is None
            or self.service is None
            or self.content_digest is None
        ):
            raise ValueError("invalid present artifact")
        if self.state == "missing" and (
            self.repository_path is None
            or self.service is None
            or self.content_digest is not None
        ):
            raise ValueError("invalid missing artifact")
        if (
            self.state in {"invalid", "unsafe", "unknown"}
            and self.content_digest is not None
        ):
            raise ValueError("rejected artifact cannot have digest")
        if self.state in {"invalid", "unsafe"} and (
            self.repository_path is None or self.service is None
        ):
            raise ValueError("rejected bound artifact must retain binding")
        if self.state == "unknown" and (
            (self.repository_path is None) != (self.service is None)
        ):
            raise ValueError("unknown artifact has partial binding")
        return self


class ImageDecisionInputV1(ContractModel):
    state: Literal[
        "grounded",
        "missing",
        "mutable",
        "untrusted",
        "conflicted",
        "mismatched",
        "unknown",
    ]
    reference: OciRepository | None
    digest: Sha256Digest | None
    release_version: Version | None

    @model_validator(mode="after")
    def relation(self) -> ImageDecisionInputV1:
        if self.state == "grounded":
            valid = all(
                value is not None
                for value in (self.reference, self.digest, self.release_version)
            )
        elif self.state == "conflicted":
            valid = (
                self.reference is None
                and self.digest is None
                and self.release_version is not None
            )
        elif self.state == "mutable":
            valid = self.reference is not None and self.digest is None
        elif self.state == "missing":
            valid = self.digest is None
        elif self.state == "untrusted":
            valid = all(
                value is not None
                for value in (self.reference, self.digest, self.release_version)
            )
        else:
            valid = (self.reference is None) == (self.digest is None)
        if not valid:
            raise ValueError("invalid image decision relation")
        return self


class ProvenanceDecisionInputV1(ContractModel):
    claim: Id128
    source_class: ProvenanceSourceClass
    source_id: SafeSourceId
    immutable_identity: LowerHex64
    observed_at: UtcSecond | None
    attested_at: UtcSecond | None


class CompatibilityFindingInputV1(ContractModel):
    id: Id128
    check_type: Literal[
        "capability",
        "resource",
        "platform",
        "network",
        "relationship",
        "catalog",
        "version",
    ]
    severity: Literal["blocker", "warning", "info", "unknown"]
    status: Literal[
        "compatible",
        "compatible_with_warnings",
        "insufficient_information",
        "incompatible",
    ]
    subject: Id128
    evidence_ids: tuple[Id64, ...] = Field(max_length=32)

    @model_validator(mode="after")
    def normalized_evidence(self) -> CompatibilityFindingInputV1:
        if tuple(sorted(self.evidence_ids)) != self.evidence_ids or len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence IDs must be sorted and unique")
        return self


def _compatibility_source_relation(
    status: str,
    findings: tuple[CompatibilityFindingInputV1, ...],
    unknown_fact_codes: tuple[str, ...],
) -> bool:
    """Validate the frozen aggregate/finding relation of a released result."""
    warning_basis = any(finding.severity == "warning" for finding in findings)
    blocker_basis = any(finding.severity == "blocker" for finding in findings)
    unknown_basis = bool(unknown_fact_codes) or any(
        finding.severity == "unknown" for finding in findings
    )
    if status == "compatible":
        return not warning_basis and not blocker_basis and not unknown_basis
    if status == "compatible_with_warnings":
        return warning_basis and not blocker_basis and not unknown_basis
    if status == "incompatible":
        return blocker_basis and not unknown_basis
    if status == "insufficient_information":
        return unknown_basis
    return False


class CompatibilityDecisionInputV1(ContractModel):
    contract: Literal["installation-plan-compatibility-input-v1"] = (
        "installation-plan-compatibility-input-v1"
    )
    item_id: Id64
    evaluator_identity: LowerHex64
    input_identity: LowerHex64
    source_target_type_present: StrictBool
    source_result: Literal[
        "compatible",
        "compatible_with_warnings",
        "insufficient_information",
        "incompatible",
        "not_available",
    ]
    projected_result: Literal[
        "compatible", "compatible_with_warnings", "incompatible", "unknown"
    ]
    projected_reason: Literal[
        "target_free_catalog_compatible",
        "target_free_catalog_warning",
        "target_free_catalog_incompatible",
        "target_required",
        "compatibility_fact_missing",
        "compatibility_fact_malformed",
    ]
    findings: tuple[CompatibilityFindingInputV1, ...] = Field(max_length=128)
    unknown_fact_codes: tuple[Id128, ...] = Field(max_length=128)
    warning_projection: StrictBool
    target_required_projection: StrictBool

    @model_validator(mode="after")
    def relation(self) -> CompatibilityDecisionInputV1:
        finding_keys = tuple(
            (f.id, f.check_type, f.severity, f.status, f.subject, f.evidence_ids)
            for f in self.findings
        )
        _ordered_unique(finding_keys, "compatibility findings")
        unknown_keys = tuple((code,) for code in self.unknown_fact_codes)
        _ordered_unique(unknown_keys, "compatibility unknown fact codes")
        warnings = any(f.severity == "warning" for f in self.findings)
        blockers = any(f.severity == "blocker" for f in self.findings)
        unknown = bool(self.unknown_fact_codes)
        source_valid = self.source_result == "not_available" or _compatibility_source_relation(
            self.source_result, self.findings, self.unknown_fact_codes
        )
        if self.source_target_type_present:
            valid = (
                self.source_result != "not_available"
                and source_valid
                and self.projected_result == "unknown"
                and self.projected_reason == "target_required"
                and not self.warning_projection
                and self.target_required_projection
            )
        elif self.projected_reason == "compatibility_fact_malformed":
            valid = (
                self.source_result == "insufficient_information"
                and self.projected_result == "unknown"
                and not self.findings
                and self.unknown_fact_codes
                == ("malformed_optional_compatibility_fact",)
                and not self.warning_projection
                and not self.target_required_projection
            )
        elif self.source_result == "not_available":
            valid = (
                self.projected_result == "unknown"
                and self.projected_reason == "compatibility_fact_missing"
                and not self.findings
                and not self.unknown_fact_codes
                and not self.warning_projection
                and not self.target_required_projection
            )
        elif self.source_result == "compatible":
            valid = (
                source_valid
                and self.projected_result == "compatible"
                and self.projected_reason == "target_free_catalog_compatible"
                and not warnings
                and not blockers
                and not unknown
                and not self.warning_projection
                and not self.target_required_projection
            )
        elif self.source_result == "compatible_with_warnings":
            valid = (
                source_valid
                and self.projected_result == "compatible_with_warnings"
                and self.projected_reason == "target_free_catalog_warning"
                and warnings
                and not blockers
                and not unknown
                and self.warning_projection
                and not self.target_required_projection
            )
        elif self.source_result == "incompatible":
            valid = (
                source_valid
                and self.projected_result == "incompatible"
                and self.projected_reason == "target_free_catalog_incompatible"
                and blockers
                and not unknown
                and not self.warning_projection
                and not self.target_required_projection
            )
        else:
            valid = (
                source_valid
                and self.source_result == "insufficient_information"
                and self.projected_result == "unknown"
                and self.projected_reason == "compatibility_fact_missing"
                and not self.warning_projection
                and not self.target_required_projection
            )
        if not valid:
            raise ValueError("invalid compatibility projection relation")
        return self


class CompatibilityReleasedInputV1(ContractModel):
    item_id: Id64
    target_type_present: StrictBool
    status: Literal[
        "compatible", "compatible_with_warnings", "insufficient_information", "incompatible"
    ]
    findings: tuple[CompatibilityFindingInputV1, ...] = Field(max_length=128)
    unknown_fact_codes: tuple[Id128, ...] = Field(max_length=128)

    @model_validator(mode="after")
    def relation(self) -> CompatibilityReleasedInputV1:
        finding_keys = tuple(
            (f.id, f.check_type, f.severity, f.status, f.subject, f.evidence_ids)
            for f in self.findings
        )
        _ordered_unique(finding_keys, "compatibility findings")
        _ordered_unique(tuple((code,) for code in self.unknown_fact_codes), "compatibility unknown fact codes")
        if not _compatibility_source_relation(
            self.status, self.findings, self.unknown_fact_codes
        ):
            raise ValueError("invalid released compatibility relation")
        return self


class CompatibilityAbsentInputV1(ContractModel):
    item_id: Id64
    state: Literal["not_available"] = "not_available"


class CompatibilityEvaluatorIdentityInputV1(ContractModel):
    contract: Literal["installation-plan-compatibility-v1"] = (
        "installation-plan-compatibility-v1"
    )
    catalog_identity: LowerHex64
    ruleset_version: Literal[1] = 1


class PrerequisiteDescriptorInputV1(ContractModel):
    kind: Literal["storage", "network", "platform", "application"]
    requirement_key: Annotated[str, AfterValidator(lambda v: plain_text(v, 1, 192))]
    relationship: RelationshipDecisionInputV1 | None


class PrerequisiteDecisionInputV1(ContractModel):
    prerequisite_id: Id64
    kind: Literal["storage", "network", "platform", "application", "operator"]
    state: Literal["satisfied", "missing", "unknown"]
    descriptor: PrerequisiteDescriptorInputV1


class PrerequisiteIdentityInputV1(ContractModel):
    descriptor: PrerequisiteDescriptorInputV1
    prerequisite: PrerequisiteDecisionInputV1
    catalog_identity: LowerHex64


class AssumptionDecisionInputV1(ContractModel):
    assumption_id: Id64
    kind: Literal["catalog", "environment", "operator"]
    source_fact_kind: Literal["prerequisite_unknown", "compatibility_warning"]
    subject: Id128


class AssumptionIdentityInputV1(ContractModel):
    kind: Literal["catalog", "environment", "operator"]
    source_fact_kind: Literal["prerequisite_unknown", "compatibility_warning"]
    subject: Id128


class BlockerDecisionInputV1(ContractModel):
    code: BlockerCode
    subject: Id128


class RiskDecisionInputV1(ContractModel):
    code: Literal["evidence_approaching_expiry", "compatibility_warning"]
    severity: Literal["low", "medium", "high", "critical"]
    subject: Id128


class MissingFactDecisionInputV1(ContractModel):
    code: Literal[
        "deployment_binding",
        "deployment_artifact",
        "immutable_image_identity",
        "accepted_evidence",
        "prerequisite_fact",
        "target_identity",
        "compatibility_fact",
        "source_fact",
    ]
    subject: Id128


class ConfirmationDecisionInputV1(ContractModel):
    code: Literal["accept_assumption", "confirm_prerequisite", "confirm_risk"]
    subject: Id128
    prompt_template_id: Annotated[str, AfterValidator(lambda v: bounded_id(v, 1, 64))]


class AbsenceFactInputV1(ContractModel):
    kind: Literal[
        "deployment_binding",
        "deployment_artifact",
        "evidence_record",
        "compatibility_fact",
        "prerequisite_fact",
    ]
    subject: Id128
    source_id: SafeSourceId
    identity: LowerHex64


class ConflictFactInputV1(ContractModel):
    kind: Literal["image_claim", "provenance_identity", "immutable_identity"]
    subject: Id128
    left_identity: LowerHex64
    right_identity: LowerHex64

    @model_validator(mode="after")
    def ordered_pair(self) -> ConflictFactInputV1:
        if self.left_identity >= self.right_identity:
            raise ValueError("conflict identities must be strictly ordered")
        return self


class SourceUnavailableFactInputV1(ContractModel):
    kind: Literal["optional_evidence_source"] = "optional_evidence_source"
    subject: Id128
    expected_source_id: SafeSourceId
    reason_code: Literal["source_read_unavailable"] = "source_read_unavailable"
    identity: LowerHex64


class FreshnessDecisionInputV1(ContractModel):
    evidence_identity: LowerHex64
    effective_time: UtcSecond
    window_seconds: Annotated[StrictInt, Field(ge=60, le=31536000)]
    age_seconds: Annotated[StrictInt, Field(ge=0, le=315537897599)]
    result: Literal["fresh", "stale"]

    @model_validator(mode="after")
    def relation(self) -> FreshnessDecisionInputV1:
        if (self.age_seconds <= self.window_seconds) != (self.result == "fresh"):
            raise ValueError("invalid freshness result")
        return self


class FreshnessPolicyIdentityInputV1(ContractModel):
    curated: Literal[31536000] = 31536000
    registry_attested: Literal[2592000] = 2592000
    upstream_signed: Literal[604800] = 604800


class FreshnessIdentityInputV1(ContractModel):
    policy_identity: LowerHex64
    evaluation_instant: UtcSecond
    evidence_identity: LowerHex64
    effective_time: UtcSecond
    window_seconds: Annotated[StrictInt, Field(ge=60, le=31536000)]
    age_seconds: Annotated[StrictInt, Field(ge=0, le=315537897599)]
    result: Literal["fresh", "stale"]


class AbsenceIdentityInputV1(ContractModel):
    kind: Literal[
        "deployment_binding", "deployment_artifact", "evidence_record",
        "compatibility_fact", "prerequisite_fact",
    ]
    subject: Id128
    source_id: SafeSourceId


class SourceUnavailableIdentityInputV1(ContractModel):
    kind: Literal["optional_evidence_source"] = "optional_evidence_source"
    subject: Id128
    expected_source_id: SafeSourceId
    reason_code: Literal["source_read_unavailable"] = "source_read_unavailable"


class FingerprintInputV1(ContractModel):
    fingerprint_contract: Literal["installation-plan-fingerprint-v1"] = (
        "installation-plan-fingerprint-v1"
    )
    schema_version: Literal["installation-plan-v1"] = "installation-plan-v1"
    evaluation_instant: UtcSecond
    freshness_policy_identity: LowerHex64
    application: ApplicationDecisionInputV1
    catalog: CatalogDecisionFingerprintInputV1
    binding: BindingDecisionInputV1
    artifact: ArtifactDecisionInputV1
    image: ImageDecisionInputV1
    evidence_decisions: tuple[EvidenceDecisionInput, ...] = Field(max_length=128)
    provenance_decisions: tuple[ProvenanceDecisionInputV1, ...] = Field(
        min_length=1, max_length=256
    )
    compatibility_decisions: tuple[CompatibilityDecisionInputV1, ...] = Field(
        min_length=1, max_length=1
    )
    prerequisites: tuple[PrerequisiteDecisionInputV1, ...] = Field(max_length=64)
    relationships: tuple[RelationshipDecisionInputV1, ...] = Field(max_length=64)
    assumptions: tuple[AssumptionDecisionInputV1, ...] = Field(max_length=32)
    blockers: tuple[BlockerDecisionInputV1, ...] = Field(max_length=64)
    risks: tuple[RiskDecisionInputV1, ...] = Field(max_length=32)
    missing_facts: tuple[MissingFactDecisionInputV1, ...] = Field(max_length=64)
    confirmations: tuple[ConfirmationDecisionInputV1, ...] = Field(max_length=32)
    absence_facts: tuple[AbsenceFactInputV1, ...] = Field(max_length=128)
    conflict_facts: tuple[ConflictFactInputV1, ...] = Field(max_length=128)
    source_unavailable_facts: tuple[SourceUnavailableFactInputV1, ...] = Field(
        max_length=32
    )
    freshness_decisions: tuple[FreshnessDecisionInputV1, ...] = Field(max_length=128)

    @model_validator(mode="after")
    def normalized_arrays(self) -> FingerprintInputV1:
        arrays = (
            (tuple((x.expected_source_id, _SOURCE_CLASS_RANK[x.source_class],
                    _nullable(x.subject), x.claim, _nullable(x.release_version),
                    _nullable(x.image_reference), _nullable(x.image_digest),
                    _nullable(x.source_id), _nullable(x.immutable_identity),
                    _nullable(x.evidence_id), _DISPOSITION_RANK[x.disposition],
                    _ELIGIBILITY_RANK[x.eligibility],
                    _EVIDENCE_REASON_RANK[x.reason_code], _nullable(x.attested_at),
                    (-1 if x.freshness_window_seconds is None else x.freshness_window_seconds))
                   for x in self.evidence_decisions), "fingerprint evidence decisions"),
            (tuple((x.claim, _PROVENANCE_RANK[x.source_class], x.source_id,
                    x.immutable_identity, _nullable(x.observed_at),
                    _nullable(x.attested_at)) for x in self.provenance_decisions),
             "fingerprint provenance decisions"),
            (tuple((x.item_id, x.evaluator_identity, x.input_identity,
                    _COMPAT_RESULT_RANK[x.projected_result],
                    _COMPAT_REASON_RANK[x.projected_reason])
                   for x in self.compatibility_decisions),
             "fingerprint compatibility decisions"),
            (tuple((x.prerequisite_id, _PREREQUISITE_KIND_RANK[x.kind],
                    _PREREQUISITE_STATE_RANK[x.state]) for x in self.prerequisites),
             "fingerprint prerequisites"),
            (tuple((_RELATIONSHIP_RANK[x.kind], x.item_id, x.required,
                    _nullable(x.minimum_version), _nullable(x.maximum_version))
                   for x in self.relationships), "fingerprint relationships"),
            (tuple((x.assumption_id, _ASSUMPTION_KIND_RANK[x.kind])
                   for x in self.assumptions), "fingerprint assumptions"),
            (tuple((_BLOCKER_RANK[x.code], x.subject) for x in self.blockers),
             "fingerprint blockers"),
            (tuple((_SEVERITY_RANK[x.severity], _RISK_RANK[x.code], x.subject)
                   for x in self.risks), "fingerprint risks"),
            (tuple((_MISSING_RANK[x.code], x.subject) for x in self.missing_facts),
             "fingerprint missing facts"),
            (tuple((_CONFIRMATION_RANK[x.code], x.subject) for x in self.confirmations),
             "fingerprint confirmations"),
            (tuple((_ABSENCE_RANK[x.kind], x.subject, x.source_id, x.identity)
                   for x in self.absence_facts), "fingerprint absence facts"),
            (tuple((_CONFLICT_RANK[x.kind], x.subject, x.left_identity,
                    x.right_identity) for x in self.conflict_facts),
             "fingerprint conflict facts"),
            (tuple((x.kind, x.subject, x.expected_source_id, x.reason_code, x.identity)
                   for x in self.source_unavailable_facts),
             "fingerprint source unavailable facts"),
            (tuple((x.evidence_identity, x.effective_time, x.window_seconds,
                    x.age_seconds, _FRESHNESS_RANK[x.result])
                   for x in self.freshness_decisions),
             "fingerprint freshness decisions"),
        )
        for keys, name in arrays:
            _ordered_unique(keys, name)
        has_image_claim = any(
            fact.kind == "image_claim" for fact in self.conflict_facts
        )
        if (self.image.state == "conflicted") != has_image_claim:
            raise ValueError("fingerprint image conflict relation is invalid")
        return self


def fingerprint(input_value: FingerprintInputV1) -> Fingerprint:
    return Fingerprint(
        value=compound_hash("atlas:installation-plan-fingerprint:v1", input_value)
    )
