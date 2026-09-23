"""Pure v0.65 reference-only control-plane contract.

This package is intentionally a closed value boundary. It has no route,
store, clock, client, credential, command, or effect. Evaluation accepts only
caller-supplied facts and returns a redacted, deterministic decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

SCHEMA = "atlas-closed-control-plane-v1"
PROFILE = "core-reference-only-control-plane-v1"
MAX_ITEMS = 32
MAX_BYTES = 64 * 1024
MAX_IDEMPOTENCY_KEY = 128
MAX_RECORD_BYTES = 96 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


def _identity(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or _ID.fullmatch(value) is None:
        raise ValueError("canonical identity required")
    return value


def _digest(value: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("lowercase SHA-256 digest required")
    return value


def _timestamp(value: str) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise ValueError("whole-second UTC timestamp required")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("whole-second UTC timestamp required") from error
    return value


Identity = Annotated[str, AfterValidator(_identity)]
Sha256 = Annotated[str, AfterValidator(_digest)]
UtcSecond = Annotated[str, AfterValidator(_timestamp)]


def _plain(value: Any, depth: int = 0) -> Any:
    if depth > 32:
        raise ValueError("contract nesting exceeds bound")
    if isinstance(value, BaseModel):
        value = {**value.__dict__, **(value.__pydantic_extra__ or {})}
    if isinstance(value, dict):
        return {key: _plain(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_plain(item, depth + 1) for item in value)
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def fingerprint(domain: str, value: Any) -> str:
    """Hash one explicit domain; domains prevent cross-purpose substitution."""
    if not isinstance(domain, str) or not domain or ":" in domain:
        raise ValueError("invalid fingerprint domain")
    return hashlib.sha256(f"atlas:{domain}:v1\0".encode() + _canonical(value)).hexdigest()


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    @model_validator(mode="before")
    @classmethod
    def copy_input(cls, value: Any) -> Any:
        raw = _plain(value)
        if len(_canonical(raw)) > MAX_BYTES:
            raise ValueError("contract envelope exceeds bound")
        return raw

    @model_validator(mode="after")
    def bounded(self) -> ContractModel:
        if len(_canonical(self)) > MAX_BYTES:
            raise ValueError("contract envelope exceeds bound")
        return self


class ControlPlanePolicyV1(ContractModel):
    schema: Literal["atlas-control-plane-policy-v1"] = "atlas-control-plane-policy-v1"
    permitted_kinds: tuple[Literal["reference"], ...] = ("reference",)
    max_items: int = Field(default=0, ge=0, le=MAX_ITEMS)
    effect_allowed: Literal[False] = False
    runtime_creation_allowed: Literal[False] = False
    credential_present: Literal[False] = False
    payload_bytes: Literal[0] = 0

    @model_validator(mode="after")
    def closed(self) -> ControlPlanePolicyV1:
        if self.permitted_kinds != ("reference",) or self.max_items != 0:
            raise ValueError("policy widening is forbidden")
        return self


class ControlPlaneLineageV1(ContractModel):
    schema: Literal["atlas-control-plane-lineage-v1"] = "atlas-control-plane-lineage-v1"
    lineage_id: Identity
    predecessor_fingerprint: Sha256
    generation: Literal[1] = 1
    lineage_fingerprint: Sha256

    @model_validator(mode="after")
    def exact(self) -> ControlPlaneLineageV1:
        if self.lineage_fingerprint != lineage_fingerprint(self):
            raise ValueError("lineage fingerprint mismatch")
        return self


class ControlPlaneInputV1(ContractModel):
    schema: Literal["atlas-closed-control-plane-input-v1"] = "atlas-closed-control-plane-input-v1"
    subject_id: Identity
    lineage: ControlPlaneLineageV1
    policy: ControlPlanePolicyV1
    observed_fingerprint: Sha256
    observed_at: UtcSecond
    valid_until: UtcSecond
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    authority_granted: Literal[False] = False
    ambiguous: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> ControlPlaneInputV1:
        if self.valid_until <= self.observed_at:
            raise ValueError("invalid validity interval")
        if self.observed_fingerprint != input_fingerprint(self):
            raise ValueError("observed fingerprint mismatch")
        return self


RefusalV1 = Literal[
    "invalid_request", "stale_lineage", "foreign_lineage", "fingerprint_mismatch",
    "policy_widening", "ambiguous_outcome", "authority_payload", "expired",
]


class ControlPlaneEvaluationV1(ContractModel):
    schema: Literal["atlas-closed-control-plane-evaluation-v1"] = "atlas-closed-control-plane-evaluation-v1"
    profile: Literal[PROFILE] = PROFILE
    subject_id: Identity
    evaluated_at: UtcSecond
    outcome: Literal["accepted", "blocked"]
    reason: Literal["reference_recorded"] | RefusalV1
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    authority_granted: Literal[False] = False
    effect_allowed: Literal[False] = False
    runtime_creation_allowed: Literal[False] = False
    credential_present: Literal[False] = False
    payload_bytes: Literal[0] = 0
    evaluation_fingerprint: Sha256

    @model_validator(mode="after")
    def outcome_matches_reason(self) -> ControlPlaneEvaluationV1:
        if (self.outcome == "accepted") != (self.reason == "reference_recorded"):
            raise ValueError("ambiguous outcome")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("evaluation fingerprint mismatch")
        return self


class ControlPlaneEvidenceCreateV1(ContractModel):
    """The only input accepted by the durable, reference-only service."""

    schema: Literal["atlas-control-plane-evidence-create-v1"] = "atlas-control-plane-evidence-create-v1"
    owner_id: Identity
    input: ControlPlaneInputV1
    idempotency_key: Annotated[str, AfterValidator(_identity)]

    @model_validator(mode="after")
    def bounded_key(self) -> ControlPlaneEvidenceCreateV1:
        if len(self.idempotency_key) > MAX_IDEMPOTENCY_KEY:
            raise ValueError("idempotency key exceeds bound")
        if self.input.subject_id == "blocked":
            raise ValueError("blocked subject is not recordable")
        return self


class ControlPlaneEvidenceRecordV1(ContractModel):
    schema: Literal["atlas-control-plane-evidence-record-v1"] = "atlas-control-plane-evidence-record-v1"
    owner_id: Identity
    subject_id: Identity
    input: ControlPlaneInputV1
    evaluation: ControlPlaneEvaluationV1
    recorded_at: UtcSecond
    valid_until: UtcSecond
    subject_fingerprint: Sha256
    idempotency_key_fingerprint: Sha256
    record_fingerprint: Sha256

    @model_validator(mode="after")
    def exact(self) -> ControlPlaneEvidenceRecordV1:
        if self.input.subject_id != self.subject_id:
            raise ValueError("subject mismatch")
        if self.evaluation.subject_id != self.subject_id:
            raise ValueError("evaluation subject mismatch")
        if self.evaluation.outcome != "accepted":
            raise ValueError("only accepted evidence is recordable")
        if self.valid_until != self.input.valid_until or self.recorded_at >= self.valid_until:
            raise ValueError("invalid record validity")
        if self.subject_fingerprint != evidence_subject_fingerprint(self):
            raise ValueError("subject fingerprint mismatch")
        if self.record_fingerprint != evidence_record_fingerprint(self):
            raise ValueError("record fingerprint mismatch")
        return self


class ControlPlaneEvidenceErrorV1(ContractModel):
    schema: Literal["atlas-control-plane-evidence-error-v1"] = "atlas-control-plane-evidence-error-v1"
    error_code: Literal[
        "unauthenticated", "forbidden", "disabled", "invalid_request",
        "expired", "foreign_lineage", "policy_widening", "fingerprint_mismatch",
        "ambiguous_state", "authority_payload", "idempotency_conflict",
        "permanent_subject_reserved", "append_indeterminate", "quota_exceeded",
        "store_corrupt", "unavailable", "evidence_not_found",
    ]
    correlation_fingerprint: Sha256


def lineage_fingerprint(value: ControlPlaneLineageV1 | dict[str, Any]) -> str:
    raw = {"schema": "atlas-control-plane-lineage-v1", "generation": 1, **_plain(value)}
    return fingerprint("control-plane-lineage", {**raw, "lineage_fingerprint": None})


def policy_fingerprint(value: ControlPlanePolicyV1 | dict[str, Any]) -> str:
    raw = {"schema": "atlas-control-plane-policy-v1", "permitted_kinds": ("reference",), "max_items": 0, "effect_allowed": False, "runtime_creation_allowed": False, "credential_present": False, "payload_bytes": 0, **_plain(value)}
    return fingerprint("control-plane-policy", raw)


def input_fingerprint(value: ControlPlaneInputV1 | dict[str, Any]) -> str:
    raw = {"schema": "atlas-closed-control-plane-input-v1", "evidence_only": True, "reference_only": True, "authority_granted": False, "ambiguous": False, **_plain(value)}
    return fingerprint("control-plane-input", {**raw, "observed_fingerprint": None})


def evaluation_fingerprint(value: ControlPlaneEvaluationV1 | dict[str, Any]) -> str:
    raw = {"schema": "atlas-closed-control-plane-evaluation-v1", "profile": PROFILE, "evidence_only": True, "reference_only": True, "authority_granted": False, "effect_allowed": False, "runtime_creation_allowed": False, "credential_present": False, "payload_bytes": 0, **_plain(value)}
    return fingerprint("control-plane-evaluation", {**raw, "evaluation_fingerprint": None})


def idempotency_fingerprint(owner_id: str, key: str) -> str:
    return fingerprint("control-plane-idempotency", {"owner_id": owner_id, "key": key})


def evidence_subject_fingerprint(value: ControlPlaneEvidenceRecordV1 | dict[str, Any]) -> str:
    raw = _plain(value)
    return fingerprint("control-plane-evidence-subject", {"owner_id": raw["owner_id"], "subject_id": raw["subject_id"]})


def evidence_record_fingerprint(value: ControlPlaneEvidenceRecordV1 | dict[str, Any]) -> str:
    raw = _plain(value)
    return fingerprint("control-plane-evidence-record", {"schema": "atlas-control-plane-evidence-record-v1", **raw, "record_fingerprint": None})


def _result(subject_id: str, evaluated_at: str, reason: str) -> ControlPlaneEvaluationV1:
    raw = {"subject_id": subject_id, "evaluated_at": evaluated_at, "outcome": "accepted" if reason == "reference_recorded" else "blocked", "reason": reason, "evaluation_fingerprint": "0" * 64}
    raw["evaluation_fingerprint"] = evaluation_fingerprint(raw)
    return ControlPlaneEvaluationV1.model_validate(raw)


def evaluate_control_plane(value: Any, *, expected_lineage_fingerprint: str, expected_policy_fingerprint: str, evaluated_at: str) -> ControlPlaneEvaluationV1:
    """Evaluate injected evidence; every malformed or unsafe case is blocked."""
    safe_evaluated_at = evaluated_at
    try:
        _timestamp(evaluated_at)
    except (TypeError, ValueError):
        safe_evaluated_at = "1970-01-01T00:00:00Z"
    try:
        raw = _plain(value)
        if not isinstance(raw, dict):
            raise TypeError("invalid request")
        if any(key in raw for key in ("command", "endpoint", "credential", "token", "payload")):
            return _result("blocked", safe_evaluated_at, "authority_payload")
        candidate = ControlPlaneInputV1.model_validate(raw)
        if candidate.ambiguous or candidate.authority_granted:
            return _result(candidate.subject_id, safe_evaluated_at, "ambiguous_outcome")
        if candidate.lineage.lineage_fingerprint != expected_lineage_fingerprint:
            return _result(candidate.subject_id, safe_evaluated_at, "foreign_lineage")
        if policy_fingerprint(candidate.policy) != expected_policy_fingerprint:
            return _result(candidate.subject_id, safe_evaluated_at, "policy_widening")
        if candidate.valid_until <= safe_evaluated_at:
            return _result(candidate.subject_id, safe_evaluated_at, "expired")
        return _result(candidate.subject_id, safe_evaluated_at, "reference_recorded")
    except (KeyError, TypeError, ValueError, ValidationError, RecursionError, OverflowError):
        return _result("blocked", safe_evaluated_at, "invalid_request")


ClosedControlPlaneInputV1 = ControlPlaneInputV1
ClosedControlPlaneEvaluationV1 = ControlPlaneEvaluationV1
