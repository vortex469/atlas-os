"""Closed immutable v0.36 installation execution admission models."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.execution_permission_grant.contract import (
    ExecutionPermissionGrantLinkageV1,
    ExecutionPermissionGrantStatusV1,
    ExecutionPermissionGrantV1,
    OperatorId,
    canonical_json,
)
from app.execution_permission_grant.contract import (
    grant_fingerprint as v035_grant_fingerprint,
)
from app.execution_permission_grant.contract import (
    status_fingerprint as v035_status_fingerprint,
)
from app.installation_dispatch_handoff.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 8192
MAX_CREATE_NESTING = 4
MAX_MODEL_BYTES = 65536
MAX_RESULT_BYTES = 131072
MAX_INHERITED_FRESHNESS_SECONDS = 30
PERMISSION = "installation.execution.admission.record"
READ_PERMISSION = "installation.execution.admission.read"
SCOPE = "future_installation_runner_consideration_only"
GRANT_SCOPE = "future_execution_admission_consideration_only"
SAFE_MESSAGE = "Installation execution admission evidence could not be recorded."
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_KEY = re.compile(r"[\x20-\x7e]{1,128}")

BlockerV1 = Literal[
    "missing_evidence", "ownership_mismatch", "linkage_mismatch",
    "fingerprint_mismatch", "invalid_evidence", "stale_evidence",
    "expired_evidence", "grant_not_active", "grant_scope_mismatch",
    "grant_unavailable", "permission_denied", "subject_reserved",
    "installation_capability_unsupported", "runner_binding_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER = (
    "missing_evidence", "ownership_mismatch", "linkage_mismatch",
    "fingerprint_mismatch", "invalid_evidence", "stale_evidence",
    "expired_evidence", "grant_not_active", "grant_scope_mismatch",
    "grant_unavailable", "permission_denied", "subject_reserved",
    "installation_capability_unsupported", "runner_binding_not_defined",
    "execution_start_boundary_not_defined",
)
ADMISSION_BLOCKERS: tuple[BlockerV1, ...] = (
    "runner_binding_not_defined", "execution_start_boundary_not_defined"
)


class StrictContractError(ValueError):
    pass


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _correlation(value: str) -> str:
    if not value.isascii() or _IDENTITY.fullmatch(value) is None:
        raise ValueError("invalid canonical correlation ID")
    return value


CorrelationId = Annotated[str, AfterValidator(_correlation)]


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _fp(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _without(value: BaseModel | dict[str, Any], field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


def _bounded(value: BaseModel, maximum: int = MAX_MODEL_BYTES) -> None:
    if len(canonical_json(value)) > maximum:
        raise ValueError("contract envelope exceeds bound")


def _ordered(blockers: tuple[BlockerV1, ...]) -> None:
    if len(blockers) != len(set(blockers)):
        raise ValueError("duplicate blockers")
    if [BLOCKER_ORDER.index(x) for x in blockers] != sorted(
        BLOCKER_ORDER.index(x) for x in blockers
    ):
        raise ValueError("blockers are not in canonical order")


class InstallationExecutionAdmissionCreateV1(ContractModel):
    schema: Literal["installation-execution-admission-create-v1"] = "installation-execution-admission-create-v1"
    permission_grant_id: CanonicalUuid4
    permission_grant_fingerprint: FingerprintV1
    grant_valid_until: UtcSecond
    requested_scope: Literal[SCOPE] = SCOPE
    runner_eligibility_claim: Literal["evidence_chain_only_no_runner_selected"] = "evidence_chain_only_no_runner_selected"
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bound(self) -> InstallationExecutionAdmissionCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 8 KiB")
        return self


class InstallationExecutionAdmissionAuthorityContextV1(ContractModel):
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = "core_trusted_whole_second_utc_clock"


class InstallationExecutionAdmissionLinkageV1(ContractModel):
    permission_grant_linkage: ExecutionPermissionGrantLinkageV1
    v035_grant_id: CanonicalUuid4
    v035_grant_fingerprint: FingerprintV1
    v035_status_fingerprint: FingerprintV1
    v035_request_fingerprint: FingerprintV1
    v035_confirmation_fingerprint: FingerprintV1
    v035_operator_fingerprint: FingerprintV1
    v034_review_fingerprint: FingerprintV1
    v034_audit_evidence_fingerprint: FingerprintV1
    chain_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionLinkageV1:
        source = self.permission_grant_linkage
        if (
            self.v035_operator_fingerprint != source.v034_operator_fingerprint
            or self.v034_review_fingerprint != source.v034_review_fingerprint
            or self.v034_audit_evidence_fingerprint
            != source.v034_audit_evidence_fingerprint
        ):
            raise ValueError("embedded permission grant linkage mismatch")
        if self.chain_fingerprint != chain_fingerprint(self):
            raise ValueError("admission chain fingerprint mismatch")
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("admission linkage fingerprint mismatch")
        _bounded(self)
        return self


class InstallationRunnerEligibilityV1(ContractModel):
    schema: Literal["installation-runner-eligibility-v1"] = "installation-runner-eligibility-v1"
    evaluation: Literal["evidence_chain_eligible"] = "evidence_chain_eligible"
    scope: Literal[SCOPE] = SCOPE
    evaluated_at: UtcSecond
    admission_gated: Literal[True] = True
    runner_selected: Literal[False] = False
    runner_registered: Literal[False] = False
    runner_available: Literal[False] = False
    runner_invocation_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    workflow_start_allowed: Literal[False] = False
    execution_start_boundary_defined: Literal[False] = False
    evidence_only: Literal[True] = True
    eligibility_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> InstallationRunnerEligibilityV1:
        if self.eligibility_fingerprint != eligibility_fingerprint(self):
            raise ValueError("runner eligibility fingerprint mismatch")
        _bounded(self)
        return self


class _NoAuthority(ContractModel):
    evidence_only: Literal[True] = True
    execution_start_allowed: Literal[False] = False
    runner_binding_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    docker_allowed: Literal[False] = False
    podman_allowed: Literal[False] = False
    shell_allowed: Literal[False] = False
    process_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class InstallationExecutionAdmissionV1(_NoAuthority):
    schema: Literal["installation-execution-admission-v1"] = "installation-execution-admission-v1"
    admission_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    readiness: Literal["admission_gated"] = "admission_gated"
    blockers: tuple[BlockerV1, ...] = ADMISSION_BLOCKERS
    scope: Literal[SCOPE] = SCOPE
    linkage: InstallationExecutionAdmissionLinkageV1
    runner_eligibility: InstallationRunnerEligibilityV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    admission_evidence_recorded: Literal[True] = True
    admission_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionV1:
        if self.blockers != ADMISSION_BLOCKERS:
            raise ValueError("admission-gated blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=30):
            raise ValueError("admission expiry exceeds inherited freshness")
        candidate = self.linkage.permission_grant_linkage.readiness_linkage.candidate_record_id
        if self.candidate_record_id != candidate:
            raise ValueError("admission candidate linkage mismatch")
        if self.runner_eligibility.evaluated_at != self.recorded_at:
            raise ValueError("eligibility time mismatch")
        if self.admission_fingerprint != admission_fingerprint(self):
            raise ValueError("admission fingerprint mismatch")
        _bounded(self)
        return self


class InstallationExecutionAdmissionStatusV1(ContractModel):
    schema: Literal["installation-execution-admission-status-v1"] = "installation-execution-admission-status-v1"
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    observed_at: UtcSecond
    lifecycle: Literal["active", "expired"]
    readiness: Literal["admission_gated"] = "admission_gated"
    evidence_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False
    status_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionStatusV1:
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("admission status fingerprint mismatch")
        _bounded(self)
        return self


class InstallationExecutionAdmissionIdempotencyV1(ContractModel):
    schema: Literal["installation-execution-admission-idempotency-v1"] = "installation-execution-admission-idempotency-v1"
    operator_id: OperatorId
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    raw_key_persisted: Literal[False] = False
    permanent: Literal[True] = True
    exact_duplicate_read_only: Literal[True] = True
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class InstallationExecutionAdmissionReservationV1(ContractModel):
    schema: Literal["installation-execution-admission-reservation-v1"] = "installation-execution-admission-reservation-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    idempotency_key_fingerprint: FingerprintV1
    v035_grant_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    admission_id: CanonicalUuid4
    reservation_state: Literal["permanent"] = "permanent"
    idempotency_subject_reserved: Literal[True] = True
    grant_subject_reserved: Literal[True] = True
    releasable: Literal[False] = False
    reusable: Literal[False] = False
    expires: Literal[False] = False
    replay_allowed: Literal[False] = False
    reservation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionReservationV1:
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("admission reservation fingerprint mismatch")
        _bounded(self)
        return self


class InstallationExecutionAdmissionAuditEvidenceV1(ContractModel):
    schema: Literal["installation-execution-admission-audit-evidence-v1"] = "installation-execution-admission-audit-evidence-v1"
    admission_id: CanonicalUuid4 | None
    candidate_record_id: CanonicalUuid4 | None
    operator_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1 | None
    idempotency_key_fingerprint: FingerprintV1 | None
    v035_grant_fingerprint: FingerprintV1 | None
    linkage_fingerprint: FingerprintV1 | None
    eligibility_fingerprint: FingerprintV1 | None
    admission_fingerprint: FingerprintV1 | None
    blocker_codes: tuple[BlockerV1, ...]
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
    def exact(self) -> InstallationExecutionAdmissionAuditEvidenceV1:
        _ordered(self.blocker_codes)
        if self.evidence_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("admission audit fingerprint mismatch")
        _bounded(self)
        return self


class InstallationExecutionAdmissionRedactedErrorV1(ContractModel):
    schema: Literal["installation-execution-admission-error-v1"] = "installation-execution-admission-error-v1"
    error_code: Literal["malformed", "unauthenticated", "unauthorized", "not_found", "not_eligible", "expired", "conflict", "quota_exceeded", "unavailable"]
    safe_message: Literal[SAFE_MESSAGE] = SAFE_MESSAGE
    blocker_codes: tuple[BlockerV1, ...]
    correlation_id: CorrelationId
    redacted: Literal[True] = True
    retryable: Literal[False] = False
    evidence_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionRedactedErrorV1:
        _ordered(self.blocker_codes)
        _bounded(self)
        return self


class InstallationExecutionAdmissionResultV1(ContractModel):
    disposition: Literal["recorded", "exact_duplicate", "rejected", "unavailable"]
    admission: InstallationExecutionAdmissionV1 | None
    status: InstallationExecutionAdmissionStatusV1 | None
    audit_evidence: InstallationExecutionAdmissionAuditEvidenceV1 | None
    error: InstallationExecutionAdmissionRedactedErrorV1 | None
    evidence_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    worker_allowed: Literal[False] = False
    workflow_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionResultV1:
        success = self.disposition in {"recorded", "exact_duplicate"}
        if success and (self.admission is None or self.status is None or self.audit_evidence is None or self.error is not None):
            raise ValueError("successful result requires admission, status, audit, and no error")
        if not success and (self.admission is not None or self.status is not None or self.error is None):
            raise ValueError("failed result requires one redacted error and no admission/status")
        if success and (self.audit_evidence.outcome != self.disposition or self.status.admission_id != self.admission.admission_id):
            raise ValueError("successful result binding mismatch")
        _bounded(self, MAX_RESULT_BYTES)
        return self


class InstallationExecutionAdmissionValidationInputV1(ContractModel):
    """Injected P1 facts only; no reader, store, reservation, or I/O."""

    operator_id: OperatorId
    authority: InstallationExecutionAdmissionAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: InstallationExecutionAdmissionCreateV1
    permission_grant: ExecutionPermissionGrantV1
    permission_grant_status: ExecutionPermissionGrantStatusV1
    idempotency_key: str
    home_assistant: bool = False

    @model_validator(mode="after")
    def exact(self) -> InstallationExecutionAdmissionValidationInputV1:
        grant, status = self.permission_grant, self.permission_grant_status
        now = _instant(self.authority.request_received_at)
        if self.operator_id != self.authority.authenticated_operator_id or grant.operator_id != self.operator_id:
            raise ValueError("operator ownership mismatch")
        if grant.candidate_record_id != self.candidate_record_id:
            raise ValueError("permission grant candidate linkage mismatch")
        if (self.create.permission_grant_id != grant.grant_id or self.create.permission_grant_fingerprint != grant.grant_fingerprint or self.create.grant_valid_until != grant.valid_until):
            raise ValueError("permission grant binding mismatch")
        if grant.permission_scope != GRANT_SCOPE:
            raise ValueError("permission grant scope mismatch")
        if (status.grant_id != grant.grant_id or status.grant_fingerprint != grant.grant_fingerprint or status.status_fingerprint != v035_status_fingerprint(status)):
            raise ValueError("permission grant status linkage mismatch")
        if status.lifecycle != "active":
            raise ValueError("permission grant is not active")
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if _KEY.fullmatch(self.idempotency_key) is None:
            raise ValueError("invalid idempotency key")
        observed, expiry = _instant(status.observed_at), _instant(grant.valid_until)
        if observed > now or now - observed > timedelta(seconds=30):
            raise ValueError("permission grant status is stale or from the future")
        if now >= expiry:
            raise ValueError("permission grant is expired")
        return self


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    if _KEY.fullmatch(raw_key) is None:
        raise ValueError("invalid idempotency key")
    digest = hashlib.sha256(b"atlas:installation-execution-admission-idempotency:v1\0" + operator_id.encode() + b"\0" + raw_key.encode()).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest)


def request_fingerprint(*, operator_id: str, candidate_record_id: str, create: InstallationExecutionAdmissionCreateV1, idempotency_fingerprint: FingerprintV1) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission-request:v1", {"operator_id": operator_id, "candidate_record_id": candidate_record_id, "create": create, "idempotency_key_fingerprint": idempotency_fingerprint})


def chain_fingerprint(value: InstallationExecutionAdmissionLinkageV1 | dict[str, Any]) -> FingerprintV1:
    raw = _without(value, "linkage_fingerprint")
    raw.pop("chain_fingerprint", None)
    return _fp("atlas:installation-execution-admission-chain:v1", raw)


def linkage_fingerprint(value: InstallationExecutionAdmissionLinkageV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission-linkage:v1", _without(value, "linkage_fingerprint"))


def eligibility_fingerprint(value: InstallationRunnerEligibilityV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-runner-eligibility:v1", _without(value, "eligibility_fingerprint"))


def admission_fingerprint(value: InstallationExecutionAdmissionV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission:v1", _without(value, "admission_fingerprint"))


def status_fingerprint(value: InstallationExecutionAdmissionStatusV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission-status:v1", _without(value, "status_fingerprint"))


def reservation_fingerprint(value: InstallationExecutionAdmissionReservationV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission-reservation:v1", _without(value, "reservation_fingerprint"))


def audit_evidence_fingerprint(value: InstallationExecutionAdmissionAuditEvidenceV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission-audit-evidence:v1", _without(value, "evidence_fingerprint"))


def operator_fingerprint(operator_id: str) -> FingerprintV1:
    return _fp("atlas:installation-execution-admission-operator:v1", operator_id)


def build_linkage(grant: ExecutionPermissionGrantV1, status: ExecutionPermissionGrantStatusV1) -> InstallationExecutionAdmissionLinkageV1:
    source = grant.linkage
    raw = {"permission_grant_linkage": source, "v035_grant_id": grant.grant_id, "v035_grant_fingerprint": v035_grant_fingerprint(grant), "v035_status_fingerprint": v035_status_fingerprint(status), "v035_request_fingerprint": grant.request_fingerprint, "v035_confirmation_fingerprint": grant.confirmation_fingerprint, "v035_operator_fingerprint": source.v034_operator_fingerprint, "v034_review_fingerprint": source.v034_review_fingerprint, "v034_audit_evidence_fingerprint": source.v034_audit_evidence_fingerprint}
    seed = InstallationExecutionAdmissionLinkageV1.model_construct(**raw, chain_fingerprint=_fp("atlas:seed:v1", "chain"), linkage_fingerprint=_fp("atlas:seed:v1", "linkage"))
    chain = chain_fingerprint(seed)
    seed = InstallationExecutionAdmissionLinkageV1.model_construct(**raw, chain_fingerprint=chain, linkage_fingerprint=_fp("atlas:seed:v1", "linkage"))
    return InstallationExecutionAdmissionLinkageV1.model_validate({**raw, "chain_fingerprint": chain, "linkage_fingerprint": linkage_fingerprint(seed)})


def build_admission(validation: InstallationExecutionAdmissionValidationInputV1, *, admission_id: str) -> tuple[InstallationExecutionAdmissionV1, InstallationExecutionAdmissionIdempotencyV1, InstallationExecutionAdmissionReservationV1]:
    recorded = _instant(validation.authority.request_received_at)
    valid_until = min(recorded + timedelta(seconds=30), _instant(validation.permission_grant.valid_until))
    if recorded >= valid_until:
        raise ValueError("inherited permission grant is expired")
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request = request_fingerprint(operator_id=validation.operator_id, candidate_record_id=validation.candidate_record_id, create=validation.create, idempotency_fingerprint=idem)
    linkage = build_linkage(validation.permission_grant, validation.permission_grant_status)
    eligibility_raw = {"evaluated_at": validation.authority.request_received_at}
    seed = InstallationRunnerEligibilityV1.model_construct(**eligibility_raw, eligibility_fingerprint=_fp("atlas:seed:v1", "eligibility"))
    eligibility = InstallationRunnerEligibilityV1.model_validate({**eligibility_raw, "eligibility_fingerprint": eligibility_fingerprint(seed)})
    raw = {"admission_id": admission_id, "operator_id": validation.operator_id, "candidate_record_id": validation.candidate_record_id, "recorded_at": validation.authority.request_received_at, "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"), "linkage": linkage, "runner_eligibility": eligibility, "idempotency_key_fingerprint": idem, "request_fingerprint": request}
    seed = InstallationExecutionAdmissionV1.model_construct(**raw, admission_fingerprint=_fp("atlas:seed:v1", "admission"))
    admission = InstallationExecutionAdmissionV1.model_validate({**raw, "admission_fingerprint": admission_fingerprint(seed)})
    idem_model = InstallationExecutionAdmissionIdempotencyV1(operator_id=validation.operator_id, idempotency_key_fingerprint=idem, request_fingerprint=request)
    reservation_raw = {"operator_id": validation.operator_id, "candidate_record_id": validation.candidate_record_id, "idempotency_key_fingerprint": idem, "v035_grant_fingerprint": admission.linkage.v035_grant_fingerprint, "request_fingerprint": request, "admission_id": admission_id}
    seed = InstallationExecutionAdmissionReservationV1.model_construct(**reservation_raw, reservation_fingerprint=_fp("atlas:seed:v1", "reservation"))
    reservation = InstallationExecutionAdmissionReservationV1.model_validate({**reservation_raw, "reservation_fingerprint": reservation_fingerprint(seed)})
    return admission, idem_model, reservation


def derive_status(admission: InstallationExecutionAdmissionV1, *, observed_at: str) -> InstallationExecutionAdmissionStatusV1:
    raw = {"admission_id": admission.admission_id, "admission_fingerprint": admission.admission_fingerprint, "observed_at": observed_at, "lifecycle": "active" if _instant(observed_at) < _instant(admission.valid_until) else "expired"}
    seed = InstallationExecutionAdmissionStatusV1.model_construct(**raw, status_fingerprint=_fp("atlas:seed:v1", "status"))
    return InstallationExecutionAdmissionStatusV1.model_validate({**raw, "status_fingerprint": status_fingerprint(seed)})


def parse_create_json(payload: bytes | str) -> InstallationExecutionAdmissionCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 8 KiB")
    try:
        decoded = raw.decode()
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        return InstallationExecutionAdmissionCreateV1.model_validate(json.loads(decoded, object_pairs_hook=_reject_duplicate_keys))
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid installation execution admission request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
