"""Closed, immutable v0.34 installation readiness review models."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.end_to_end_inert_delivery_receipt.contract import (
    EndToEndInertDeliveryLinkageV1,
)
from app.end_to_end_inert_delivery_receipt.contract import (
    linkage_fingerprint as v033_linkage_fingerprint_for,
)
from app.installation_dispatch_handoff.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_REVIEW_BYTES = 64 * 1024
MAX_AUDIT_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_JSON_NESTING = 32
REVIEW_NAMESPACE = uuid.UUID("0c6de994-a4fc-5b75-bad2-b4b62e627e2d")

_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UUID5 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)

ReleaseV1 = Literal[
    "v0.20", "v0.21", "v0.22", "v0.23", "v0.24", "v0.25", "v0.26",
    "v0.27", "v0.28", "v0.29", "v0.30", "v0.31", "v0.32", "v0.33",
]
EvidenceKindV1 = Literal[
    "candidate_record", "approval_intent", "agent_install_container_validation",
    "execution_request", "dispatch_handoff", "agent_intake_simulation",
    "simulated_handoff_delivery", "real_agent_intake", "dormant_delivery_wiring",
    "delivery_activation_preflight", "operator_delivery_enablement",
    "live_delivery_send", "agent_live_intake_admission", "inert_delivery_receipt",
]
EvidenceStateV1 = Literal["current", "missing", "expired", "terminal", "unavailable"]
InstallationReadinessStateV1 = Literal["blocked", "readiness_gated"]
InstallationReadinessBlockerV1 = Literal[
    "missing_evidence", "ownership_mismatch", "linkage_mismatch",
    "fingerprint_mismatch", "invalid_evidence", "stale_evidence",
    "expired_evidence", "terminal_ambiguity", "agent_evidence_unavailable",
    "source_unavailable", "installation_capability_unsupported",
    "execution_admission_not_defined",
]

EVIDENCE_ORDER: tuple[tuple[str, str], ...] = (
    ("v0.20", "candidate_record"), ("v0.21", "approval_intent"),
    ("v0.22", "agent_install_container_validation"),
    ("v0.23", "execution_request"), ("v0.24", "dispatch_handoff"),
    ("v0.25", "agent_intake_simulation"),
    ("v0.26", "simulated_handoff_delivery"),
    ("v0.27", "real_agent_intake"), ("v0.28", "dormant_delivery_wiring"),
    ("v0.29", "delivery_activation_preflight"),
    ("v0.30", "operator_delivery_enablement"),
    ("v0.31", "live_delivery_send"),
    ("v0.32", "agent_live_intake_admission"),
    ("v0.33", "inert_delivery_receipt"),
)
BLOCKER_ORDER: tuple[str, ...] = (
    "missing_evidence", "ownership_mismatch", "linkage_mismatch",
    "fingerprint_mismatch", "invalid_evidence", "stale_evidence",
    "expired_evidence", "terminal_ambiguity", "agent_evidence_unavailable",
    "source_unavailable", "installation_capability_unsupported",
    "execution_admission_not_defined",
)


class StrictContractError(ValueError):
    """Input was outside the closed v0.34 contract."""


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _identity(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid canonical identity")
    return value


def _uuid5(value: str) -> str:
    if _UUID5.fullmatch(value) is None:
        raise ValueError("invalid canonical UUIDv5")
    return value


OperatorId = Annotated[str, AfterValidator(_identity)]
CorrelationId = Annotated[str, AfterValidator(_identity)]
CanonicalUuid5 = Annotated[str, AfterValidator(_uuid5)]


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _closed_value(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_JSON_NESTING:
        raise ValueError("JSON nesting exceeds bound")
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise ValueError("strings must be NFC")
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _closed_value(key, depth=depth + 1)
            _closed_value(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _closed_value(item, depth=depth + 1)
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError("unsupported JSON value")


def canonical_json(value: Any) -> bytes:
    value = _json_value(value)
    _closed_value(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode()


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _fingerprint(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1",
                         value=digest)


def _without(value: BaseModel | dict[str, Any], field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


class _ReadOnlyAuthority(ContractModel):
    evidence_only: Literal[True] = True
    read_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class InstallationReadinessReviewLinkageV1(EndToEndInertDeliveryLinkageV1):
    v033_receipt_id: CanonicalUuid4
    v033_receipt_fingerprint: FingerprintV1
    v033_verification_fingerprint: FingerprintV1
    v033_linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_v033_linkage(self) -> InstallationReadinessReviewLinkageV1:
        inherited = {name: getattr(self, name)
                     for name in EndToEndInertDeliveryLinkageV1.model_fields}
        base = EndToEndInertDeliveryLinkageV1.model_validate(inherited)
        if self.v033_linkage_fingerprint != v033_linkage_fingerprint_for(base):
            raise ValueError("v0.33 linkage fingerprint mismatch")
        return self


class InstallationReadinessEvidenceSummaryV1(ContractModel):
    release: ReleaseV1
    evidence_kind: EvidenceKindV1
    evidence_id: CanonicalUuid4 | None
    evidence_fingerprint: FingerprintV1 | None
    evidence_state: EvidenceStateV1
    valid_until: UtcSecond | None
    evidence_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact_presence(self) -> InstallationReadinessEvidenceSummaryV1:
        identity_missing = self.evidence_id is None or self.evidence_fingerprint is None
        if (self.evidence_id is None) != (self.evidence_fingerprint is None):
            raise ValueError("evidence identity must be complete")
        if identity_missing != (self.evidence_state in {"missing", "unavailable"}):
            raise ValueError("evidence identity and state mismatch")
        if self.evidence_state == "expired" and self.valid_until is None:
            raise ValueError("expired evidence requires valid_until")
        return self


class InstallationReadinessReviewV1(_ReadOnlyAuthority):
    schema: Literal["installation-readiness-review-v1"] = "installation-readiness-review-v1"
    review_id: CanonicalUuid5
    candidate_record_id: CanonicalUuid4
    operator_id: OperatorId
    observed_at: UtcSecond
    readiness: InstallationReadinessStateV1
    blockers: tuple[InstallationReadinessBlockerV1, ...]
    evidence: tuple[InstallationReadinessEvidenceSummaryV1, ...]
    linkage: InstallationReadinessReviewLinkageV1 | None
    source: Literal["core_local_owner_scoped_evidence_v1"] = (
        "core_local_owner_scoped_evidence_v1"
    )
    review_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_review(self) -> InstallationReadinessReviewV1:
        actual_order = tuple((item.release, item.evidence_kind) for item in self.evidence)
        if actual_order != EVIDENCE_ORDER:
            raise ValueError("evidence must contain the exact ordered v0.20-v0.33 chain")
        if tuple(sorted(set(self.blockers), key=BLOCKER_ORDER.index)) != self.blockers:
            raise ValueError("blockers must be unique and canonically ordered")
        if self.readiness == "readiness_gated":
            if self.blockers != ("execution_admission_not_defined",):
                raise ValueError("readiness-gated review requires its sole blocker")
            if self.linkage is None or any(item.evidence_state != "current"
                                           for item in self.evidence):
                raise ValueError("readiness-gated review requires a complete current chain")
        elif not self.blockers:
            raise ValueError("blocked review requires a blocker")
        if self.linkage is None and self.readiness != "blocked":
            raise ValueError("null linkage is allowed only for blocked reviews")
        if self.linkage is not None:
            expected = _expected_summary_identities(self.linkage)
            actual = tuple(
                (item.evidence_id, item.evidence_fingerprint) for item in self.evidence
            )
            if actual != expected:
                raise ValueError("evidence summary linkage mismatch")
        observed = _instant(self.observed_at)
        for item in self.evidence:
            if item.valid_until is None:
                continue
            expiry = _instant(item.valid_until)
            if item.evidence_state == "current" and observed >= expiry:
                raise ValueError("current evidence is stale or expired")
            if item.evidence_state == "expired" and observed < expiry:
                raise ValueError("expired evidence is still current")
        if self.review_id != review_id_for(
            operator_id=self.operator_id, candidate_record_id=self.candidate_record_id,
            receipt_fingerprint=(self.linkage.v033_receipt_fingerprint
                                 if self.linkage else None),
            observed_at=self.observed_at,
        ):
            raise ValueError("review ID mismatch")
        if self.review_fingerprint != review_fingerprint(self):
            raise ValueError("review fingerprint mismatch")
        if len(canonical_json(self)) > MAX_REVIEW_BYTES:
            raise ValueError("review exceeds 64 KiB")
        return self


class InstallationReadinessReviewAuditEvidenceV1(ContractModel):
    schema: Literal["installation-readiness-review-audit-evidence-v1"] = (
        "installation-readiness-review-audit-evidence-v1"
    )
    review_id: CanonicalUuid5
    review_fingerprint: FingerprintV1
    candidate_record_id: CanonicalUuid4
    v033_receipt_fingerprint: FingerprintV1 | None
    linkage_fingerprint: FingerprintV1 | None
    operator_fingerprint: FingerprintV1
    correlation_id: CorrelationId
    observed_at: UtcSecond
    outcome: InstallationReadinessStateV1
    blocker_codes: tuple[InstallationReadinessBlockerV1, ...]
    source_was_owner_scoped_local_readers: Literal[True] = True
    evidence_only: Literal[True] = True
    read_only: Literal[True] = True
    mutation_attempted: Literal[False] = False
    execution_attempted: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact_audit(self) -> InstallationReadinessReviewAuditEvidenceV1:
        if tuple(sorted(set(self.blocker_codes), key=BLOCKER_ORDER.index)) != self.blocker_codes:
            raise ValueError("audit blockers must be unique and canonically ordered")
        if (self.v033_receipt_fingerprint is None) != (self.linkage_fingerprint is None):
            raise ValueError("audit linkage identity must be complete")
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        if len(canonical_json(self)) > MAX_AUDIT_BYTES:
            raise ValueError("audit evidence exceeds 64 KiB")
        return self


class InstallationReadinessReviewRedactedErrorV1(ContractModel):
    schema: Literal["installation-readiness-review-error-v1"] = (
        "installation-readiness-review-error-v1"
    )
    error_code: Literal["malformed", "unauthenticated", "unauthorized",
                        "not_found", "unavailable"]
    safe_message: Literal["Installation readiness review is unavailable."] = (
        "Installation readiness review is unavailable."
    )
    correlation_id: CorrelationId
    redacted: Literal[True] = True
    retryable: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False


class InstallationReadinessReviewResponseV1(ContractModel):
    review: InstallationReadinessReviewV1
    audit_evidence: InstallationReadinessReviewAuditEvidenceV1

    @model_validator(mode="after")
    def exact_response(self) -> InstallationReadinessReviewResponseV1:
        audit, review = self.audit_evidence, self.review
        if not (audit.review_id == review.review_id
                and audit.review_fingerprint == review.review_fingerprint
                and audit.candidate_record_id == review.candidate_record_id
                and audit.observed_at == review.observed_at
                and audit.outcome == review.readiness
                and audit.blocker_codes == review.blockers):
            raise ValueError("review audit binding mismatch")
        if len(canonical_json(self)) > MAX_RESPONSE_BYTES:
            raise ValueError("response exceeds 128 KiB")
        return self


class InstallationReadinessReviewResultV1(_ReadOnlyAuthority):
    disposition: Literal["reviewed", "rejected", "unavailable"]
    response: InstallationReadinessReviewResponseV1 | None
    error: InstallationReadinessReviewRedactedErrorV1 | None

    @model_validator(mode="after")
    def exact_union(self) -> InstallationReadinessReviewResultV1:
        success = self.disposition == "reviewed"
        if success != (self.response is not None and self.error is None):
            raise ValueError("review result union mismatch")
        if not success and not (self.response is None and self.error is not None):
            raise ValueError("review error result union mismatch")
        return self


class InstallationReadinessReviewEvidenceV1(ContractModel):
    """Injected P1-only evidence for pure evaluation; no reader or I/O."""

    operator_id: OperatorId
    authenticated_operator_id: OperatorId
    authentication_verified: Literal[True] = True
    read_permission_verified: Literal[True] = True
    candidate_record_id: CanonicalUuid4
    observed_at: UtcSecond
    evidence: tuple[InstallationReadinessEvidenceSummaryV1, ...]
    linkage: InstallationReadinessReviewLinkageV1 | None
    blockers: tuple[InstallationReadinessBlockerV1, ...] = ()
    home_assistant: bool = False
    installation_capability_supported: bool = True
    source_was_owner_scoped_local_readers: Literal[True] = True

    @model_validator(mode="after")
    def exact_owner(self) -> InstallationReadinessReviewEvidenceV1:
        if self.operator_id != self.authenticated_operator_id:
            raise ValueError("operator ownership mismatch")
        if self.linkage and self.candidate_record_id != self.linkage.candidate_record_id:
            raise ValueError("candidate linkage mismatch")
        return self


def review_id_for(*, operator_id: str, candidate_record_id: str,
                  receipt_fingerprint: FingerprintV1 | None, observed_at: str) -> str:
    receipt = receipt_fingerprint.value if receipt_fingerprint else "missing"
    name = f"{operator_id}\0{candidate_record_id}\0{receipt}\0{observed_at}"
    return str(uuid.uuid5(REVIEW_NAMESPACE, name))


def review_fingerprint(value: InstallationReadinessReviewV1 | dict[str, Any]) -> FingerprintV1:
    return _fingerprint("atlas:installation-readiness-review:v1",
                        _without(value, "review_fingerprint"))


def audit_evidence_fingerprint(
    value: InstallationReadinessReviewAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return _fingerprint("atlas:installation-readiness-review-audit-evidence:v1",
                        _without(value, "evidence_fingerprint"))


def operator_fingerprint(operator_id: str) -> FingerprintV1:
    return _fingerprint("atlas:installation-readiness-review-operator:v1", operator_id)


def _expected_summary_identities(
    linkage: InstallationReadinessReviewLinkageV1,
) -> tuple[tuple[str, FingerprintV1], ...]:
    return (
        (linkage.candidate_record_id, linkage.candidate_record_fingerprint),
        (linkage.approval_intent_id, linkage.approval_intent_fingerprint),
        (linkage.agent_request_id, linkage.agent_validation_fingerprint),
        (linkage.execution_request_id, linkage.execution_request_fingerprint),
        (linkage.dispatch_envelope_id, linkage.dispatch_envelope_fingerprint),
        (linkage.intake_record_id, linkage.intake_record_fingerprint),
        (linkage.simulated_delivery_id, linkage.simulated_delivery_fingerprint),
        (linkage.intake_request_id, linkage.dormant_preparation_fingerprint),
        (linkage.delivery_preparation_id, linkage.preparation_fingerprint),
        (linkage.preflight_id, linkage.preflight_fingerprint),
        (linkage.enablement_id, linkage.enablement_fingerprint),
        (linkage.send_attempt_id, linkage.v031_send_receipt_fingerprint),
        (linkage.v032_admission_id, linkage.v032_admission_fingerprint),
        (linkage.v033_receipt_id, linkage.v033_receipt_fingerprint),
    )


def _canonical_blockers(values: set[str]) -> tuple[str, ...]:
    return tuple(value for value in BLOCKER_ORDER if value in values)


def create_installation_readiness_review(
    evidence: InstallationReadinessReviewEvidenceV1, *, correlation_id: str,
) -> InstallationReadinessReviewResponseV1:
    blockers = set(evidence.blockers)
    states = {item.evidence_state for item in evidence.evidence}
    for state, blocker in (("missing", "missing_evidence"),
                           ("expired", "expired_evidence"),
                           ("terminal", "terminal_ambiguity"),
                           ("unavailable", "agent_evidence_unavailable")):
        if state in states:
            blockers.add(blocker)
    observed = _instant(evidence.observed_at)
    if any(item.evidence_state == "current" and item.valid_until is not None
           and observed >= _instant(item.valid_until) for item in evidence.evidence):
        blockers.add("stale_evidence")
    if evidence.home_assistant or not evidence.installation_capability_supported:
        blockers.add("installation_capability_unsupported")
    complete = (evidence.linkage is not None
                and len(evidence.evidence) == len(EVIDENCE_ORDER)
                and all(item.evidence_state == "current" for item in evidence.evidence)
                and not blockers)
    if complete:
        blockers.add("execution_admission_not_defined")
        readiness: InstallationReadinessStateV1 = "readiness_gated"
    else:
        readiness = "blocked"
        if not blockers:
            blockers.add("invalid_evidence")
    ordered_blockers = _canonical_blockers(blockers)
    receipt = evidence.linkage.v033_receipt_fingerprint if evidence.linkage else None
    identifier = review_id_for(operator_id=evidence.operator_id,
                               candidate_record_id=evidence.candidate_record_id,
                               receipt_fingerprint=receipt,
                               observed_at=evidence.observed_at)
    review_raw: dict[str, Any] = {
        "review_id": identifier, "candidate_record_id": evidence.candidate_record_id,
        "operator_id": evidence.operator_id, "observed_at": evidence.observed_at,
        "readiness": readiness, "blockers": ordered_blockers,
        "evidence": evidence.evidence, "linkage": evidence.linkage,
    }
    review_seed = InstallationReadinessReviewV1.model_construct(
        **review_raw, review_fingerprint=_fingerprint("atlas:seed:v1", "review")
    )
    review_raw = review_seed.model_dump(mode="python")
    review_raw["review_fingerprint"] = review_fingerprint(review_seed)
    review = InstallationReadinessReviewV1.model_validate(review_raw)
    audit_raw: dict[str, Any] = {
        "review_id": review.review_id, "review_fingerprint": review.review_fingerprint,
        "candidate_record_id": review.candidate_record_id,
        "v033_receipt_fingerprint": receipt,
        "linkage_fingerprint": (evidence.linkage.v033_linkage_fingerprint
                                if evidence.linkage else None),
        "operator_fingerprint": operator_fingerprint(evidence.operator_id),
        "correlation_id": correlation_id, "observed_at": evidence.observed_at,
        "outcome": readiness, "blocker_codes": ordered_blockers,
    }
    audit_seed = InstallationReadinessReviewAuditEvidenceV1.model_construct(
        **audit_raw, evidence_fingerprint=_fingerprint("atlas:seed:v1", "audit")
    )
    audit_raw = audit_seed.model_dump(mode="python")
    audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(
        audit_seed
    )
    audit = InstallationReadinessReviewAuditEvidenceV1.model_validate(audit_raw)
    return InstallationReadinessReviewResponseV1(review=review, audit_evidence=audit)


def parse_response_json(payload: bytes | str) -> InstallationReadinessReviewResponseV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_RESPONSE_BYTES:
        raise StrictContractError("response exceeds 128 KiB")
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        if isinstance(value, dict):
            review = value.get("review")
            audit = value.get("audit_evidence")
            if isinstance(review, dict):
                review["blockers"] = tuple(review.get("blockers", ()))
                review["evidence"] = tuple(review.get("evidence", ()))
            if isinstance(audit, dict):
                audit["blocker_codes"] = tuple(audit.get("blocker_codes", ()))
        return InstallationReadinessReviewResponseV1.model_validate(value)
    except (TypeError, ValueError) as error:
        raise StrictContractError("invalid installation readiness response") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value
