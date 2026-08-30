"""Closed immutable v0.37 runner binding plan models and pure validation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.execution_permission_grant.contract import OperatorId, canonical_json
from app.installation_execution_admission.contract import (
    FingerprintV1,
    InstallationExecutionAdmissionLinkageV1,
    InstallationExecutionAdmissionStatusV1,
    InstallationExecutionAdmissionV1,
)
from app.installation_execution_admission.contract import (
    admission_fingerprint as v036_admission_fingerprint,
)
from app.installation_execution_admission.contract import (
    status_fingerprint as v036_status_fingerprint,
)
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 4096
MAX_CREATE_NESTING = 8
MAX_MODEL_BYTES = 65536
MAX_RESULT_BYTES = 65536
MAX_FRESHNESS_SECONDS = 30
PERMISSION = "installation.runner.binding.plan.record"
READ_PERMISSION = "installation.runner.binding.plan.read"
SCOPE = "installation_runner_binding_plan_only"
SAFE_MESSAGE = "runner binding plan request could not be completed"
CPU_MILLIS_MAX, MEMORY_BYTES_MAX, PIDS_MAX = 1000, 536870912, 64
WALL_TIME_SECONDS_MAX, OUTPUT_BYTES_MAX = 900, 1048576
EPHEMERAL_BYTES_MAX = 268435456
_VISIBLE = re.compile(r"[\x20-\x7e]{1,128}")

BlockerV1 = Literal[
    "authentication_required", "permission_required", "owner_mismatch",
    "evidence_missing", "evidence_linkage_mismatch",
    "evidence_fingerprint_mismatch", "evidence_stale", "evidence_expired",
    "execution_admission_not_active",
    "execution_admission_not_admission_gated", "runner_reference_missing",
    "runner_reference_owner_mismatch", "runner_reference_ineligible",
    "runner_reference_expired", "runner_identity_mismatch",
    "runner_capability_mismatch", "limits_mismatch",
    "home_assistant_unsupported", "runner_not_bound",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "authentication_required", "permission_required", "owner_mismatch",
    "evidence_missing", "evidence_linkage_mismatch",
    "evidence_fingerprint_mismatch", "evidence_stale", "evidence_expired",
    "execution_admission_not_active",
    "execution_admission_not_admission_gated", "runner_reference_missing",
    "runner_reference_owner_mismatch", "runner_reference_ineligible",
    "runner_reference_expired", "runner_identity_mismatch",
    "runner_capability_mismatch", "limits_mismatch",
    "home_assistant_unsupported", "runner_not_bound",
    "execution_start_boundary_not_defined",
)
PLAN_BLOCKERS: tuple[BlockerV1, ...] = (
    "runner_not_bound", "execution_start_boundary_not_defined"
)


class StrictContractError(ValueError):
    pass


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _visible(value: str) -> str:
    if _VISIBLE.fullmatch(value) is None:
        raise ValueError("value must be visible ASCII with 1-128 bytes")
    return value


VisibleAscii128 = Annotated[str, AfterValidator(_visible)]


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _fp(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(
        domain.encode() + b"\0" + canonical_json(value)
    ).hexdigest()
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


class RunnerBindingPlanCreateV1(ContractModel):
    schema: Literal["runner-binding-plan-create-v1"] = "runner-binding-plan-create-v1"
    admission_id: CanonicalUuid4
    admission_fingerprint: FingerprintV1
    admission_valid_until: UtcSecond
    runner_reference_id: CanonicalUuid4
    runner_reference_fingerprint: FingerprintV1
    limits_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE
    evidence_only: Literal[True] = True
    runner_binding_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 4096 bytes")
        return self


class RunnerBindingPlanAuthorityContextV1(ContractModel):
    schema: Literal["runner-binding-plan-authority-context-v1"] = "runner-binding-plan-authority-context-v1"
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = "core_trusted_whole_second_utc_clock"


class RunnerSandboxLimitsV1(ContractModel):
    profile: Literal["atlas-installation-confined-v1"] = "atlas-installation-confined-v1"
    privileged: Literal[False] = False
    privilege_escalation: Literal[False] = False
    host_pid_namespace: Literal[False] = False
    host_ipc_namespace: Literal[False] = False
    host_network_namespace: Literal[False] = False
    host_devices: Literal[False] = False
    capabilities_drop_all: Literal[True] = True
    seccomp_required: Literal[True] = True
    apparmor_required: Literal[True] = True


class RunnerResourceLimitsV1(ContractModel):
    cpu_millis_max: Literal[CPU_MILLIS_MAX] = CPU_MILLIS_MAX
    memory_bytes_max: Literal[MEMORY_BYTES_MAX] = MEMORY_BYTES_MAX
    pids_max: Literal[PIDS_MAX] = PIDS_MAX
    wall_time_seconds_max: Literal[WALL_TIME_SECONDS_MAX] = WALL_TIME_SECONDS_MAX
    output_bytes_max: Literal[OUTPUT_BYTES_MAX] = OUTPUT_BYTES_MAX


class RunnerNetworkLimitsV1(ContractModel):
    mode: Literal["none"] = "none"
    ingress_allowed: Literal[False] = False
    egress_allowed: Literal[False] = False
    dns_allowed: Literal[False] = False
    image_pull_allowed: Literal[False] = False
    allowed_endpoint_fingerprints: tuple[()] = ()


class RunnerFilesystemLimitsV1(ContractModel):
    root_filesystem_read_only: Literal[True] = True
    host_mounts_allowed: Literal[False] = False
    repository_mount_allowed: Literal[False] = False
    guest_mount_allowed: Literal[False] = False
    internal_path_disclosure_allowed: Literal[False] = False
    ephemeral_workspace_allowed: Literal[True] = True
    ephemeral_workspace_bytes_max: Literal[EPHEMERAL_BYTES_MAX] = EPHEMERAL_BYTES_MAX
    writable_scope: Literal["ephemeral_workspace_only"] = "ephemeral_workspace_only"


class RunnerBindingLimitsV1(ContractModel):
    schema: Literal["runner-binding-limits-v1"] = "runner-binding-limits-v1"
    sandbox: RunnerSandboxLimitsV1
    resources: RunnerResourceLimitsV1
    network: RunnerNetworkLimitsV1
    filesystem: RunnerFilesystemLimitsV1
    limits_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingLimitsV1:
        if self.limits_fingerprint != limits_fingerprint(self):
            raise ValueError("runner binding limits fingerprint mismatch")
        _bounded(self)
        return self


class RunnerReferenceV1(ContractModel):
    schema: Literal["installation-runner-reference-v1"] = "installation-runner-reference-v1"
    runner_reference_id: CanonicalUuid4
    owner_operator_id: OperatorId
    runner_kind: Literal["isolated_installation_runner"] = "isolated_installation_runner"
    trust_domain: Literal["atlas-installation"] = "atlas-installation"
    scope: Literal[SCOPE] = SCOPE
    eligibility: Literal["eligible_for_binding_plan_only"] = "eligible_for_binding_plan_only"
    identity_fingerprint: FingerprintV1
    capability_profile_fingerprint: FingerprintV1
    limits: RunnerBindingLimitsV1
    valid_from: UtcSecond
    valid_until: UtcSecond
    reference_fingerprint: FingerprintV1
    registered: Literal[False] = False
    available: Literal[False] = False
    contacted: Literal[False] = False
    reserved: Literal[False] = False
    invocation_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> RunnerReferenceV1:
        start, expiry = _instant(self.valid_from), _instant(self.valid_until)
        if not start < expiry <= start + timedelta(seconds=MAX_FRESHNESS_SECONDS):
            raise ValueError("runner reference expiry exceeds freshness bound")
        if self.reference_fingerprint != runner_reference_fingerprint(self):
            raise ValueError("runner reference fingerprint mismatch")
        _bounded(self)
        return self


class RunnerBindingPlanLinkageV1(ContractModel):
    schema: Literal["runner-binding-plan-linkage-v1"] = "runner-binding-plan-linkage-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    execution_admission_linkage: InstallationExecutionAdmissionLinkageV1
    v020_v035_chain_fingerprint: FingerprintV1
    readiness_review_fingerprint: FingerprintV1
    permission_grant_fingerprint: FingerprintV1
    execution_admission_id: CanonicalUuid4
    execution_admission_fingerprint: FingerprintV1
    execution_admission_status_fingerprint: FingerprintV1
    runner_reference_id: CanonicalUuid4
    runner_reference_fingerprint: FingerprintV1
    runner_identity_fingerprint: FingerprintV1
    runner_capability_profile_fingerprint: FingerprintV1
    limits_fingerprint: FingerprintV1
    linkage_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanLinkageV1:
        source = self.execution_admission_linkage
        if (
            self.v020_v035_chain_fingerprint != source.chain_fingerprint
            or self.readiness_review_fingerprint != source.v034_review_fingerprint
            or self.permission_grant_fingerprint != source.v035_grant_fingerprint
        ):
            raise ValueError("embedded execution admission linkage mismatch")
        if self.linkage_fingerprint != linkage_fingerprint(self):
            raise ValueError("runner binding plan linkage fingerprint mismatch")
        _bounded(self)
        return self


class _NoAuthority(ContractModel):
    evidence_only: Literal[True] = True
    runner_registered: Literal[False] = False
    runner_contacted: Literal[False] = False
    runner_reserved: Literal[False] = False
    runner_bound: Literal[False] = False
    runner_binding_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
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


class RunnerBindingPlanV1(_NoAuthority):
    schema: Literal["runner-binding-plan-v1"] = "runner-binding-plan-v1"
    plan_id: CanonicalUuid4
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    recorded_at: UtcSecond
    valid_until: UtcSecond
    record_state: Literal["recorded"] = "recorded"
    lifecycle: Literal["active"] = "active"
    eligibility: Literal["binding_planned"] = "binding_planned"
    blockers: tuple[BlockerV1, ...] = PLAN_BLOCKERS
    linkage: RunnerBindingPlanLinkageV1
    runner_reference: RunnerReferenceV1
    limits: RunnerBindingLimitsV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    plan_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanV1:
        if self.blockers != PLAN_BLOCKERS:
            raise ValueError("binding-planned blockers must remain fixed")
        recorded, expiry = _instant(self.recorded_at), _instant(self.valid_until)
        if not recorded < expiry <= recorded + timedelta(seconds=30):
            raise ValueError("runner binding plan expiry exceeds freshness bound")
        if (
            self.operator_id != self.linkage.operator_id
            or self.operator_id != self.runner_reference.owner_operator_id
            or self.candidate_record_id != self.linkage.candidate_record_id
            or self.runner_reference.runner_reference_id != self.linkage.runner_reference_id
            or self.runner_reference.reference_fingerprint != self.linkage.runner_reference_fingerprint
            or self.limits != self.runner_reference.limits
            or self.limits.limits_fingerprint != self.linkage.limits_fingerprint
        ):
            raise ValueError("runner binding plan ownership or linkage mismatch")
        if self.plan_fingerprint != plan_fingerprint(self):
            raise ValueError("runner binding plan fingerprint mismatch")
        _bounded(self)
        return self


class RunnerBindingPlanStatusV1(ContractModel):
    schema: Literal["runner-binding-plan-status-v1"] = "runner-binding-plan-status-v1"
    plan_id: CanonicalUuid4
    observed_at: UtcSecond
    lifecycle: Literal["active", "expired"]
    eligibility: Literal["binding_planned"] = "binding_planned"
    blockers: tuple[BlockerV1, ...] = PLAN_BLOCKERS
    status_fingerprint: FingerprintV1
    evidence_only: Literal[True] = True
    runner_bound: Literal[False] = False
    execution_authorized: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanStatusV1:
        if self.blockers != PLAN_BLOCKERS:
            raise ValueError("binding-planned status blockers must remain fixed")
        if self.status_fingerprint != status_fingerprint(self):
            raise ValueError("runner binding plan status fingerprint mismatch")
        _bounded(self)
        return self


class RunnerBindingPlanIdempotencyV1(ContractModel):
    schema: Literal["runner-binding-plan-idempotency-v1"] = "runner-binding-plan-idempotency-v1"
    operator_id: OperatorId
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    raw_key_persisted: Literal[False] = False
    retained_forever: Literal[True] = True
    exact_duplicate_read_only: Literal[True] = True
    retry_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


class RunnerBindingPlanReservationV1(ContractModel):
    schema: Literal["runner-binding-plan-reservation-v1"] = "runner-binding-plan-reservation-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    execution_admission_fingerprint: FingerprintV1
    runner_reference_fingerprint: FingerprintV1
    limits_fingerprint: FingerprintV1
    subject_fingerprint: FingerprintV1
    idempotency_key_fingerprint: FingerprintV1
    request_fingerprint: FingerprintV1
    plan_id: CanonicalUuid4
    reserved_at: UtcSecond
    reservation_state: Literal["permanent"] = "permanent"
    retained_forever: Literal[True] = True
    releasable: Literal[False] = False
    replay_allowed: Literal[False] = False
    reservation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanReservationV1:
        if self.subject_fingerprint != subject_fingerprint(self):
            raise ValueError("runner binding plan subject fingerprint mismatch")
        if self.reservation_fingerprint != reservation_fingerprint(self):
            raise ValueError("runner binding plan reservation fingerprint mismatch")
        _bounded(self)
        return self


class RunnerBindingPlanAuditEvidenceV1(ContractModel):
    schema: Literal["runner-binding-plan-audit-evidence-v1"] = "runner-binding-plan-audit-evidence-v1"
    event: Literal["runner_binding_plan_recorded", "runner_binding_plan_read"]
    outcome: Literal["recorded", "exact_duplicate", "read", "blocked"]
    operator_fingerprint: FingerprintV1
    candidate_record_fingerprint: FingerprintV1
    plan_fingerprint: FingerprintV1 | None
    correlation_fingerprint: FingerprintV1
    occurred_at: UtcSecond
    audit_fingerprint: FingerprintV1
    evidence_only: Literal[True] = True
    runner_contact_attempted: Literal[False] = False
    runner_binding_attempted: Literal[False] = False
    worker_start_attempted: Literal[False] = False
    execution_start_attempted: Literal[False] = False
    dispatch_attempted: Literal[False] = False
    agent_invocation_attempted: Literal[False] = False
    workflow_start_attempted: Literal[False] = False
    process_execution_attempted: Literal[False] = False
    mutation_attempted: Literal[False] = False
    effect_attempted: Literal[False] = False
    replay_attempted: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanAuditEvidenceV1:
        if self.audit_fingerprint != audit_evidence_fingerprint(self):
            raise ValueError("runner binding plan audit fingerprint mismatch")
        _bounded(self)
        return self


class RunnerBindingPlanRedactedErrorV1(ContractModel):
    schema: Literal["runner-binding-plan-redacted-error-v1"] = "runner-binding-plan-redacted-error-v1"
    error_code: Literal["malformed", "unauthenticated", "unauthorized", "not_found", "not_eligible", "expired", "conflict", "quota_exceeded", "unavailable"]
    message: Literal[SAFE_MESSAGE] = SAFE_MESSAGE
    correlation_fingerprint: FingerprintV1
    retryable: Literal[False] = False
    redacted: Literal[True] = True
    evidence_only: Literal[True] = True
    runner_binding_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanRedactedErrorV1:
        _bounded(self)
        return self


class RunnerBindingPlanResultV1(ContractModel):
    schema: Literal["runner-binding-plan-result-v1"] = "runner-binding-plan-result-v1"
    disposition: Literal["recorded", "exact_duplicate", "read", "blocked"]
    plan: RunnerBindingPlanV1 | None
    status: RunnerBindingPlanStatusV1 | None
    audit_evidence: RunnerBindingPlanAuditEvidenceV1 | None
    error: RunnerBindingPlanRedactedErrorV1 | None
    evidence_only: Literal[True] = True
    runner_registration_allowed: Literal[False] = False
    runner_contact_allowed: Literal[False] = False
    runner_reservation_allowed: Literal[False] = False
    runner_binding_allowed: Literal[False] = False
    runner_bound: Literal[False] = False
    execution_start_allowed: Literal[False] = False
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
    def exact(self) -> RunnerBindingPlanResultV1:
        success = self.disposition in {"recorded", "exact_duplicate", "read"}
        if success and (self.plan is None or self.status is None or self.audit_evidence is None or self.error is not None):
            raise ValueError("successful result requires plan, status, and audit")
        if not success and (self.plan is not None or self.status is not None or self.error is None):
            raise ValueError("blocked result requires one redacted error")
        if success and self.audit_evidence.outcome != self.disposition:
            raise ValueError("result audit disposition mismatch")
        _bounded(self, MAX_RESULT_BYTES)
        return self


class RunnerBindingPlanCollectionV1(ContractModel):
    schema: Literal["runner-binding-plan-collection-v1"] = "runner-binding-plan-collection-v1"
    plans: tuple[RunnerBindingPlanResultV1, ...]
    evidence_only: Literal[True] = True
    execution_authorized: Literal[False] = False
    mutation_allowed: Literal[False] = False


class RunnerBindingPlanValidationInputV1(ContractModel):
    """Injected P1 facts only; no reader, store, reservation, or I/O."""

    operator_id: OperatorId
    authority: RunnerBindingPlanAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: RunnerBindingPlanCreateV1
    execution_admission: InstallationExecutionAdmissionV1
    execution_admission_status: InstallationExecutionAdmissionStatusV1
    runner_reference: RunnerReferenceV1
    idempotency_key: VisibleAscii128
    home_assistant: bool = False

    @model_validator(mode="after")
    def exact(self) -> RunnerBindingPlanValidationInputV1:
        admission, status, runner = self.execution_admission, self.execution_admission_status, self.runner_reference
        now = _instant(self.authority.request_received_at)
        if self.operator_id != self.authority.authenticated_operator_id or admission.operator_id != self.operator_id or runner.owner_operator_id != self.operator_id:
            raise ValueError("runner binding plan ownership mismatch")
        if admission.candidate_record_id != self.candidate_record_id or self.create.admission_id != admission.admission_id or self.create.admission_fingerprint != admission.admission_fingerprint or self.create.admission_valid_until != admission.valid_until:
            raise ValueError("execution admission linkage mismatch")
        if status.admission_id != admission.admission_id or status.admission_fingerprint != admission.admission_fingerprint or status.status_fingerprint != v036_status_fingerprint(status):
            raise ValueError("execution admission status linkage mismatch")
        if status.lifecycle != "active":
            raise ValueError("execution admission is not active")
        if status.readiness != "admission_gated":
            raise ValueError("execution admission is not admission_gated")
        if self.create.runner_reference_id != runner.runner_reference_id or self.create.runner_reference_fingerprint != runner.reference_fingerprint or self.create.limits_fingerprint != runner.limits.limits_fingerprint:
            raise ValueError("runner reference or limits binding mismatch")
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        instants = (_instant(admission.recorded_at), _instant(status.observed_at), _instant(runner.valid_from))
        if any(value > now or now - value > timedelta(seconds=30) for value in instants):
            raise ValueError("runner binding evidence is stale or from the future")
        if now >= _instant(admission.valid_until) or now >= _instant(runner.valid_until):
            raise ValueError("runner binding evidence is expired")
        return self


def sandbox_limits_fingerprint(value: RunnerSandboxLimitsV1) -> FingerprintV1:
    return _fp("atlas:runner-sandbox-limits:v1", value)


def resource_limits_fingerprint(value: RunnerResourceLimitsV1) -> FingerprintV1:
    return _fp("atlas:runner-resource-limits:v1", value)


def network_limits_fingerprint(value: RunnerNetworkLimitsV1) -> FingerprintV1:
    return _fp("atlas:runner-network-limits:v1", value)


def filesystem_limits_fingerprint(value: RunnerFilesystemLimitsV1) -> FingerprintV1:
    return _fp("atlas:runner-filesystem-limits:v1", value)


def limits_fingerprint(value: RunnerBindingLimitsV1 | dict[str, Any]) -> FingerprintV1:
    raw = _without(value, "limits_fingerprint")
    return _fp("atlas:runner-binding-limits:v1", {
        "limits": raw,
        "sandbox_fingerprint": sandbox_limits_fingerprint(RunnerSandboxLimitsV1.model_validate(raw["sandbox"], strict=False)),
        "resource_fingerprint": resource_limits_fingerprint(RunnerResourceLimitsV1.model_validate(raw["resources"], strict=False)),
        "network_fingerprint": network_limits_fingerprint(RunnerNetworkLimitsV1.model_validate(raw["network"], strict=False)),
        "filesystem_fingerprint": filesystem_limits_fingerprint(RunnerFilesystemLimitsV1.model_validate(raw["filesystem"], strict=False)),
    })


def runner_reference_fingerprint(value: RunnerReferenceV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:installation-runner-reference:v1", _without(value, "reference_fingerprint"))


def linkage_fingerprint(value: RunnerBindingPlanLinkageV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:runner-binding-plan-linkage:v1", _without(value, "linkage_fingerprint"))


def idempotency_key_fingerprint(operator_id: str, raw_key: str) -> FingerprintV1:
    key = _visible(raw_key)
    digest = hashlib.sha256(b"atlas:runner-binding-plan-idempotency:v1\0" + operator_id.encode() + b"\0" + key.encode()).hexdigest()
    return FingerprintV1(algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest)


def request_fingerprint(*, operator_id: str, candidate_record_id: str, create: RunnerBindingPlanCreateV1, request_received_at: str, idempotency_fingerprint: FingerprintV1) -> FingerprintV1:
    return _fp("atlas:runner-binding-plan-request:v1", {"operator_id": operator_id, "candidate_record_id": candidate_record_id, "create": create, "request_received_at": request_received_at, "idempotency_key_fingerprint": idempotency_fingerprint})


def plan_fingerprint(value: RunnerBindingPlanV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:runner-binding-plan:v1", _without(value, "plan_fingerprint"))


def status_fingerprint(value: RunnerBindingPlanStatusV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:runner-binding-plan-status:v1", _without(value, "status_fingerprint"))


def subject_fingerprint(value: RunnerBindingPlanReservationV1 | dict[str, Any]) -> FingerprintV1:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return _fp("atlas:runner-binding-plan-subject:v1", {key: raw[key] for key in ("operator_id", "candidate_record_id", "execution_admission_fingerprint", "runner_reference_fingerprint", "limits_fingerprint")})


def reservation_fingerprint(value: RunnerBindingPlanReservationV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:runner-binding-plan-reservation:v1", _without(value, "reservation_fingerprint"))


def audit_evidence_fingerprint(value: RunnerBindingPlanAuditEvidenceV1 | dict[str, Any]) -> FingerprintV1:
    return _fp("atlas:runner-binding-plan-audit:v1", _without(value, "audit_fingerprint"))


def opaque_fingerprint(domain: str, value: str) -> FingerprintV1:
    return _fp(domain, value)


def build_limits() -> RunnerBindingLimitsV1:
    raw = {"sandbox": RunnerSandboxLimitsV1(), "resources": RunnerResourceLimitsV1(), "network": RunnerNetworkLimitsV1(), "filesystem": RunnerFilesystemLimitsV1()}
    seed = RunnerBindingLimitsV1.model_construct(**raw, limits_fingerprint=_fp("atlas:seed:v1", "limits"))
    return RunnerBindingLimitsV1.model_validate({**raw, "limits_fingerprint": limits_fingerprint(seed)})


def build_runner_reference(*, runner_reference_id: str, owner_operator_id: str, identity_fingerprint: FingerprintV1, capability_profile_fingerprint: FingerprintV1, limits: RunnerBindingLimitsV1, valid_from: str, valid_until: str) -> RunnerReferenceV1:
    raw = {"runner_reference_id": runner_reference_id, "owner_operator_id": owner_operator_id, "identity_fingerprint": identity_fingerprint, "capability_profile_fingerprint": capability_profile_fingerprint, "limits": limits, "valid_from": valid_from, "valid_until": valid_until}
    seed = RunnerReferenceV1.model_construct(**raw, reference_fingerprint=_fp("atlas:seed:v1", "reference"))
    return RunnerReferenceV1.model_validate({**raw, "reference_fingerprint": runner_reference_fingerprint(seed)})


def build_linkage(admission: InstallationExecutionAdmissionV1, status: InstallationExecutionAdmissionStatusV1, runner: RunnerReferenceV1) -> RunnerBindingPlanLinkageV1:
    source = admission.linkage
    raw = {"operator_id": admission.operator_id, "candidate_record_id": admission.candidate_record_id, "execution_admission_linkage": source, "v020_v035_chain_fingerprint": source.chain_fingerprint, "readiness_review_fingerprint": source.v034_review_fingerprint, "permission_grant_fingerprint": source.v035_grant_fingerprint, "execution_admission_id": admission.admission_id, "execution_admission_fingerprint": v036_admission_fingerprint(admission), "execution_admission_status_fingerprint": v036_status_fingerprint(status), "runner_reference_id": runner.runner_reference_id, "runner_reference_fingerprint": runner.reference_fingerprint, "runner_identity_fingerprint": runner.identity_fingerprint, "runner_capability_profile_fingerprint": runner.capability_profile_fingerprint, "limits_fingerprint": runner.limits.limits_fingerprint}
    seed = RunnerBindingPlanLinkageV1.model_construct(**raw, linkage_fingerprint=_fp("atlas:seed:v1", "linkage"))
    return RunnerBindingPlanLinkageV1.model_validate({**raw, "linkage_fingerprint": linkage_fingerprint(seed)})


def build_plan(validation: RunnerBindingPlanValidationInputV1, *, plan_id: str) -> tuple[RunnerBindingPlanV1, RunnerBindingPlanIdempotencyV1, RunnerBindingPlanReservationV1]:
    recorded = _instant(validation.authority.request_received_at)
    valid_until = min(recorded + timedelta(seconds=30), _instant(validation.execution_admission.valid_until), _instant(validation.runner_reference.valid_until))
    if recorded >= valid_until:
        raise ValueError("runner binding evidence is expired")
    idem = idempotency_key_fingerprint(validation.operator_id, validation.idempotency_key)
    request = request_fingerprint(operator_id=validation.operator_id, candidate_record_id=validation.candidate_record_id, create=validation.create, request_received_at=validation.authority.request_received_at, idempotency_fingerprint=idem)
    linkage = build_linkage(validation.execution_admission, validation.execution_admission_status, validation.runner_reference)
    raw = {"plan_id": plan_id, "operator_id": validation.operator_id, "candidate_record_id": validation.candidate_record_id, "recorded_at": validation.authority.request_received_at, "valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ"), "linkage": linkage, "runner_reference": validation.runner_reference, "limits": validation.runner_reference.limits, "idempotency_key_fingerprint": idem, "request_fingerprint": request}
    seed = RunnerBindingPlanV1.model_construct(**raw, plan_fingerprint=_fp("atlas:seed:v1", "plan"))
    plan = RunnerBindingPlanV1.model_validate({**raw, "plan_fingerprint": plan_fingerprint(seed)})
    idempotency = RunnerBindingPlanIdempotencyV1(operator_id=validation.operator_id, idempotency_key_fingerprint=idem, request_fingerprint=request)
    reservation_raw = {"operator_id": validation.operator_id, "candidate_record_id": validation.candidate_record_id, "execution_admission_fingerprint": plan.linkage.execution_admission_fingerprint, "runner_reference_fingerprint": plan.linkage.runner_reference_fingerprint, "limits_fingerprint": plan.linkage.limits_fingerprint, "idempotency_key_fingerprint": idem, "request_fingerprint": request, "plan_id": plan_id, "reserved_at": validation.authority.request_received_at}
    seed = RunnerBindingPlanReservationV1.model_construct(**reservation_raw, subject_fingerprint=_fp("atlas:seed:v1", "subject"), reservation_fingerprint=_fp("atlas:seed:v1", "reservation"))
    subject = subject_fingerprint(seed)
    seed = RunnerBindingPlanReservationV1.model_construct(**reservation_raw, subject_fingerprint=subject, reservation_fingerprint=_fp("atlas:seed:v1", "reservation"))
    reservation = RunnerBindingPlanReservationV1.model_validate({**reservation_raw, "subject_fingerprint": subject, "reservation_fingerprint": reservation_fingerprint(seed)})
    return plan, idempotency, reservation


def derive_status(plan: RunnerBindingPlanV1, *, observed_at: str) -> RunnerBindingPlanStatusV1:
    raw = {"plan_id": plan.plan_id, "observed_at": observed_at, "lifecycle": "active" if _instant(observed_at) < _instant(plan.valid_until) else "expired"}
    seed = RunnerBindingPlanStatusV1.model_construct(**raw, status_fingerprint=_fp("atlas:seed:v1", "status"))
    return RunnerBindingPlanStatusV1.model_validate({**raw, "status_fingerprint": status_fingerprint(seed)})


def parse_create_json(payload: bytes | str) -> RunnerBindingPlanCreateV1:
    raw = payload.encode() if isinstance(payload, str) else payload
    if len(raw) > MAX_CREATE_BYTES:
        raise StrictContractError("runner binding plan request exceeds 4096 bytes")
    try:
        decoded = raw.decode()
        if unicodedata.normalize("NFC", decoded) != decoded:
            raise ValueError("request must be NFC")
        return RunnerBindingPlanCreateV1.model_validate(json.loads(decoded, object_pairs_hook=_reject_duplicate_keys))
    except (UnicodeError, TypeError, ValueError) as error:
        raise StrictContractError("invalid runner binding plan request") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
