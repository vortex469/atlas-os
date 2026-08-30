"""Closed immutable v0.35 execution-permission grant models and pure validation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.installation_dispatch_handoff.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_readiness_review.contract import (
    InstallationReadinessReviewLinkageV1,
    InstallationReadinessReviewResponseV1,
)
from app.installation_readiness_review.contract import (
    audit_evidence_fingerprint as v034_audit_fingerprint,
)
from app.installation_readiness_review.contract import (
    operator_fingerprint as v034_operator_fingerprint,
)
from app.installation_readiness_review.contract import (
    review_fingerprint as v034_review_fingerprint,
)
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 8 * 1024
MAX_CREATE_NESTING = 4
MAX_MODEL_BYTES = 64 * 1024
MAX_RESULT_BYTES = 128 * 1024
MAX_INHERITED_FRESHNESS_SECONDS = 30
CONFIRMATION_TEXT = (
    "I confirm that Atlas may record my permission for this exact evidence chain "
    "to be considered by a future execution-admission boundary. This does not "
    "install or execute anything."
)
PERMISSION = "installation.execution.permission.grant"
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UUID5 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_KEY = re.compile(r"[\x20-\x7e]{1,128}")


class StrictContractError(ValueError):
    pass


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


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _closed(value: Any, depth: int = 0, max_depth: int = 32) -> None:
    if depth > max_depth:
        raise ValueError("JSON nesting exceeds bound")
    if isinstance(value, str) and unicodedata.normalize("NFC", value) != value:
        raise ValueError("strings must be NFC")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _closed(key, depth + 1, max_depth)
            _closed(item, depth + 1, max_depth)
    elif isinstance(value, list):
        for item in value:
            _closed(item, depth + 1, max_depth)
    elif value is not None and not isinstance(value, (str, bool, int, float, dict)):
        raise ValueError("unsupported JSON value")


def canonical_json(value: Any, *, max_depth: int = 32) -> bytes:
    value = _json_value(value)
    _closed(value, max_depth=max_depth)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _fingerprint(domain: str, value: Any) -> FingerprintV1:
    value = hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=value
    )


def _without(value: BaseModel | dict[str, Any], field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


class _NonAuthorizing(ContractModel):
    evidence_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    docker_allowed: Literal[False] = False
    podman_allowed: Literal[False] = False
    shell_allowed: Literal[False] = False
    process_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class ExecutionPermissionGrantCreateV1(ContractModel):
    schema: Literal["execution-permission-grant-create-v1"] = (
        "execution-permission-grant-create-v1"
    )
    readiness_review_id: CanonicalUuid5
    readiness_review_fingerprint: FingerprintV1
    review_observed_at: UtcSecond
    confirmation_text: Literal[CONFIRMATION_TEXT]
    permission_scope: Literal["future_execution_admission_consideration_only"] = (
        "future_execution_admission_consideration_only"
    )
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bounded(self) -> ExecutionPermissionGrantCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 8 KiB")
        return self


class ExecutionPermissionGrantAuthorityContextV1(ContractModel):
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class ExecutionPermissionGrantLinkageV1(ContractModel):
    readiness_linkage: InstallationReadinessReviewLinkageV1
    v034_review_id: CanonicalUuid5
    v034_review_fingerprint: FingerprintV1
    v034_audit_evidence_fingerprint: FingerprintV1
    v034_operator_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantLinkageV1:
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("execution permission linkage fingerprint mismatch")
        return self


class ExecutionPermissionGrantV1(_NonAuthorizing):
    schema: Literal["execution-permission-grant-v1"] = "execution-permission-grant-v1"
    grant_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    permission_scope: Literal["future_execution_admission_consideration_only"] = (
        "future_execution_admission_consideration_only"
    )
    confirmation_text: Literal[CONFIRMATION_TEXT]
    confirmation_fingerprint: FingerprintV1
    linkage: ExecutionPermissionGrantLinkageV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    statement: Literal["operator_recorded_exact_non_executing_permission_evidence"] = (
        "operator_recorded_exact_non_executing_permission_evidence"
    )
    permission_evidence_recorded: Literal[True] = True
    grant_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantV1:
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=30):
            raise ValueError("grant expiry exceeds inherited 30-second freshness")
        if (
            self.candidate_record_id
            != self.linkage.readiness_linkage.candidate_record_id
        ):
            raise ValueError("grant candidate linkage mismatch")
        if self.linkage.v034_operator_fingerprint != v034_operator_fingerprint(
            self.operator_id
        ):
            raise ValueError("grant operator linkage mismatch")
        if self.confirmation_fingerprint != confirmation_fingerprint():
            raise ValueError("confirmation fingerprint mismatch")
        if self.grant_fingerprint != grant_fingerprint(self):
            raise ValueError("grant fingerprint mismatch")
        if len(canonical_json(self)) > MAX_MODEL_BYTES:
            raise ValueError("grant exceeds 64 KiB")
        return self


class ExecutionPermissionGrantStatusV1(ContractModel):
    schema: Literal["execution-permission-grant-status-v1"] = (
        "execution-permission-grant-status-v1"
    )
    grant_id: CanonicalUuid4
    grant_fingerprint: FingerprintV1
    observed_at: UtcSecond
    lifecycle: Literal["active", "expired"]
    permission_evidence_recorded: Literal[True] = True
    evidence_only: Literal[True] = True
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    status_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantStatusV1:
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("status fingerprint mismatch")
        return self


class ExecutionPermissionGrantIdempotencyV1(ContractModel):
    schema: Literal["execution-permission-grant-idempotency-v1"] = (
        "execution-permission-grant-idempotency-v1"
    )
    operator_id: OperatorId
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    raw_key_persisted: Literal[False] = False
    permanent: Literal[True] = True
    exact_duplicate_read_only: Literal[True] = True
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class ExecutionPermissionGrantReservationV1(ContractModel):
    schema: Literal["execution-permission-grant-reservation-v1"] = (
        "execution-permission-grant-reservation-v1"
    )
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    v034_review_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    grant_id: CanonicalUuid4
    reservation_state: Literal["permanent"] = "permanent"
    idempotency_subject_reserved: Literal[True] = True
    review_subject_reserved: Literal[True] = True
    releasable: Literal[False] = False
    reusable: Literal[False] = False
    expires: Literal[False] = False
    replay_allowed: Literal[False] = False
    reservation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("reservation fingerprint mismatch")
        return self


class ExecutionPermissionGrantAuditEvidenceV1(ContractModel):
    schema: Literal["execution-permission-grant-audit-evidence-v1"] = (
        "execution-permission-grant-audit-evidence-v1"
    )
    grant_id: CanonicalUuid4 | None
    candidate_record_id: CanonicalUuid4 | None
    operator_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1 | None
    idempotency_key_fingerprint: FingerprintV1 | None
    confirmation_fingerprint: FingerprintV1 | None
    v034_review_fingerprint: FingerprintV1 | None
    linkage_fingerprint: FingerprintV1 | None
    grant_fingerprint: FingerprintV1 | None
    correlation_id: CorrelationId
    occurred_at: UtcSecond
    outcome: Literal["recorded", "exact_duplicate", "rejected", "unavailable"]
    evidence_only: Literal[True] = True
    execution_attempted: Literal[False] = False
    dispatch_attempted: Literal[False] = False
    agent_invoked: Literal[False] = False
    worker_started: Literal[False] = False
    workflow_started: Literal[False] = False
    process_started: Literal[False] = False
    mutation_attempted: Literal[False] = False
    retry_attempted: Literal[False] = False
    replay_attempted: Literal[False] = False
    evidence_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantAuditEvidenceV1:
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("audit evidence fingerprint mismatch")
        return self


class ExecutionPermissionGrantRedactedErrorV1(ContractModel):
    schema: Literal["execution-permission-grant-error-v1"] = (
        "execution-permission-grant-error-v1"
    )
    error_code: Literal[
        "malformed",
        "unauthenticated",
        "unauthorized",
        "not_found",
        "confirmation_mismatch",
        "not_readiness_gated",
        "expired",
        "conflict",
        "quota_exceeded",
        "unavailable",
    ]
    safe_message: Literal["Execution permission evidence could not be recorded."] = (
        "Execution permission evidence could not be recorded."
    )
    correlation_id: CorrelationId
    redacted: Literal[True] = True
    retryable: Literal[False] = False
    execution_admission_granted: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class ExecutionPermissionGrantResultV1(_NonAuthorizing):
    disposition: Literal["recorded", "exact_duplicate", "rejected", "unavailable"]
    grant: ExecutionPermissionGrantV1 | None
    status: ExecutionPermissionGrantStatusV1 | None
    audit_evidence: ExecutionPermissionGrantAuditEvidenceV1 | None
    error: ExecutionPermissionGrantRedactedErrorV1 | None

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantResultV1:
        success = self.disposition in {"recorded", "exact_duplicate"}
        if success and (
            self.grant is None
            or self.status is None
            or self.audit_evidence is None
            or self.error is not None
        ):
            raise ValueError(
                "successful result requires grant, status, audit, and no error"
            )
        if not success and (
            self.grant is not None or self.status is not None or self.error is None
        ):
            raise ValueError(
                "failed result requires one redacted error and no grant/status"
            )
        if success and (
            self.audit_evidence.outcome != self.disposition
            or self.status.grant_id != self.grant.grant_id
        ):
            raise ValueError("successful result binding mismatch")
        if len(canonical_json(self)) > MAX_RESULT_BYTES:
            raise ValueError("result exceeds 128 KiB")
        return self


class ExecutionPermissionGrantValidationInputV1(ContractModel):
    """Injected P1-only facts; no reader, store, reservation, or I/O."""

    operator_id: OperatorId
    authority: ExecutionPermissionGrantAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: ExecutionPermissionGrantCreateV1
    readiness_response: InstallationReadinessReviewResponseV1
    idempotency_key: str
    home_assistant: bool = False

    @model_validator(mode="after")
    def exact(self) -> ExecutionPermissionGrantValidationInputV1:
        review = self.readiness_response.review
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or review.operator_id != self.operator_id
        ):
            raise ValueError("operator ownership mismatch")
        if _KEY.fullmatch(self.idempotency_key) is None:
            raise ValueError("invalid idempotency key")
        if self.home_assistant or review.readiness != "readiness_gated":
            raise ValueError("review is not readiness gated")
        if review.candidate_record_id != self.candidate_record_id:
            raise ValueError("readiness review candidate mismatch")
        if (
            review.review_id != self.create.readiness_review_id
            or review.review_fingerprint != self.create.readiness_review_fingerprint
            or review.observed_at != self.create.review_observed_at
        ):
            raise ValueError("readiness review binding mismatch")
        recorded, observed = (
            _instant(self.authority.request_received_at),
            _instant(review.observed_at),
        )
        if observed > recorded or recorded - observed > timedelta(seconds=30):
            raise ValueError("readiness review is stale or from the future")
        if any(item.evidence_state != "current" for item in review.evidence):
            raise ValueError("readiness evidence is not current")
        if any(
            item.valid_until is not None and recorded >= _instant(item.valid_until)
            for item in review.evidence
        ):
            raise ValueError("readiness evidence is expired")
        return self


def confirmation_fingerprint() -> FingerprintV1:
    value = hashlib.sha256(
        b"atlas:execution-permission-confirmation:v1\0" + CONFIRMATION_TEXT.encode()
    ).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=value
    )


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    if _KEY.fullmatch(raw_key) is None:
        raise ValueError("invalid idempotency key")
    value = hashlib.sha256(
        b"atlas:execution-permission-grant-idempotency:v1\0"
        + operator_id.encode()
        + b"\0"
        + raw_key.encode()
    ).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=value
    )


def request_fingerprint(
    *,
    operator_id: str,
    candidate_record_id: str,
    create: ExecutionPermissionGrantCreateV1,
    idempotency_fingerprint: FingerprintV1,
) -> FingerprintV1:
    return _fingerprint(
        "atlas:execution-permission-grant-request:v1",
        {
            "operator_id": operator_id,
            "candidate_record_id": candidate_record_id,
            "create": create,
            "idempotency_key_fingerprint": idempotency_fingerprint,
        },
    )


def linkage_fingerprint(
    value: ExecutionPermissionGrantLinkageV1 | dict[str, Any],
) -> FingerprintV1:
    return _fingerprint(
        "atlas:execution-permission-grant-linkage:v1",
        _without(value, "linkage_fingerprint"),
    )


def grant_fingerprint(
    value: ExecutionPermissionGrantV1 | dict[str, Any],
) -> FingerprintV1:
    return _fingerprint(
        "atlas:execution-permission-grant:v1", _without(value, "grant_fingerprint")
    )


def status_fingerprint(
    value: ExecutionPermissionGrantStatusV1 | dict[str, Any],
) -> FingerprintV1:
    return _fingerprint(
        "atlas:execution-permission-grant-status:v1",
        _without(value, "status_fingerprint"),
    )


def reservation_fingerprint(
    value: ExecutionPermissionGrantReservationV1 | dict[str, Any],
) -> FingerprintV1:
    return _fingerprint(
        "atlas:execution-permission-grant-reservation:v1",
        _without(value, "reservation_fingerprint"),
    )


def audit_evidence_fingerprint(
    value: ExecutionPermissionGrantAuditEvidenceV1 | dict[str, Any],
) -> FingerprintV1:
    return _fingerprint(
        "atlas:execution-permission-grant-audit-evidence:v1",
        _without(value, "evidence_fingerprint"),
    )


def build_linkage(
    response: InstallationReadinessReviewResponseV1,
) -> ExecutionPermissionGrantLinkageV1:
    review, audit = response.review, response.audit_evidence
    if review.linkage is None:
        raise ValueError("readiness review has no complete linkage")
    raw = {
        "readiness_linkage": review.linkage,
        "v034_review_id": review.review_id,
        "v034_review_fingerprint": v034_review_fingerprint(review),
        "v034_audit_evidence_fingerprint": v034_audit_fingerprint(audit),
        "v034_operator_fingerprint": v034_operator_fingerprint(review.operator_id),
    }
    seed = ExecutionPermissionGrantLinkageV1.model_construct(
        **raw, linkage_fingerprint=_fingerprint("atlas:seed:v1", "linkage")
    )
    return ExecutionPermissionGrantLinkageV1.model_validate(
        {**raw, "linkage_fingerprint": linkage_fingerprint(seed)}
    )


def build_grant(
    validation: ExecutionPermissionGrantValidationInputV1, *, grant_id: str
) -> tuple[
    ExecutionPermissionGrantV1,
    ExecutionPermissionGrantIdempotencyV1,
    ExecutionPermissionGrantReservationV1,
]:
    review = validation.readiness_response.review
    recorded = _instant(validation.authority.request_received_at)
    expiries = [
        recorded + timedelta(seconds=30),
        _instant(review.observed_at) + timedelta(seconds=30),
    ]
    expiries.extend(
        _instant(item.valid_until)
        for item in review.evidence
        if item.valid_until is not None
    )
    valid_until = min(expiries)
    if recorded >= valid_until:
        raise ValueError("inherited readiness evidence is expired")
    idem = idempotency_key_fingerprint(
        validation.operator_id, validation.idempotency_key
    )
    request = request_fingerprint(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        create=validation.create,
        idempotency_fingerprint=idem,
    )
    linkage = build_linkage(validation.readiness_response)
    raw = {
        "grant_id": grant_id,
        "operator_id": validation.operator_id,
        "candidate_record_id": validation.candidate_record_id,
        "recorded_at": validation.authority.request_received_at,
        "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "confirmation_text": validation.create.confirmation_text,
        "confirmation_fingerprint": confirmation_fingerprint(),
        "linkage": linkage,
        "idempotency_key_fingerprint": idem,
        "request_fingerprint": request,
    }
    seed = ExecutionPermissionGrantV1.model_construct(
        **raw, grant_fingerprint=_fingerprint("atlas:seed:v1", "grant")
    )
    grant = ExecutionPermissionGrantV1.model_validate(
        {**raw, "grant_fingerprint": grant_fingerprint(seed)}
    )
    idempotency = ExecutionPermissionGrantIdempotencyV1(
        operator_id=grant.operator_id,
        idempotency_key_fingerprint=idem,
        request_fingerprint=request,
    )
    reservation_raw = {
        "operator_id": grant.operator_id,
        "candidate_record_id": grant.candidate_record_id,
        "idempotency_key_fingerprint": idem,
        "v034_review_fingerprint": linkage.v034_review_fingerprint,
        "request_fingerprint": request,
        "grant_id": grant.grant_id,
    }
    reservation_seed = ExecutionPermissionGrantReservationV1.model_construct(
        **reservation_raw,
        reservation_fingerprint=_fingerprint("atlas:seed:v1", "reservation"),
    )
    reservation = ExecutionPermissionGrantReservationV1.model_validate(
        {
            **reservation_raw,
            "reservation_fingerprint": reservation_fingerprint(reservation_seed),
        }
    )
    return grant, idempotency, reservation


def derive_status(
    grant: ExecutionPermissionGrantV1, *, observed_at: str
) -> ExecutionPermissionGrantStatusV1:
    raw = {
        "grant_id": grant.grant_id,
        "grant_fingerprint": grant.grant_fingerprint,
        "observed_at": observed_at,
        "lifecycle": "active"
        if _instant(observed_at) < _instant(grant.valid_until)
        else "expired",
    }
    seed = ExecutionPermissionGrantStatusV1.model_construct(
        **raw, status_fingerprint=_fingerprint("atlas:seed:v1", "status")
    )
    return ExecutionPermissionGrantStatusV1.model_validate(
        {**raw, "status_fingerprint": status_fingerprint(seed)}
    )


def parse_create_json(payload: bytes | str) -> ExecutionPermissionGrantCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 8 KiB")
    try:
        return ExecutionPermissionGrantCreateV1.model_validate(
            json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        )
    except (TypeError, ValueError) as error:
        raise StrictContractError(
            "invalid execution permission grant request"
        ) from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value
