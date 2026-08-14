"""Deterministic, descriptive operational candidate planning."""

from __future__ import annotations

import hashlib
from datetime import datetime

from app.candidate_planning.models import (
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    OperationalCandidatePlan,
    OperationalVerificationSpecification,
    PlanningDecision,
)
from app.workflow.models import WorkflowEffectKind


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
