"""Deterministic candidate-aware read-only planners."""

from __future__ import annotations

from pathlib import Path

from app.candidate_planning.models import (
    CandidatePlan,
    CandidatePlanningContext,
    CandidatePlanningFailure,
    CandidatePlanningFailureCode,
    CandidatePlanningSessionStatus,
    PlanningDecision,
)
from app.repository.models import RepositorySnapshot

_COMPOSE_TARGETS = frozenset({"atlas-compose", "atlas-repository"})
_RC1_SMOKE_INTENT = "rc1-validation-smoke"
_RC1_SMOKE_TARGET = Path("services/atlas-agent/tests/test_execution_engine.py")
_RC1_SMOKE_MARKER = "# Atlas RC1 execution smoke marker"
_UNSAFE_PLAN_TOKENS = (
    "$",
    "&&",
    "||",
    ";",
    "`",
    "sudo ",
    "rm -",
    "docker compose",
    "docker-compose",
)


class RepositoryResolver:
    """Resolve candidate planning repositories from Agent-owned configuration only."""

    def __init__(self, *, repository_root: Path) -> None:
        self._repository_root = repository_root

    def resolve(self, *, target_id: str, target_type: str) -> Path | None:
        """Resolve a trusted repository path for a candidate target."""

        if target_type != "repository":
            return None
        if target_id not in _COMPOSE_TARGETS:
            return None
        return self._repository_root


class UpdateComposeStackCandidatePlanner:
    """Create deterministic descriptive plans for compose-stack updates."""

    def create_plan(
        self,
        *,
        context: CandidatePlanningContext,
        snapshot: RepositorySnapshot,
    ) -> CandidatePlan:
        """Create one read-only descriptive candidate plan."""

        if context.execution_intent == _RC1_SMOKE_INTENT:
            return self._create_rc1_smoke_plan(context=context, snapshot=snapshot)
        if context.mutation is None:
            raise ValueError("update-compose-stack candidate lacks a mutation specification")
        plan = CandidatePlan(
            identifier=f"candidate-plan-output-{context.session_id}",
            session_id=context.session_id,
            candidate_id=context.candidate_id,
            candidate_fingerprint=context.candidate_fingerprint,
            title="Prepare compose stack update proposal",
            objective=(
                "Create a minimal repository change proposal for the accepted "
                "compose-stack candidate without executing it."
            ),
            assumptions=(
                "The trusted Agent repository is the only repository context for this candidate.",
                "Atlas Core revalidated the candidate immediately before planning.",
                "A later workflow conversion and implementation approval are required before any change.",
            ),
            constraints=tuple(sorted(context.constraints)),
            proposed_steps=(
                "Inspect the trusted compose definitions in the configured Atlas repository.",
                "Identify the repository files and service definitions that correspond to the candidate target.",
                "Prepare a minimal repository change proposal that preserves unrelated services and configuration.",
                "Describe later validation for compose syntax and Atlas regression tests without running commands now.",
                "Document rollback considerations before any workflow conversion or implementation approval.",
            ),
            likely_affected_components=(context.target_id,),
            likely_affected_files=(Path("compose.production.yaml"),),
            verification_strategy=(
                "Later workflow conversion should validate compose configuration syntax.",
                "Later workflow conversion should run relevant Atlas regression checks.",
                "Later workflow conversion should confirm unrelated runtime configuration is unchanged.",
            ),
            rollback_considerations=(
                "Keep the previous compose definition available through version control.",
                "Avoid altering unrelated services so a focused revert remains possible.",
            ),
            unresolved_questions=(
                "Confirm the exact compose service mapping during workflow conversion.",
            ),
            evidence_ids=tuple(sorted(context.evidence_ids)),
            created_at=context.planning_timestamp,
            repository_root=snapshot.root,
            repository_branch=snapshot.branch,
            repository_head=snapshot.head_commit,
            revalidated_candidate_fingerprint=context.revalidated_candidate_fingerprint,
            mutation=context.mutation,
        )
        _validate_safe_plan(plan)
        return plan

    def _create_rc1_smoke_plan(
        self,
        *,
        context: CandidatePlanningContext,
        snapshot: RepositorySnapshot,
    ) -> CandidatePlan:
        """Create the fixed, validation-only RC1 smoke plan."""

        if not _rc1_smoke_context_is_exact(context):
            raise ValueError("RC1 smoke context is not the fixed validation request")
        if context.mutation is None or (
            context.mutation.file != _RC1_SMOKE_TARGET
            or context.mutation.operation != "append-fixed-marker"
            or context.mutation.desired_value != _RC1_SMOKE_MARKER
        ):
            raise ValueError("RC1 smoke mutation is not the fixed validation mutation")
        plan = CandidatePlan(
            identifier=f"candidate-plan-output-{context.session_id}",
            session_id=context.session_id,
            candidate_id=context.candidate_id,
            candidate_fingerprint=context.candidate_fingerprint,
            title="Prepare the RC1 validation marker change",
            objective="Apply one fixed validation marker to the trusted Atlas test file.",
            assumptions=(
                "This is an RC1 validation-only operation.",
                "The trusted Agent repository is the only repository context.",
                "Implementation approval and later verification approval are required.",
            ),
            constraints=(
                "no-deployment-files",
                "no-commit",
                "rc1-validation-only",
            ),
            proposed_steps=(
                "Inspect the trusted Atlas test file.",
                "Append the fixed RC1 validation marker once.",
                "Return the bounded one-file change for Agent review.",
            ),
            likely_affected_components=("atlas-repository",),
            likely_affected_files=(_RC1_SMOKE_TARGET,),
            verification_strategy=(
                "Confirm only the fixed Atlas test file changed.",
                "Require verification approval before any later review or commit.",
            ),
            rollback_considerations=(
                "Restore the fixed test file without changing deployment files.",
            ),
            unresolved_questions=(),
            evidence_ids=tuple(sorted(context.evidence_ids)),
            created_at=context.planning_timestamp,
            repository_root=snapshot.root,
            repository_branch=snapshot.branch,
            repository_head=snapshot.head_commit,
            revalidated_candidate_fingerprint=context.revalidated_candidate_fingerprint,
            mutation=context.mutation,
        )
        _validate_rc1_smoke_plan(plan)
        return plan


