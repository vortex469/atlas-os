"""Closed immutable v0.52 queue claim/lease/acknowledgement boundary models.

This module is pure contract validation. It performs no persistence, queue I/O,
worker contact, Agent invocation, execution, installation, deployment,
publication, rollback, or mutation behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    SUCCESS_BLOCKERS as V051_SUCCESS_BLOCKERS,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    admission_record_fingerprint as v051_record_fingerprint,
)
from app.controlled_worker_queue_claim_lease_acknowledgement_admission.contract import (
    status_fingerprint as v051_status_fingerprint,
)
from app.execution_permission_grant.contract import (
    CanonicalUuid5,
    OperatorId,
    canonical_json,
)
from app.installation_execution_admission.contract import FingerprintV1
from app.installation_plan.contract import UtcSecond
from app.installation_targets.contract import CanonicalUuid4

MAX_CREATE_BYTES = 16 * 1024
MAX_CREATE_NESTING = 16
MAX_MODEL_BYTES = 192 * 1024
MAX_FRESHNESS_SECONDS = 30
PERMISSION = (
    "installation.execution.controlled_worker_queue_claim_lease_acknowledgement.evaluate"
)
SCOPE = "controlled_worker_queue_claim_lease_acknowledgement_only"
SAFE_MESSAGE = (
    "controlled worker queue claim lease acknowledgement request could not be completed"
)
_VISIBLE = re.compile(r"[\x20-\x7e]{16,128}")
_SAFE_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_BLOCKED_OPERATOR_ID = "blocked-evaluation"
_BLOCKED_CANDIDATE_ID = "00000000-0000-4000-8000-000000000000"
_CREDENTIAL_KEYS = frozenset(
    {"credential", "credentials", "secret", "token", "claim_token", "lease_token"}
)
_ENDPOINT_KEYS = frozenset({"endpoint", "endpoints", "url", "uri"})
_COMMAND_KEYS = frozenset(
    {"command", "commands", "cmd", "shell", "payload", "ack_handle"}
)
_AUTHORITY_FLAGS = frozenset(
    {
        "caller_supplied_credentials_allowed",
        "caller_supplied_endpoint_allowed",
        "caller_supplied_command_allowed",
        "caller_supplied_payload_allowed",
        "caller_supplied_queue_selector_allowed",
        "caller_supplied_claim_token_allowed",
        "caller_supplied_lease_token_allowed",
        "caller_supplied_acknowledgement_handle_allowed",
        "payload_schema_defined",
        "payload_constructed",
        "payload_serialized",
        "autonomous_queue_polling_allowed",
        "work_discovery_allowed",
        "queue_consume_allowed",
        "queue_requeue_allowed",
        "queue_mutation_allowed",
        "worker_activation_runtime_allowed",
        "worker_store_contact_allowed",
        "worker_runtime_contact_allowed",
        "worker_contact_allowed",
        "worker_start_admission_allowed",
        "worker_start_allowed",
        "worker_invocation_allowed",
        "agent_invocation_allowed",
        "execution_authorization_allowed",
        "execution_start_allowed",
        "process_execution_allowed",
        "store_contact_allowed",
        "runtime_contact_allowed",
        "dispatch_allowed",
        "retry_allowed",
        "resend_allowed",
        "scheduler_allowed",
        "workflow_start_allowed",
        "shell_execution_allowed",
        "provider_mutation_allowed",
        "repository_mutation_allowed",
        "in_guest_mutation_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "replay_bypass_allowed",
        "artifact_publication_allowed",
        "tag_push_allowed",
        "release_publication_allowed",
        "worker_start_admitted",
        "worker_started",
        "agent_invoked",
        "execution_started",
        "worker_start_admission_build_allowed",
        "execution_start_admission_build_allowed",
        "runtime_effect_allowed",
        "controlled_worker_queue_claim_lease_acknowledgement_recorded",
    }
)

BlockerV1 = Literal[
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v051_admission_not_active",
    "v051_admission_not_recorded",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "adapter_identity_mismatch",
    "reservation_before_effect_missing",
    "claim_receipt_mismatch",
    "lease_receipt_mismatch",
    "acknowledgement_receipt_mismatch",
    "replay_detected",
    "corrupt_adapter_evidence",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "caller_supplied_queue_selector",
    "caller_supplied_claim_token",
    "caller_supplied_lease_token",
    "caller_supplied_acknowledgement_handle",
    "unsupported_authority",
    "worker_activation_runtime_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_admission_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
]
BLOCKER_ORDER: tuple[BlockerV1, ...] = (
    "installation_capability_unsupported",
    "evidence_not_found",
    "ownership_mismatch",
    "permission_scope_missing",
    "v051_admission_not_active",
    "v051_admission_not_recorded",
    "linkage_mismatch",
    "fingerprint_mismatch",
    "inherited_limits_mismatch",
    "evidence_stale",
    "evidence_expired",
    "ambiguous_state",
    "adapter_identity_mismatch",
    "reservation_before_effect_missing",
    "claim_receipt_mismatch",
    "lease_receipt_mismatch",
    "acknowledgement_receipt_mismatch",
    "replay_detected",
    "corrupt_adapter_evidence",
    "caller_supplied_credential",
    "caller_supplied_endpoint",
    "caller_supplied_command",
    "caller_supplied_queue_selector",
    "caller_supplied_claim_token",
    "caller_supplied_lease_token",
    "caller_supplied_acknowledgement_handle",
    "unsupported_authority",
    "worker_activation_runtime_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_admission_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
)
SUCCESS_BLOCKERS: tuple[BlockerV1, ...] = (
    "worker_activation_runtime_not_defined",
    "store_contact_not_defined",
    "runtime_contact_not_defined",
    "worker_start_admission_not_defined",
    "worker_start_not_defined",
    "agent_invocation_not_defined",
    "execution_start_boundary_not_defined",
)


class StrictContractError(ValueError):
    pass


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _visible(value: str) -> str:
    if _VISIBLE.fullmatch(value) is None:
        raise ValueError("idempotency key must be 16-128 visible ASCII bytes")
    return value


def _safe_label(value: str) -> str:
    if _SAFE_LABEL.fullmatch(value) is None:
        raise ValueError("adapter label must be bounded safe ASCII")
    return value


VisibleIdempotencyKey = Annotated[str, AfterValidator(_visible)]
SafeAdapterLabel = Annotated[str, AfterValidator(_safe_label)]


def _instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def fingerprint(domain: str, value: Any) -> FingerprintV1:
    digest = hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()
    return FingerprintV1(
        algorithm="sha256", canonicalization="atlas-jcs-nfc-v1", value=digest
    )


def _without(value: BaseModel | dict[str, Any], field: str) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    raw.pop(field, None)
    return raw


def _bounded(value: BaseModel) -> None:
    if len(canonical_json(value)) > MAX_MODEL_BYTES:
        raise ValueError("contract envelope exceeds bound")


def _ordered(blockers: tuple[BlockerV1, ...]) -> None:
    if len(blockers) != len(set(blockers)):
        raise ValueError("v0.52 blockers contain duplicates")
    indexes = [BLOCKER_ORDER.index(item) for item in blockers]
    if indexes != sorted(indexes):
        raise ValueError("v0.52 blockers are not ordered")


class ClosedAuthorityV1(ContractModel):
    evidence_only: Literal[True] = True
    reference_only: Literal[True] = True
    caller_supplied_credentials_allowed: Literal[False] = False
    caller_supplied_endpoint_allowed: Literal[False] = False
    caller_supplied_command_allowed: Literal[False] = False
    caller_supplied_payload_allowed: Literal[False] = False
    caller_supplied_queue_selector_allowed: Literal[False] = False
    caller_supplied_claim_token_allowed: Literal[False] = False
    caller_supplied_lease_token_allowed: Literal[False] = False
    caller_supplied_acknowledgement_handle_allowed: Literal[False] = False
    credential_material_present: bool = False
    endpoint_material_present: bool = False
    command_material_present: bool = False
    payload_material_present: bool = False
    queue_selector_material_present: bool = False
    claim_token_material_present: bool = False
    lease_token_material_present: bool = False
    acknowledgement_handle_material_present: bool = False
    payload_schema_defined: Literal[False] = False
    payload_constructed: Literal[False] = False
    payload_serialized: Literal[False] = False
    payload_bytes: Literal[0] = 0
    autonomous_queue_polling_allowed: Literal[False] = False
    work_discovery_allowed: Literal[False] = False
    queue_consume_allowed: Literal[False] = False
    queue_requeue_allowed: Literal[False] = False
    queue_mutation_allowed: Literal[False] = False
    worker_activation_runtime_allowed: Literal[False] = False
    worker_store_contact_allowed: Literal[False] = False
    worker_runtime_contact_allowed: Literal[False] = False
    worker_contact_allowed: Literal[False] = False
    worker_start_admission_allowed: Literal[False] = False
    worker_start_allowed: Literal[False] = False
    worker_invocation_allowed: Literal[False] = False
    agent_invocation_allowed: Literal[False] = False
    execution_authorization_allowed: Literal[False] = False
    execution_start_allowed: Literal[False] = False
    process_execution_allowed: Literal[False] = False
    store_contact_allowed: Literal[False] = False
    runtime_contact_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    retry_allowed: Literal[False] = False
    resend_allowed: Literal[False] = False
    scheduler_allowed: Literal[False] = False
    workflow_start_allowed: Literal[False] = False
    shell_execution_allowed: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    in_guest_mutation_allowed: Literal[False] = False
    installation_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    rollback_allowed: Literal[False] = False
    replay_bypass_allowed: Literal[False] = False
    artifact_publication_allowed: Literal[False] = False
    tag_push_allowed: Literal[False] = False
    release_publication_allowed: Literal[False] = False
    worker_start_admitted: Literal[False] = False
    worker_started: Literal[False] = False
    agent_invoked: Literal[False] = False
    execution_started: Literal[False] = False


class ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1(ClosedAuthorityV1):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-create-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-create-v1"
    admission_id: CanonicalUuid5
    admission_record_fingerprint: FingerprintV1
    admission_status_fingerprint: FingerprintV1
    admission_valid_until: UtcSecond
    v050_prerequisite_record_fingerprint: FingerprintV1
    v050_prerequisite_status_fingerprint: FingerprintV1
    v049_admission_record_fingerprint: FingerprintV1
    v049_admission_status_fingerprint: FingerprintV1
    binding_subject_fingerprint: FingerprintV1
    worker_subject_fingerprint: FingerprintV1
    queue_item_reference_fingerprint: FingerprintV1
    inherited_limits_fingerprint: FingerprintV1
    adapter_identity_fingerprint: FingerprintV1
    expected_queue_subject_fingerprint: FingerprintV1
    expected_claim_receipt_fingerprint: FingerprintV1
    expected_lease_receipt_fingerprint: FingerprintV1
    expected_acknowledgement_receipt_fingerprint: FingerprintV1
    requested_scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def exact(self) -> ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1:
        if len(canonical_json(self, max_depth=MAX_CREATE_NESTING)) > MAX_CREATE_BYTES:
            raise ValueError("create request exceeds 16 KiB")
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1(
    ClosedAuthorityV1
):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-authority-context-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-authority-context-v1"
    authenticated_operator_id: OperatorId
    permission: Literal[PERMISSION]
    permission_verified: Literal[True] = True
    requested_scope: Literal[SCOPE] = SCOPE
    request_received_at: UtcSecond
    request_time_source: Literal["core_trusted_whole_second_utc_clock"] = (
        "core_trusted_whole_second_utc_clock"
    )


class ControlledWorkerQueueAdapterReceiptFactsV1(ContractModel):
    """Injected, redacted adapter facts; this model never contacts a queue."""

    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-adapter-receipt-facts-v1"
    ] = (
        "controlled-worker-queue-claim-lease-acknowledgement-adapter-receipt-facts-v1"
    )
    adapter_label: SafeAdapterLabel
    adapter_identity_fingerprint: FingerprintV1
    queue_subject_fingerprint: FingerprintV1
    claim_receipt_fingerprint: FingerprintV1
    lease_receipt_fingerprint: FingerprintV1
    acknowledgement_receipt_fingerprint: FingerprintV1
    reservation_before_effect: Literal[True] = True
    single_subject: Literal[True] = True
    terminal_acknowledgement: Literal[True] = True
    replay_detected: Literal[False] = False
    ambiguity_detected: Literal[False] = False
    corruption_detected: Literal[False] = False
    redacted: Literal[True] = True
    secret_free: Literal[True] = True
    observed_at: UtcSecond


class ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1(ClosedAuthorityV1):
    schema: Literal[
        "controlled-worker-queue-claim-lease-acknowledgement-evaluation-v1"
    ] = "controlled-worker-queue-claim-lease-acknowledgement-evaluation-v1"
    operator_id: OperatorId
    candidate_record_id: CanonicalUuid4
    evaluated_at: UtcSecond
    earliest_expiry: UtcSecond | None
    receipt_state: Literal["recorded", "blocked"]
    eligibility: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_recorded",
        "blocked",
    ]
    blockers: tuple[BlockerV1, ...]
    recognized_v051_admission_count: int
    recognized_adapter_receipt_count: int
    controlled_queue_claim_recorded: bool = False
    controlled_queue_lease_recorded: bool = False
    controlled_queue_acknowledgement_recorded: bool = False
    worker_start_admission_build_allowed: Literal[False] = False
    execution_start_admission_build_allowed: Literal[False] = False
    runtime_effect_allowed: Literal[False] = False
    controlled_worker_queue_claim_lease_acknowledgement_recorded: bool = False
    evaluation_fingerprint: FingerprintV1

    @model_validator(mode="after")
    def exact(self) -> ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1:
        _ordered(self.blockers)
        recorded = self.receipt_state == "recorded"
        if (
            self.eligibility
            == "controlled_worker_queue_claim_lease_acknowledgement_recorded"
        ) != recorded:
            raise ValueError("v0.52 eligibility mismatch")
        if self.recognized_v051_admission_count != (1 if recorded else 0):
            raise ValueError("v0.51 admission recognition count mismatch")
        if self.recognized_adapter_receipt_count != (1 if recorded else 0):
            raise ValueError("adapter receipt recognition count mismatch")
        receipt_flags = (
            self.controlled_queue_claim_recorded,
            self.controlled_queue_lease_recorded,
            self.controlled_queue_acknowledgement_recorded,
            self.controlled_worker_queue_claim_lease_acknowledgement_recorded,
        )
        if recorded and (self.blockers != SUCCESS_BLOCKERS or not all(receipt_flags)):
            raise ValueError("recorded v0.52 queue receipt shape mismatch")
        if not recorded and any(receipt_flags):
            raise ValueError("blocked v0.52 queue receipt shape mismatch")
        if self.evaluation_fingerprint != evaluation_fingerprint(self):
            raise ValueError("v0.52 evaluation fingerprint mismatch")
        _bounded(self)
        return self


class ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1(ContractModel):
    """Injected facts only; no store, runtime, queue, worker, endpoint, or I/O."""

    operator_id: OperatorId
    authority: ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1
    candidate_record_id: CanonicalUuid4
    create: ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1
    controlled_worker_queue_claim_lease_acknowledgement_admission: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1
    )
    controlled_worker_queue_claim_lease_acknowledgement_admission_status: (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1
    )
    adapter_receipt: ControlledWorkerQueueAdapterReceiptFactsV1
    idempotency_key: VisibleIdempotencyKey | None = None
    home_assistant: bool = False
    ambiguous_admission_count: int = 0
    ambiguous_adapter_receipt_count: int = 0
    boundary_enabled: Literal[False] = False

    @model_validator(mode="after")
    def exact(self) -> ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1:
        admission = self.controlled_worker_queue_claim_lease_acknowledgement_admission
        status = self.controlled_worker_queue_claim_lease_acknowledgement_admission_status
        receipt = self.adapter_receipt
        if self.home_assistant:
            raise ValueError("Home Assistant installation capability is unsupported")
        if self.ambiguous_admission_count or self.ambiguous_adapter_receipt_count:
            raise ValueError("ambiguous v0.52 prerequisite")
        if (
            self.operator_id != self.authority.authenticated_operator_id
            or admission.operator_id != self.operator_id
            or status.operator_id != self.operator_id
        ):
            raise ValueError("v0.52 ownership mismatch")
        if (
            admission.candidate_record_id != self.candidate_record_id
            or status.candidate_record_id != self.candidate_record_id
        ):
            raise ValueError("v0.52 candidate linkage mismatch")
        if (
            self.create.admission_id != admission.admission_id
            or self.create.admission_valid_until != admission.valid_until
            or status.admission_id != admission.admission_id
            or status.admission_record_fingerprint != admission.admission_record_fingerprint
        ):
            raise ValueError("v0.51 admission linkage mismatch")
        if (
            self.create.admission_record_fingerprint != admission.admission_record_fingerprint
            or self.create.admission_status_fingerprint != status.status_fingerprint
            or admission.admission_record_fingerprint
            != v051_record_fingerprint(admission)
            or status.status_fingerprint != v051_status_fingerprint(status)
        ):
            raise ValueError("v0.51 admission fingerprint mismatch")
        if status.lifecycle != "active":
            raise ValueError("v0.51 admission is not active")
        if (
            admission.lifecycle != "active"
            or admission.admission_state != "recorded"
            or admission.eligibility
            != "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
            or status.admission_state
            != "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
            or status.eligibility
            != "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
            or admission.blockers != V051_SUCCESS_BLOCKERS
            or status.blockers != V051_SUCCESS_BLOCKERS
            or not admission.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
            or not status.controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
        ):
            raise ValueError("v0.51 admission is not recorded")
        if (
            self.create.v050_prerequisite_record_fingerprint
            != admission.prerequisite_record_fingerprint
            or self.create.v050_prerequisite_status_fingerprint
            != admission.prerequisite_status_fingerprint
            or self.create.v049_admission_record_fingerprint
            != admission.v049_admission_record_fingerprint
            or self.create.v049_admission_status_fingerprint
            != admission.v049_admission_status_fingerprint
            or self.create.binding_subject_fingerprint
            != admission.binding_subject_fingerprint
            or self.create.worker_subject_fingerprint
            != admission.worker_subject_fingerprint
            or self.create.queue_item_reference_fingerprint
            != admission.queue_item_reference_fingerprint
        ):
            raise ValueError("v0.51 admission lineage fingerprint mismatch")
        if self.create.inherited_limits_fingerprint != admission.inherited_limits_fingerprint:
            raise ValueError("v0.51 admission inherited limits mismatch")
        if self.create.adapter_identity_fingerprint != receipt.adapter_identity_fingerprint:
            raise ValueError("adapter identity mismatch")
        if (
            self.create.expected_queue_subject_fingerprint
            != receipt.queue_subject_fingerprint
            or self.create.expected_queue_subject_fingerprint
            != queue_subject_fingerprint(admission)
        ):
            raise ValueError("v0.52 queue subject linkage mismatch")
        if not receipt.reservation_before_effect:
            raise ValueError("reservation before effect missing")
        if self.create.expected_claim_receipt_fingerprint != receipt.claim_receipt_fingerprint:
            raise ValueError("claim receipt mismatch")
        if self.create.expected_lease_receipt_fingerprint != receipt.lease_receipt_fingerprint:
            raise ValueError("lease receipt mismatch")
        if (
            self.create.expected_acknowledgement_receipt_fingerprint
            != receipt.acknowledgement_receipt_fingerprint
        ):
            raise ValueError("acknowledgement receipt mismatch")
        if receipt.replay_detected:
            raise ValueError("replay detected")
        if receipt.corruption_detected:
            raise ValueError("corrupt adapter evidence")
        if receipt.ambiguity_detected:
            raise ValueError("ambiguous adapter evidence")
        if (
            self.authority.credential_material_present
            or self.create.credential_material_present
            or self.authority.claim_token_material_present
            or self.create.claim_token_material_present
            or self.authority.lease_token_material_present
            or self.create.lease_token_material_present
        ):
            raise ValueError("caller supplied credential")
        if self.authority.endpoint_material_present or self.create.endpoint_material_present:
            raise ValueError("caller supplied endpoint")
        if (
            self.authority.command_material_present
            or self.create.command_material_present
            or self.authority.payload_material_present
            or self.create.payload_material_present
        ):
            raise ValueError("caller supplied command")
        if (
            self.authority.queue_selector_material_present
            or self.create.queue_selector_material_present
        ):
            raise ValueError("caller supplied queue selector")
        if (
            self.authority.acknowledgement_handle_material_present
            or self.create.acknowledgement_handle_material_present
        ):
            raise ValueError("caller supplied acknowledgement handle")
        if any(getattr(self.authority, flag, False) for flag in _AUTHORITY_FLAGS):
            raise ValueError("unsupported authority")
        now = _instant(self.authority.request_received_at)
        starts = (
            _instant(admission.recorded_at),
            _instant(status.evaluated_at),
            _instant(receipt.observed_at),
        )
        if any(
            value > now or now - value > timedelta(seconds=MAX_FRESHNESS_SECONDS)
            for value in starts
        ):
            raise ValueError("v0.52 evidence is stale or from the future")
        expiries = (_instant(admission.valid_until), _instant(status.valid_until))
        if any(now >= expiry for expiry in expiries):
            raise ValueError("v0.51 admission is expired")
        return self


def build_create(
    *,
    admission: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
    admission_status: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStatusV1,
    adapter_receipt: ControlledWorkerQueueAdapterReceiptFactsV1,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1:
    return ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1(
        admission_id=admission.admission_id,
        admission_record_fingerprint=admission.admission_record_fingerprint,
        admission_status_fingerprint=admission_status.status_fingerprint,
        admission_valid_until=admission.valid_until,
        v050_prerequisite_record_fingerprint=admission.prerequisite_record_fingerprint,
        v050_prerequisite_status_fingerprint=admission.prerequisite_status_fingerprint,
        v049_admission_record_fingerprint=admission.v049_admission_record_fingerprint,
        v049_admission_status_fingerprint=admission.v049_admission_status_fingerprint,
        binding_subject_fingerprint=admission.binding_subject_fingerprint,
        worker_subject_fingerprint=admission.worker_subject_fingerprint,
        queue_item_reference_fingerprint=admission.queue_item_reference_fingerprint,
        inherited_limits_fingerprint=admission.inherited_limits_fingerprint,
        adapter_identity_fingerprint=adapter_receipt.adapter_identity_fingerprint,
        expected_queue_subject_fingerprint=adapter_receipt.queue_subject_fingerprint,
        expected_claim_receipt_fingerprint=adapter_receipt.claim_receipt_fingerprint,
        expected_lease_receipt_fingerprint=adapter_receipt.lease_receipt_fingerprint,
        expected_acknowledgement_receipt_fingerprint=(
            adapter_receipt.acknowledgement_receipt_fingerprint
        ),
    )


def evaluate_controlled_worker_queue_claim_lease_acknowledgement(
    value: ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1 | dict[str, Any],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1:
    preflight_blocker = _preflight_blocker(value)
    if preflight_blocker is not None:
        return _blocked_evaluation(value, preflight_blocker)
    try:
        validation = (
            value
            if isinstance(value, ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1)
            else ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1.model_validate(
                value
            )
        )
    except (TypeError, ValueError) as error:
        return _blocked_evaluation(value, str(error))
    admission = validation.controlled_worker_queue_claim_lease_acknowledgement_admission
    status = validation.controlled_worker_queue_claim_lease_acknowledgement_admission_status
    earliest = min(
        _instant(admission.valid_until),
        _instant(status.valid_until),
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _evaluation(
        operator_id=validation.operator_id,
        candidate_record_id=validation.candidate_record_id,
        evaluated_at=validation.authority.request_received_at,
        earliest_expiry=earliest,
        receipt_state="recorded",
        eligibility="controlled_worker_queue_claim_lease_acknowledgement_recorded",
        blockers=SUCCESS_BLOCKERS,
    )


def _preflight_blocker(
    value: ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1 | dict[str, Any],
) -> BlockerV1 | None:
    if isinstance(value, BaseModel) or not isinstance(value, dict):
        return None
    if value.get("boundary_enabled"):
        return "unsupported_authority"
    if value.get("ambiguous_admission_count", 0) or value.get(
        "ambiguous_adapter_receipt_count", 0
    ):
        return "ambiguous_state"
    for section_name in ("create", "authority"):
        section = value.get(section_name)
        if not isinstance(section, dict):
            continue
        keys = set(section)
        if "queue_selector" in keys or section.get("queue_selector_material_present"):
            return "caller_supplied_queue_selector"
        if "claim_token" in keys or section.get("claim_token_material_present"):
            return "caller_supplied_claim_token"
        if "lease_token" in keys or section.get("lease_token_material_present"):
            return "caller_supplied_lease_token"
        if "acknowledgement_handle" in keys or section.get(
            "acknowledgement_handle_material_present"
        ):
            return "caller_supplied_acknowledgement_handle"
        if keys & _CREDENTIAL_KEYS or section.get("credential_material_present"):
            return "caller_supplied_credential"
        if keys & _ENDPOINT_KEYS or section.get("endpoint_material_present"):
            return "caller_supplied_endpoint"
        if (
            keys & _COMMAND_KEYS
            or section.get("command_material_present")
            or section.get("payload_material_present")
        ):
            return "caller_supplied_command"
        if any(section.get(flag) for flag in _AUTHORITY_FLAGS):
            return "unsupported_authority"
    receipt = value.get("adapter_receipt")
    if isinstance(receipt, dict):
        if receipt.get("replay_detected"):
            return "replay_detected"
        if receipt.get("corruption_detected"):
            return "corrupt_adapter_evidence"
        if receipt.get("ambiguity_detected"):
            return "ambiguous_state"
        if receipt.get("reservation_before_effect") is False:
            return "reservation_before_effect_missing"
    admission = value.get("controlled_worker_queue_claim_lease_acknowledgement_admission")
    status = value.get(
        "controlled_worker_queue_claim_lease_acknowledgement_admission_status"
    )
    if isinstance(admission, dict) and admission.get("lifecycle", "active") != "active":
        return "v051_admission_not_active"
    if isinstance(status, dict) and status.get("lifecycle", "active") != "active":
        return "v051_admission_not_active"
    if isinstance(admission, dict) and (
        admission.get("admission_state", "recorded") != "recorded"
        or admission.get(
            "eligibility",
            "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
        )
        != "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded"
        or admission.get(
            "controlled_worker_queue_claim_lease_acknowledgement_admission_recorded",
            True,
        )
        is not True
    ):
        return "v051_admission_not_recorded"
    keys = set(value)
    if "queue_selector" in keys:
        return "caller_supplied_queue_selector"
    if "claim_token" in keys:
        return "caller_supplied_claim_token"
    if "lease_token" in keys:
        return "caller_supplied_lease_token"
    if "acknowledgement_handle" in keys:
        return "caller_supplied_acknowledgement_handle"
    if keys & _CREDENTIAL_KEYS:
        return "caller_supplied_credential"
    if keys & _ENDPOINT_KEYS:
        return "caller_supplied_endpoint"
    if keys & _COMMAND_KEYS:
        return "caller_supplied_command"
    return None


def _evaluation(
    *,
    operator_id: str,
    candidate_record_id: str,
    evaluated_at: str,
    earliest_expiry: str | None,
    receipt_state: Literal["recorded", "blocked"],
    eligibility: Literal[
        "controlled_worker_queue_claim_lease_acknowledgement_recorded",
        "blocked",
    ],
    blockers: tuple[BlockerV1, ...],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1:
    recorded = receipt_state == "recorded"
    raw = {
        "operator_id": operator_id,
        "candidate_record_id": candidate_record_id,
        "evaluated_at": evaluated_at,
        "earliest_expiry": earliest_expiry,
        "receipt_state": receipt_state,
        "eligibility": eligibility,
        "blockers": blockers,
        "recognized_v051_admission_count": 1 if recorded else 0,
        "recognized_adapter_receipt_count": 1 if recorded else 0,
        "controlled_queue_claim_recorded": recorded,
        "controlled_queue_lease_recorded": recorded,
        "controlled_queue_acknowledgement_recorded": recorded,
        "controlled_worker_queue_claim_lease_acknowledgement_recorded": recorded,
    }
    seed = ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1.model_construct(
        **raw,
        evaluation_fingerprint=fingerprint("atlas:seed:v1", "evaluation"),
    )
    return ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1.model_validate(
        {**raw, "evaluation_fingerprint": evaluation_fingerprint(seed)}
    )


def _blocked_evaluation(
    value: ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1 | dict[str, Any],
    reason: str,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1:
    if isinstance(value, BaseModel):
        raw = value.model_dump(mode="python")
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        raw = {}
    authority = raw.get("authority") if isinstance(raw.get("authority"), dict) else {}
    operator_id = raw.get("operator_id") or authority.get("authenticated_operator_id")
    candidate_record_id = raw.get("candidate_record_id")
    return _evaluation(
        operator_id=operator_id or _BLOCKED_OPERATOR_ID,
        candidate_record_id=candidate_record_id or _BLOCKED_CANDIDATE_ID,
        evaluated_at=authority.get("request_received_at") or "1970-01-01T00:00:00Z",
        earliest_expiry=None,
        receipt_state="blocked",
        eligibility="blocked",
        blockers=(_blocker_from_reason(reason),),
    )


def _blocker_from_reason(reason: str) -> BlockerV1:
    lowered = reason.lower()
    if lowered in BLOCKER_ORDER:
        return lowered  # type: ignore[return-value]
    if "home assistant" in lowered or "unsupported capability" in lowered:
        return "installation_capability_unsupported"
    if "ownership" in lowered:
        return "ownership_mismatch"
    if "permission" in lowered:
        return "permission_scope_missing"
    if "not active" in lowered and "v0.51" in lowered:
        return "v051_admission_not_active"
    if "not recorded" in lowered and "v0.51" in lowered:
        return "v051_admission_not_recorded"
    if "linkage" in lowered or "subject" in lowered:
        return "linkage_mismatch"
    if "limits" in lowered:
        return "inherited_limits_mismatch"
    if "fingerprint" in lowered:
        return "fingerprint_mismatch"
    if "stale" in lowered or "future" in lowered:
        return "evidence_stale"
    if "expired" in lowered:
        return "evidence_expired"
    if "ambiguous" in lowered:
        return "ambiguous_state"
    if "adapter identity" in lowered:
        return "adapter_identity_mismatch"
    if "reservation before effect" in lowered:
        return "reservation_before_effect_missing"
    if "claim receipt" in lowered:
        return "claim_receipt_mismatch"
    if "lease receipt" in lowered:
        return "lease_receipt_mismatch"
    if "acknowledgement receipt" in lowered:
        return "acknowledgement_receipt_mismatch"
    if "replay" in lowered:
        return "replay_detected"
    if "corrupt" in lowered:
        return "corrupt_adapter_evidence"
    if "queue selector" in lowered:
        return "caller_supplied_queue_selector"
    if "claim token" in lowered:
        return "caller_supplied_claim_token"
    if "lease token" in lowered:
        return "caller_supplied_lease_token"
    if "acknowledgement handle" in lowered:
        return "caller_supplied_acknowledgement_handle"
    if "credential" in lowered:
        return "caller_supplied_credential"
    if "endpoint" in lowered:
        return "caller_supplied_endpoint"
    if "command" in lowered or "payload" in lowered:
        return "caller_supplied_command"
    if "unsupported authority" in lowered:
        return "unsupported_authority"
    return "evidence_not_found"


def evaluation_fingerprint(
    value: ControlledWorkerQueueClaimLeaseAcknowledgementEvaluationV1 | dict[str, Any],
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-evaluation:v1",
        _without(value, "evaluation_fingerprint"),
    )


def queue_subject_fingerprint(
    admission: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-queue-subject:v1",
        {
            "operator_id": admission.operator_id,
            "candidate_record_id": admission.candidate_record_id,
            "admission_id": admission.admission_id,
            "admission_record_fingerprint": admission.admission_record_fingerprint,
            "queue_item_reference_fingerprint": admission.queue_item_reference_fingerprint,
            "inherited_limits_fingerprint": admission.inherited_limits_fingerprint,
        },
    )


def adapter_identity_fingerprint(adapter_label: str) -> FingerprintV1:
    return fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-adapter-identity:v1",
        {"adapter_label": _safe_label(adapter_label)},
    )


def adapter_receipt_fingerprint(kind: str, value: Any) -> FingerprintV1:
    if kind not in {"claim", "lease", "acknowledgement"}:
        raise ValueError("unsupported adapter receipt kind")
    return fingerprint(
        f"atlas:controlled-worker-queue-claim-lease-acknowledgement-{kind}-receipt:v1",
        value,
    )


def build_adapter_receipt(
    *,
    admission: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionV1,
    adapter_label: str,
    observed_at: str,
) -> ControlledWorkerQueueAdapterReceiptFactsV1:
    adapter_fp = adapter_identity_fingerprint(adapter_label)
    subject_fp = queue_subject_fingerprint(admission)
    claim_fp = adapter_receipt_fingerprint(
        "claim",
        {
            "adapter_identity_fingerprint": adapter_fp,
            "queue_subject_fingerprint": subject_fp,
            "admission_record_fingerprint": admission.admission_record_fingerprint,
        },
    )
    lease_fp = adapter_receipt_fingerprint(
        "lease",
        {
            "adapter_identity_fingerprint": adapter_fp,
            "queue_subject_fingerprint": subject_fp,
            "claim_receipt_fingerprint": claim_fp,
        },
    )
    acknowledgement_fp = adapter_receipt_fingerprint(
        "acknowledgement",
        {
            "adapter_identity_fingerprint": adapter_fp,
            "queue_subject_fingerprint": subject_fp,
            "lease_receipt_fingerprint": lease_fp,
        },
    )
    return ControlledWorkerQueueAdapterReceiptFactsV1(
        adapter_label=_safe_label(adapter_label),
        adapter_identity_fingerprint=adapter_fp,
        queue_subject_fingerprint=subject_fp,
        claim_receipt_fingerprint=claim_fp,
        lease_receipt_fingerprint=lease_fp,
        acknowledgement_receipt_fingerprint=acknowledgement_fp,
        observed_at=observed_at,
    )


def parse_create_json(
    data: str | bytes,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1:
    if isinstance(data, bytes):
        if len(data) > MAX_CREATE_BYTES:
            raise StrictContractError("create request exceeds 16 KiB")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise StrictContractError("create request must be utf-8") from error
    else:
        text = data
    if len(text.encode("utf-8")) > MAX_CREATE_BYTES:
        raise StrictContractError("create request exceeds 16 KiB")
    if unicodedata.normalize("NFC", text) != text:
        raise StrictContractError("create request must be NFC normalized")
    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as error:
        raise StrictContractError("create request must be strict json") from error
    try:
        return ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1.model_validate(raw)
    except ValueError as error:
        raise StrictContractError("create request failed closed validation") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key}")
        seen.add(key)
        result[key] = value
    return result
