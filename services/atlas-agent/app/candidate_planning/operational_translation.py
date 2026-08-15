"""Closed, side-effect-free translation of operational plan semantics."""

from __future__ import annotations

from datetime import datetime

from app.candidate_planning.models import (
    OperationalActionRequest,
    OperationalCandidatePlan,
)
from app.candidate_planning.operational import operational_plan_fingerprint
from app.workflow.models import WorkflowEffectKind

OPERATIONAL_TRANSLATOR_VERSION = "operational-action-translator-v1"
_TRANSLATION_ACTIONS = {
    ("restart-service", "proxmox", "qemu"): "proxmox-qemu-graceful-restart-v1",
}


def is_operational_translation_supported(
    *, execution_intent: str, provider_id: str, resource_type: str
) -> bool:
    """Describe closed translation support without returning native action IDs."""

    return (execution_intent, provider_id, resource_type) in _TRANSLATION_ACTIONS


def resolve_provider_action_id(
    *, execution_intent: str, provider_id: str, resource_type: str
) -> str:
    """Resolve one internal semantic ID from the closed translation table."""

    try:
        return _TRANSLATION_ACTIONS[(execution_intent, provider_id, resource_type)]
    except KeyError as exc:
        raise ValueError("unsupported operational translation combination") from exc


def translate_operational_action_request(
    *,
    plan: OperationalCandidatePlan,
    workflow_session_id: str,
    generated_at: datetime,
    expires_at: datetime,
    supplied_provider_action_id: str | None = None,
) -> OperationalActionRequest:
    """Create a semantic request without importing or invoking execution code."""

    if plan.effect_kind is not WorkflowEffectKind.OPERATIONAL_ACTION:
        raise ValueError("operational translation requires operational_action effect kind")
    if not plan.target_fingerprint.strip():
        raise ValueError("operational translation requires authoritative target fingerprint")
    provider_action_id = resolve_provider_action_id(
        execution_intent=plan.execution_intent,
        provider_id=plan.provider_id,
        resource_type=plan.resource_type,
    )
    if (
        supplied_provider_action_id is not None
        and supplied_provider_action_id != provider_action_id
    ):
        raise ValueError("provider action id must match closed translation")

    plan_fingerprint = operational_plan_fingerprint(plan)
    request_id = f"operational-action-{plan_fingerprint.rsplit(':', 1)[-1]}"
    return OperationalActionRequest(
        request_id=request_id,
        request_digest="",
        idempotency_key="",
        workflow_session_id=workflow_session_id,
        candidate_planning_session_id=plan.session_id,
        candidate_id=plan.candidate_id,
        candidate_fingerprint=plan.candidate_fingerprint,
        candidate_plan_id=plan.identifier,
        candidate_plan_fingerprint=plan_fingerprint,
        effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
        execution_intent=plan.execution_intent,
        provider_id=plan.provider_id,
        resource_id=plan.resource_id,
        resource_type=plan.resource_type,
        provider_action_id=provider_action_id,
        target_fingerprint=plan.target_fingerprint,
        target_version=plan.target_version,
        disruption_scope=plan.disruption_scope,
        evidence_ids=plan.evidence_ids,
        expected_pre_state=plan.expected_pre_state,
        verification=plan.verification,
        expires_at=expires_at,
        translator_version=OPERATIONAL_TRANSLATOR_VERSION,
        generated_at=generated_at,
    )