def planning_decision_for_plan(plan: CandidatePlan) -> PlanningDecision:
    """Wrap a successful plan in a deterministic planning decision."""

    return PlanningDecision(
        status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=plan,
    )


def unsupported_decision(code: CandidatePlanningFailureCode, message: str) -> PlanningDecision:
    """Create a sanitized unsuccessful planning decision."""

    status = CandidatePlanningSessionStatus.PLANNING_NOT_SUPPORTED
    if code in {
        CandidatePlanningFailureCode.CANDIDATE_STALE,
        CandidatePlanningFailureCode.CANDIDATE_EXPIRED,
        CandidatePlanningFailureCode.CANDIDATE_NOT_ELIGIBLE,
        CandidatePlanningFailureCode.EVIDENCE_UNAVAILABLE,
        CandidatePlanningFailureCode.TARGET_UNAVAILABLE,
    }:
        status = CandidatePlanningSessionStatus.STALE_BEFORE_PLANNING
    elif code in {
        CandidatePlanningFailureCode.PLANNING_VALIDATION_FAILED,
        CandidatePlanningFailureCode.UNSAFE_PLAN_CONTENT,
        CandidatePlanningFailureCode.REPOSITORY_INSPECTION_FAILED,
        CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE,
    }:
        status = CandidatePlanningSessionStatus.PLANNING_FAILED
    return PlanningDecision(
        status=status,
        failure=CandidatePlanningFailure(code=code, message=message),
    )


def _validate_safe_plan(plan: CandidatePlan) -> None:
    fields = (
        plan.title,
        plan.objective,
        *plan.assumptions,
        *plan.proposed_steps,
        *plan.verification_strategy,
        *plan.rollback_considerations,
        *plan.unresolved_questions,
    )
    for value in fields:
        lowered = value.lower()
        if any(token in lowered for token in _UNSAFE_PLAN_TOKENS):
            raise ValueError("Candidate plan contains executable-looking content")


def _rc1_smoke_context_is_exact(context: CandidatePlanningContext) -> bool:
    return (
        context.execution_intent == _RC1_SMOKE_INTENT
        and context.target_id == "atlas-repository"
        and context.target_type == "repository"
        and context.recommendation_class == "rc1-validation-smoke"
        and context.mutation is not None
        and context.mutation.file == _RC1_SMOKE_TARGET
        and context.mutation.service == "atlas-agent"
        and context.mutation.property == "rc1-validation-marker"
        and context.mutation.operation == "append-fixed-marker"
        and context.mutation.desired_value == _RC1_SMOKE_MARKER
        and context.mutation.expected_value is None
        and set(context.mutation.preservation_constraints)
        == {"no-deployment-files", "no-commit", "rc1-validation-only"}
    )


def _validate_rc1_smoke_plan(plan: CandidatePlan) -> None:
    if (
        plan.likely_affected_components != ("atlas-repository",)
        or plan.likely_affected_files != (_RC1_SMOKE_TARGET,)
        or plan.mutation is None
        or plan.mutation.file != _RC1_SMOKE_TARGET
        or plan.mutation.desired_value != _RC1_SMOKE_MARKER
        or plan.mutation.operation != "append-fixed-marker"
    ):
        raise ValueError("RC1 smoke plan is outside the fixed validation scope")
    _validate_safe_plan(plan)
