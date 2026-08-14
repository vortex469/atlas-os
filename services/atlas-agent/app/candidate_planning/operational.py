"""Deterministic, descriptive operational candidate planning."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.candidate_planning.models import (
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    OperationalCandidatePlan,
    OperationalVerificationSpecification,
    PlanningDecision,
)
from app.workflow.models import WorkflowEffectKind

OPERATIONAL_PLAN_FINGERPRINT_VERSION = "operational-plan-fingerprint-v1"


def operational_plan_fingerprint(plan: OperationalCandidatePlan) -> str:
    """Bind every security-relevant sanitized operational plan field."""

    payload = {
        "candidate_fingerprint": plan.candidate_fingerprint,
        "candidate_id": plan.candidate_id,
        "created_at": plan.created_at.isoformat(),
        "disruption_scope": plan.disruption_scope,
        "effect_kind": plan.effect_kind.value,
        "evidence_ids": sorted(plan.evidence_ids),
        "execution_intent": plan.execution_intent,
        "expected_pre_state": plan.expected_pre_state,
        "failure_considerations": sorted(plan.failure_considerations),
        "identifier": plan.identifier,
        "intended_action": plan.intended_action,
        "provider_id": plan.provider_id,
        "resource_id": plan.resource_id,
        "resource_type": plan.resource_type,
        "revalidated_candidate_fingerprint": plan.revalidated_candidate_fingerprint,
        "session_id": plan.session_id,
        "target_fingerprint": plan.target_fingerprint,
        "target_version": plan.target_version,
        "verification": {
            "expected_post_state": plan.verification.expected_post_state,
            "health_requirement": plan.verification.health_requirement,
            "identity_fingerprint": plan.verification.identity_fingerprint,
            "pre_state": plan.verification.pre_state,
            "unknown_outcome_policy": plan.verification.unknown_outcome_policy,
        },
        "version": OPERATIONAL_PLAN_FINGERPRINT_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{OPERATIONAL_PLAN_FINGERPRINT_VERSION}:{hashlib.sha256(encoded.encode()).hexdigest()}"


def create_operational_plan(
    session: CandidatePlanningSession,
    *,
    created_at: datetime,
    revalidated_candidate_fingerprint: str,
) -> PlanningDecision:
    """Create a non-executable restart-service description from a trusted snapshot."""

    target = session.snapshot.operational_target
    if (
        session.snapshot.effect_kind is not WorkflowEffectKind.OPERATIONAL_ACTION
        or target is None
        or session.snapshot.execution_intent != "restart-service"
    ):
        raise ValueError("operational planning requires a supported authoritative target")
    digest = hashlib.sha256(
        f"{session.identifier}\0{session.candidate_fingerprint}\0{target.resource_fingerprint}".encode()
    ).hexdigest()
    plan = OperationalCandidatePlan(
        identifier=f"operational-plan-{digest}",
        session_id=session.identifier,
        candidate_id=session.candidate_id,
        candidate_fingerprint=session.candidate_fingerprint,
        effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
        execution_intent=session.snapshot.execution_intent,
        provider_id=target.provider_id,
        resource_id=target.resource_id,
        resource_type=target.resource_type,
        target_fingerprint=target.resource_fingerprint,
        target_version=target.resource_version,
        expected_pre_state=target.expected_state,
        intended_action="restart-service",
        disruption_scope="The exact service may be temporarily unavailable during a future restart.",
        verification=OperationalVerificationSpecification(
            pre_state=target.expected_state,
            expected_post_state="service-running-and-healthy",
            identity_fingerprint=target.resource_fingerprint,
            health_requirement="The same exact service identity must report healthy after the action.",
            unknown_outcome_policy="Stop and require operator review when the outcome cannot be verified.",
        ),
        failure_considerations=(
            "The service may fail to return to a healthy state.",
            "An interrupted request may leave the action outcome unknown.",
        ),
        evidence_ids=session.snapshot.evidence_ids,
        created_at=created_at,
        revalidated_candidate_fingerprint=revalidated_candidate_fingerprint,
    )
    return PlanningDecision(
        status=CandidatePlanningSessionStatus.PLAN_READY,
        operational_plan=plan,
    )
