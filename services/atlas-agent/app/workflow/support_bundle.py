"""Bounded, allow-listed operational support evidence bundles."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.workflow.recovery_diagnostic import WorkflowRecoveryDiagnostic

SUPPORT_BUNDLE_SCHEMA = "atlas-operational-support-bundle-v1"
SUPPORT_BUNDLE_DIGEST_PREFIX = "operational-support-bundle-digest-v1"
MAX_TRANSITIONS = 64
MAX_AUDIT_REFERENCES = 32
MAX_TEXT_LENGTH = 256


class SupportBundleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SupportBundleMetadata(SupportBundleModel):
    schema_version: Literal["atlas-operational-support-bundle-v1"]
    generated_at: datetime
    agent_version: str
    workflow_id: str


class SupportBundleWorkflow(SupportBundleModel):
    candidate_id: str | None
    planning_session_id: str | None
    effect_kind: str
    execution_intent: str | None
    target_label: str | None


class SupportBundleApproval(SupportBundleModel):
    decision_status: str
    presentation_state: str
    actionable: bool
    expires_at: datetime | None


class SupportBundleApprovals(SupportBundleModel):
    preparation: SupportBundleApproval | None
    operational_action: SupportBundleApproval | None


class SupportBundleTransition(SupportBundleModel):
    sequence: int
    state: str
    occurred_at: datetime


class SupportBundleLifecycle(SupportBundleModel):
    availability: str
    request_id: str | None
    request_digest: str | None
    agent_execution_stage: str | None
    core_ledger_state: str | None
    transitions: tuple[SupportBundleTransition, ...]
    transition_sequence_valid: bool | None
    barrier_crossed: bool
    barrier_crossing_count: int
    provider_operation_captured: bool
    provider_operation_capture_count: int
    dispatch_status: str | None
    dispatch_result_known: bool
    provider_operation_reference: str | None
    verification_status: str | None
    observed_state: str | None
    observed_health: str | None
    terminal: bool


class ServiceAvailability(StrEnum):
    AVAILABLE = "available"


class SupportBundleServiceIdentity(SupportBundleModel):
    service_name: Literal["atlas-agent"]
    status: ServiceAvailability
    version: str


class CapabilityParityStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"


class SupportBundleCapabilityBoundary(SupportBundleModel):
    production_tuples: tuple[str, ...]
    agent_execution_intents: tuple[str, ...]
    parity_status: CapabilityParityStatus


class AuditEventType(StrEnum):
    EXECUTION_BLOCKED = "execution_blocked_by_agent_gate"
    DISPATCH_SUBMITTED = "authenticated_dispatch_submitted"
    SUBMISSION_OUTCOME_UNKNOWN = "submission_outcome_unknown"
    CORE_LIFECYCLE_OBSERVED = "core_lifecycle_observed"
    VERIFICATION_PENDING = "verification_pending"
    VERIFICATION_SUCCEEDED = "verification_succeeded"
    VERIFICATION_FAILED = "verification_failed"
    TARGET_REPLACED = "target_replaced"
    OUTCOME_UNKNOWN = "outcome_unknown"
    FAILED = "failed"


class SupportBundleAuditReference(SupportBundleModel):
    event_type: AuditEventType


class SupportBundleTruncation(SupportBundleModel):
    transitions_truncated: bool
    audit_references_truncated: bool
    text_fields_truncated: tuple[str, ...]


class SupportBundleIntegrity(SupportBundleModel):
    digest: str
    purpose: Literal["integrity_and_correlation_only"]


class OperationalSupportBundle(SupportBundleModel):
    applicable: bool
    metadata: SupportBundleMetadata
    workflow: SupportBundleWorkflow
    approvals: SupportBundleApprovals
    lifecycle: SupportBundleLifecycle
    diagnostic: WorkflowRecoveryDiagnostic
    service_health: tuple[SupportBundleServiceIdentity, ...]
    capability_boundary: SupportBundleCapabilityBoundary
    audit_refs: tuple[SupportBundleAuditReference, ...]
    truncation: SupportBundleTruncation
    integrity: SupportBundleIntegrity


class ApprovalFacts(Protocol):
    decision_status: str
    presentation_state: str
    actionable: bool
    expires_at: datetime | None


class TransitionFacts(Protocol):
    sequence: int
    state: str
    occurred_at: datetime


class LifecycleBundleFacts(Protocol):
    applicable: bool
    workflow_id: str
    candidate_id: str | None
    planning_session_id: str | None
    effect_kind: str
    execution_intent: str | None
    target_label: str | None
    preparation_approval: ApprovalFacts | None
    action_approval: ApprovalFacts | None
    availability: str
    action_request_id: str | None
    request_digest: str | None
    agent_execution_stage: str | None
    core_record_state: str | None
    transitions: tuple[TransitionFacts, ...]
    transition_sequence_valid: bool | None
    barrier_crossed: bool
    barrier_crossing_count: int
    provider_operation_captured: bool
    provider_operation_capture_count: int
    dispatch_status: str | None
    provider_operation_reference: str | None
    verification_status: str | None
    observed_state: str | None
    observed_health: str | None
    terminal: bool


def build_operational_support_bundle(
    *,
    lifecycle: LifecycleBundleFacts,
    diagnostic: WorkflowRecoveryDiagnostic,
    generated_at: datetime,
    agent_version: str,
    operational_execution_intents: frozenset[str],
    production_tuples: tuple[str, ...],
    audit_event_types: tuple[str, ...],
) -> OperationalSupportBundle:
    """Build one in-memory bundle from existing sanitized projections only."""

    truncated_fields: list[str] = []

    def bounded(value: str | None, field: str) -> str | None:
        if value is None or len(value) <= MAX_TEXT_LENGTH:
            return value
        truncated_fields.append(field)
        return value[:MAX_TEXT_LENGTH]

    transitions = lifecycle.transitions[:MAX_TRANSITIONS]
    safe_events = tuple(
        AuditEventType(value)
        for value in audit_event_types
        if value in AuditEventType._value2member_map_
    )
    safe_events = safe_events[:MAX_AUDIT_REFERENCES]
    bounded_diagnostic = diagnostic.model_copy(
        update={
            "correlation": diagnostic.correlation.model_copy(
                update={
                    "workflow_id": bounded(
                        diagnostic.correlation.workflow_id,
                        "diagnostic.correlation.workflow_id",
                    ),
                    "request_id": bounded(
                        diagnostic.correlation.request_id,
                        "diagnostic.correlation.request_id",
                    ),
                }
            ),
            "verification_evidence": diagnostic.verification_evidence.model_copy(
                update={
                    "observed_state": bounded(
                        diagnostic.verification_evidence.observed_state,
                        "diagnostic.verification_evidence.observed_state",
                    ),
                    "observed_health": bounded(
                        diagnostic.verification_evidence.observed_health,
                        "diagnostic.verification_evidence.observed_health",
                    ),
                }
            ),
        }
    )
    sections = {
        "applicable": lifecycle.applicable,
        "metadata": SupportBundleMetadata(
            schema_version=SUPPORT_BUNDLE_SCHEMA,
            generated_at=generated_at,
            agent_version=bounded(agent_version, "metadata.agent_version") or "unavailable",
            workflow_id=bounded(lifecycle.workflow_id, "metadata.workflow_id") or "unavailable",
        ),
        "workflow": SupportBundleWorkflow(
            candidate_id=bounded(lifecycle.candidate_id, "workflow.candidate_id"),
            planning_session_id=bounded(
                lifecycle.planning_session_id, "workflow.planning_session_id"
            ),
            effect_kind=bounded(lifecycle.effect_kind, "workflow.effect_kind") or "unavailable",
            execution_intent=bounded(
                lifecycle.execution_intent, "workflow.execution_intent"
            ),
            target_label=bounded(lifecycle.target_label, "workflow.target_label"),
        ),
        "approvals": SupportBundleApprovals(
            preparation=_approval(lifecycle.preparation_approval),
            operational_action=_approval(lifecycle.action_approval),
        ),
        "lifecycle": SupportBundleLifecycle(
            availability=lifecycle.availability,
            request_id=bounded(lifecycle.action_request_id, "lifecycle.request_id"),
            request_digest=bounded(lifecycle.request_digest, "lifecycle.request_digest"),
            agent_execution_stage=lifecycle.agent_execution_stage,
            core_ledger_state=lifecycle.core_record_state,
            transitions=tuple(
                SupportBundleTransition(
                    sequence=item.sequence,
                    state=bounded(item.state, "lifecycle.transitions.state") or "unavailable",
                    occurred_at=item.occurred_at,
                )
                for item in transitions
            ),
            transition_sequence_valid=lifecycle.transition_sequence_valid,
            barrier_crossed=lifecycle.barrier_crossed,
            barrier_crossing_count=lifecycle.barrier_crossing_count,
            provider_operation_captured=lifecycle.provider_operation_captured,
            provider_operation_capture_count=lifecycle.provider_operation_capture_count,
            dispatch_status=lifecycle.dispatch_status,
            dispatch_result_known=lifecycle.dispatch_status is not None,
            provider_operation_reference=bounded(
                lifecycle.provider_operation_reference,
                "lifecycle.provider_operation_reference",
            ),
            verification_status=lifecycle.verification_status,
            observed_state=bounded(lifecycle.observed_state, "lifecycle.observed_state"),
            observed_health=bounded(lifecycle.observed_health, "lifecycle.observed_health"),
            terminal=lifecycle.terminal,
        ),
        "diagnostic": bounded_diagnostic,
        "service_health": (
            SupportBundleServiceIdentity(
                service_name="atlas-agent",
                status=ServiceAvailability.AVAILABLE,
                version=bounded(agent_version, "service_health.version") or "unavailable",
            ),
        ),
        "capability_boundary": SupportBundleCapabilityBoundary(
            production_tuples=tuple(sorted(production_tuples)),
            agent_execution_intents=tuple(sorted(operational_execution_intents)),
            parity_status=CapabilityParityStatus.NOT_EVALUATED,
        ),
        "audit_refs": tuple(
            SupportBundleAuditReference(event_type=value) for value in safe_events
        ),
        "truncation": SupportBundleTruncation(
            transitions_truncated=len(lifecycle.transitions) > MAX_TRANSITIONS,
            audit_references_truncated=len(audit_event_types) > MAX_AUDIT_REFERENCES,
            text_fields_truncated=tuple(sorted(set(truncated_fields))),
        ),
    }
    digest = support_bundle_digest(sections)
    return OperationalSupportBundle(
        **sections,
        integrity=SupportBundleIntegrity(
            digest=digest,
            purpose="integrity_and_correlation_only",
        ),
    )


def support_bundle_digest(sections: dict[str, object]) -> str:
    """Return a deterministic, non-authenticating digest of canonical content."""

    canonical = json.dumps(
        {
            key: value.model_dump(mode="json") if isinstance(value, BaseModel) else _json(value)
            for key, value in sections.items()
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"{SUPPORT_BUNDLE_DIGEST_PREFIX}:{hashlib.sha256(canonical).hexdigest()}"


def _json(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_json(item) for item in value]
    return value


def _approval(value: ApprovalFacts | None) -> SupportBundleApproval | None:
    if value is None:
        return None
    return SupportBundleApproval(
        decision_status=value.decision_status,
        presentation_state=value.presentation_state,
        actionable=value.actionable,
        expires_at=value.expires_at,
    )
