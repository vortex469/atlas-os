"""Fail-closed InstallationPlan projection toward execution-candidate intake."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from app.execution_candidates.models import ExecutionCandidate, ExecutionCandidateModel
from app.installation_plan.contract import InstallationPlan

InstallationPlanStatus = Literal[
    "conflicted",
    "missing_deployment_artifact",
    "incompatible",
    "stale_evidence",
    "insufficient_information",
    "plan_ready_for_review",
]


class InstallationPlanCandidateReason(StrEnum):
    """Controlled reasons why an InstallationPlan cannot create a candidate."""

    INSTALLATION_PLAN_BLOCKED = "installation_plan_blocked"
    APPROVED_TARGET_CONTRACT_UNAVAILABLE = "approved_target_contract_unavailable"
    AGENT_INSTALLATION_INTENT_UNSUPPORTED = "agent_installation_intent_unsupported"


class InstallationPlanCandidateProjection(ExecutionCandidateModel):
    """Immutable, non-authoritative result of candidate-admission projection."""

    schema_version: Literal["installation-plan-candidate-projection-v1"] = (
        "installation-plan-candidate-projection-v1"
    )
    installation_plan: InstallationPlan
    installation_plan_fingerprint: str
    item_id: str
    catalog_entry_id: str
    installation_plan_status: InstallationPlanStatus
    candidate_created: Literal[False] = False
    planning_allowed: Literal[False] = False
    candidate: ExecutionCandidate | None = None
    reason_codes: tuple[InstallationPlanCandidateReason, ...]

    @model_validator(mode="after")
    def preserve_plan_identity_and_refusal(self) -> InstallationPlanCandidateProjection:
        if self.installation_plan_fingerprint != self.installation_plan.fingerprint.value:
            raise ValueError("installation plan fingerprint linkage must be exact")
        if self.item_id != self.installation_plan.application.item_id:
            raise ValueError("installation plan item linkage must be exact")
        if self.catalog_entry_id != self.installation_plan.application.catalog_entry_id:
            raise ValueError("installation plan catalog linkage must be exact")
        if self.installation_plan_status != self.installation_plan.status:
            raise ValueError("installation plan status linkage must be exact")
        if self.candidate is not None:
            raise ValueError("v1 InstallationPlan projection cannot create a candidate")
        expected = _projection_reasons(self.installation_plan.status)
        if self.reason_codes != expected:
            raise ValueError("installation plan projection reasons must be deterministic")
        return self


def _projection_reasons(
    status: InstallationPlanStatus,
) -> tuple[InstallationPlanCandidateReason, ...]:
    reasons = []
    if status != "plan_ready_for_review":
        reasons.append(InstallationPlanCandidateReason.INSTALLATION_PLAN_BLOCKED)
    reasons.extend(
        (
            InstallationPlanCandidateReason.APPROVED_TARGET_CONTRACT_UNAVAILABLE,
            InstallationPlanCandidateReason.AGENT_INSTALLATION_INTENT_UNSUPPORTED,
        )
    )
    return tuple(reasons)


def project_installation_plan_to_candidate(
    plan: InstallationPlan,
) -> InstallationPlanCandidateProjection:
    """Project without creating authority, persistence, work, or side effects."""

    return InstallationPlanCandidateProjection(
        installation_plan=plan,
        installation_plan_fingerprint=plan.fingerprint.value,
        item_id=plan.application.item_id,
        catalog_entry_id=plan.application.catalog_entry_id,
        installation_plan_status=plan.status,
        candidate=None,
        reason_codes=_projection_reasons(plan.status),
    )
