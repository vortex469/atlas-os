"""Candidate implementation execution validation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.approval.models import ApprovalPurpose, ApprovalResult, ApprovalStatus
from app.candidate_planning.conversion import candidate_plan_fingerprint
from app.candidate_planning.implementation import TRANSLATOR_VERSION
from app.candidate_planning.models import (
    RC1_VALIDATION_SMOKE_INTENT,
    CandidateImplementationRequest,
    CoreCandidatePlanningIntakeStatus,
    is_supported_execution_intent,
)
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.exceptions import AtlasCoreClientError
from app.core_client.models import CoreCandidatePlanningIntakeResponse
from app.execution.models import ExecutionRequest, PolicyViolation
from app.execution.policy import ToolPolicy
from app.planning.models import ImplementationPlan
from app.repository.exceptions import RepositoryInspectionError
from app.repository.inspector import GitInspector
from app.repository.models import RepositorySnapshot
from app.workflow.models import WorkflowSession, WorkflowSessionState, WorkflowSource


class CandidateExecutionFailureCode(StrEnum):
    """Stable candidate execution failure codes."""

    APPROVAL_MISSING = "approval_missing"
    APPROVAL_NOT_GRANTED = "approval_not_granted"
    APPROVAL_EVIDENCE_MISMATCH = "approval_evidence_mismatch"
    CANDIDATE_STALE = "candidate_stale"
    PLAN_STALE = "plan_stale"
    REPOSITORY_STALE = "repository_stale"
    CORE_UNAVAILABLE = "core_unavailable"
    TOOL_POLICY_DENIED = "tool_policy_denied"
    EXECUTION_FAILED = "execution_failed"
    PATCH_APPLICATION_FAILED = "patch_application_failed"
    PERSISTENCE_FAILED = "persistence_failed"


@dataclass(frozen=True, slots=True)
class CandidateExecutionValidationResult:
    """Candidate execution validation result."""

    approved: bool
    failure_code: CandidateExecutionFailureCode | None = None
    message: str | None = None
    retryable: bool = False
    should_block: bool = False
    implementation_request: CandidateImplementationRequest | None = None
    implementation_plan: ImplementationPlan | None = None
    execution_request: ExecutionRequest | None = None
    repository_snapshot: RepositorySnapshot | None = None


class CandidatePlanningIntakeClient(Protocol):
    async def validate_candidate_planning_intake(
        self,
        candidate_id: str,
        *,
        expected_candidate_fingerprint: str | None = None,
    ) -> CoreCandidatePlanningIntakeResponse: ...


class CandidateExecutionValidator:
    """Validate candidate execution without spreading candidate dependencies."""

    def __init__(
        self,
        *,
        core_client: CandidatePlanningIntakeClient,
        candidate_state: CandidatePlanningStateStore,
        repository_resolver: RepositoryResolver,
        repository_inspector_factory: Callable[[Path], GitInspector] = GitInspector,
        tool_policy: ToolPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._core_client = core_client
        self._candidate_state = candidate_state
        self._repository_resolver = repository_resolver
        self._repository_inspector_factory = repository_inspector_factory
        self._tool_policy = tool_policy or ToolPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def validate(
        self,
        *,
        workflow: WorkflowSession,
        approval_result: ApprovalResult | None,
    ) -> CandidateExecutionValidationResult:
        """Validate exact approval and all candidate freshness inputs."""

        local = self._validate_local_workflow_and_approval(
            workflow=workflow,
            approval_result=approval_result,
        )
        if not local.approved:
            return local
        implementation_request = local.implementation_request
        assert implementation_request is not None

        plan_result = self._validate_candidate_plan(
            workflow=workflow,
            implementation_request=implementation_request,
        )
        if not plan_result.approved:
            return plan_result

        core_result = self._validate_core_freshness(
            workflow=workflow,
            implementation_request=implementation_request,
        )
        if not core_result.approved:
            return core_result

        repository_result = self._validate_repository(
            implementation_request=implementation_request,
        )
        if not repository_result.approved:
            return repository_result

        implementation_plan = implementation_plan_from_candidate_request(
            implementation_request
        )
        execution_request = ExecutionRequest(
            identifier=implementation_request.identifier,
            plan=implementation_plan,
            argv=implementation_request.argv,
            working_directory=implementation_request.working_directory,
        )
        policy = self._tool_policy
        if implementation_request.execution_intent == RC1_VALIDATION_SMOKE_INTENT:
            if implementation_request.argv != ("atlas-rc1-validation-smoke",):
                return _failure(
                    CandidateExecutionFailureCode.TOOL_POLICY_DENIED,
                    "RC1 validation smoke request must use the exact smoke command.",
                    should_block=True,
                )
            if is_supported_execution_intent(RC1_VALIDATION_SMOKE_INTENT):
                policy = ToolPolicy(
                    frozenset({"codex", "atlas-rc1-validation-smoke"})
                )
        policy_result = policy.validate(execution_request)
        if isinstance(policy_result, PolicyViolation):
            return _failure(
                CandidateExecutionFailureCode.TOOL_POLICY_DENIED,
                "Candidate implementation request is denied by tool policy.",
                should_block=True,
            )

        return CandidateExecutionValidationResult(
            approved=True,
            implementation_request=implementation_request,
            implementation_plan=implementation_plan,
            execution_request=execution_request,
            repository_snapshot=repository_result.repository_snapshot,
        )

    def _validate_local_workflow_and_approval(
        self,
        *,
        workflow: WorkflowSession,
        approval_result: ApprovalResult | None,
    ) -> CandidateExecutionValidationResult:
        if workflow.source is not WorkflowSource.CANDIDATE:
            return _evidence_mismatch(
                "Workflow source is not candidate-based implementation workflow."
            )
        if workflow.state is not WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL:
            return _evidence_mismatch(
                "Workflow is not in awaiting implementation approval state."
            )
        metadata = workflow.candidate_metadata
        implementation_request = workflow.candidate_implementation_request
        approval_id = workflow.candidate_implementation_approval_id
        if metadata is None or implementation_request is None or approval_id is None:
            return _failure(
                CandidateExecutionFailureCode.APPROVAL_MISSING,
                "Candidate implementation approval is missing.",
                should_block=True,
            )
        if not implementation_request.argv:
            return _evidence_mismatch("Implementation request has no command arguments.")
        if implementation_request.translator_version != TRANSLATOR_VERSION:
            return _evidence_mismatch(
                f"Implementation request uses unsupported translator version:"
                f" {implementation_request.translator_version}."
            )
        if approval_result is None:
            return _failure(
                CandidateExecutionFailureCode.APPROVAL_MISSING,
                "Candidate implementation approval is missing.",
                should_block=True,
            )
        decision = approval_result.decision
        approval = decision.request
        if decision.status is ApprovalStatus.PENDING:
            return _failure(
                CandidateExecutionFailureCode.APPROVAL_NOT_GRANTED,
                "Candidate implementation approval is pending.",
                retryable=True,
            )
        if decision.status is not ApprovalStatus.APPROVED:
            return _failure(
                CandidateExecutionFailureCode.APPROVAL_NOT_GRANTED,
                "Candidate implementation approval was not granted.",
                should_block=True,
            )
        if not approval.requested_command:
            return _evidence_mismatch("Approval request is missing requested command.")

        mismatch_reasons: list[str] = []
        if approval.identifier != approval_id:
            mismatch_reasons.append("approval identifier")
        if approval.purpose is not ApprovalPurpose.IMPLEMENTATION:
            mismatch_reasons.append("approval purpose")
        if approval.workflow_id != workflow.identifier:
            mismatch_reasons.append("approval workflow id")
        if approval.checkpoint_id != implementation_request.identifier:
            mismatch_reasons.append("approval checkpoint id")
        if approval.requested_tool != implementation_request.argv[0]:
            mismatch_reasons.append("approval requested tool")
        if approval.requested_command != implementation_request.argv:
            mismatch_reasons.append("approval requested command")
        if approval.requested_working_directory != implementation_request.working_directory:
            mismatch_reasons.append("approval requested working directory")
        if mismatch_reasons:
            return _evidence_mismatch(
                "Approval request does not match implementation request: "
                + ", ".join(mismatch_reasons)
            )

        mismatch_reasons = []
        if metadata.candidate_planning_session_id != implementation_request.candidate_planning_session_id:
            mismatch_reasons.append("candidate planning session id")
        if metadata.candidate_id != implementation_request.candidate_id:
            mismatch_reasons.append("candidate id")
        if metadata.candidate_fingerprint != implementation_request.candidate_fingerprint:
            mismatch_reasons.append("candidate fingerprint")
        if metadata.candidate_plan_id != implementation_request.candidate_plan_id:
            mismatch_reasons.append("candidate plan id")
        if metadata.candidate_plan_fingerprint != implementation_request.candidate_plan_fingerprint:
            mismatch_reasons.append("candidate plan fingerprint")
        if metadata.execution_intent != implementation_request.execution_intent:
            mismatch_reasons.append("execution intent")
        if metadata.evidence_ids != implementation_request.evidence_ids:
            mismatch_reasons.append("evidence ids")
        if metadata.compatibility_assessment_id != implementation_request.compatibility_assessment_id:
            mismatch_reasons.append("compatibility assessment id")
        if metadata.compatibility_status != implementation_request.compatibility_status:
            mismatch_reasons.append("compatibility status")
        if mismatch_reasons:
            return _evidence_mismatch(
                "Candidate metadata does not match implementation request: "
                + ", ".join(mismatch_reasons)
            )

        return CandidateExecutionValidationResult(
            approved=True,
            implementation_request=implementation_request,
        )

    def _validate_candidate_plan(
        self,
        *,
        workflow: WorkflowSession,
        implementation_request: CandidateImplementationRequest,
    ) -> CandidateExecutionValidationResult:
        session = self._candidate_state.get_session(
            implementation_request.candidate_planning_session_id
        )
        if session is None or session.workflow_session_id != workflow.identifier:
            return _plan_stale()
        if session.plan is None:
            return _plan_stale()
        recomputed = candidate_plan_fingerprint(session.plan)
        metadata = workflow.candidate_metadata
        if metadata is None:
            return _plan_stale()
        if not (
            recomputed == implementation_request.candidate_plan_fingerprint
            and recomputed == metadata.candidate_plan_fingerprint
            and recomputed == session.candidate_plan_fingerprint
        ):
            return _plan_stale()
        return CandidateExecutionValidationResult(approved=True)

    def _validate_core_freshness(
        self,
        *,
        workflow: WorkflowSession,
        implementation_request: CandidateImplementationRequest,
    ) -> CandidateExecutionValidationResult:
        try:
            intake = asyncio.run(
                self._core_client.validate_candidate_planning_intake(
                    implementation_request.candidate_id,
                    expected_candidate_fingerprint=implementation_request.candidate_fingerprint,
                )
            )
        except AtlasCoreClientError:
            return _failure(
                CandidateExecutionFailureCode.CORE_UNAVAILABLE,
                "Atlas Core planning intake is unavailable.",
                retryable=True,
            )
        except RuntimeError:
            return _failure(
                CandidateExecutionFailureCode.CORE_UNAVAILABLE,
                "Atlas Core planning intake is unavailable.",
                retryable=True,
            )
        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            return _candidate_stale()
        candidate = intake.current_candidate
        metadata = workflow.candidate_metadata
        if (
            candidate is None
            or intake.current_candidate_fingerprint is None
            or metadata is None
        ):
            return _candidate_stale()
        now = self._clock()
        if candidate.expires_at is not None and candidate.expires_at <= now:
            return _candidate_stale()
        if not (
            intake.candidate_id == implementation_request.candidate_id
            and candidate.id == implementation_request.candidate_id
            and intake.current_candidate_fingerprint
            == implementation_request.candidate_fingerprint
            and candidate.target_id == metadata.target_id
            and candidate.target_type == metadata.target_type
            and candidate.execution_category == metadata.execution_category
            and candidate.execution_intent == metadata.execution_intent
            and candidate.required_approval_level
            == _candidate_session_required_approval(
                self._candidate_state,
                implementation_request,
            )
            and tuple(sorted(candidate.evidence_ids)) == metadata.evidence_ids
            and candidate.compatibility_assessment_id
            == metadata.compatibility_assessment_id
            and candidate.compatibility_status == metadata.compatibility_status
            and tuple(sorted(candidate.relationship_ids)) == metadata.relationship_ids
        ):
            return _candidate_stale()
        return CandidateExecutionValidationResult(approved=True)

    def _validate_repository(
        self,
        *,
        implementation_request: CandidateImplementationRequest,
    ) -> CandidateExecutionValidationResult:
        resolved = self._repository_resolver.resolve(
            target_id=_candidate_session_target_id(
                self._candidate_state,
                implementation_request,
            ),
            target_type=_candidate_session_target_type(
                self._candidate_state,
                implementation_request,
            ),
        )
        if resolved is None:
            return _repository_stale()
        trusted_root = resolved.resolve(strict=False)
        request_root = implementation_request.repository_root.resolve(strict=False)
        if trusted_root != request_root:
            return _repository_stale()
        working_directory = implementation_request.working_directory.resolve(strict=False)
        if not working_directory.is_relative_to(trusted_root):
            return _repository_stale()
        for path in implementation_request.affected_files:
            if path.is_absolute() or ".." in path.parts:
                return _repository_stale()
        try:
            snapshot = self._repository_inspector_factory(trusted_root).inspect()
        except (OSError, RepositoryInspectionError, ValueError):
            return _repository_stale()
        if not _repository_matches_request(snapshot, implementation_request):
            return _repository_stale()
        return CandidateExecutionValidationResult(
            approved=True,
            repository_snapshot=snapshot,
        )


def implementation_plan_from_candidate_request(
    request: CandidateImplementationRequest,
) -> ImplementationPlan:
    """Build the minimal normal plan required by execution contracts."""

    return ImplementationPlan(
        checkpoint_id=request.identifier,
        title="Candidate implementation request",
        goal="Implement the exact approved candidate repository change request.",
        repository_root=request.repository_root,
        branch=request.repository_branch,
        head_commit=request.repository_head,
        scope_items=(request.execution_intent,),
        affected_files=request.affected_files,
        required_tests=(),
        risks=(),
    )


def _candidate_session_required_approval(
    state: CandidatePlanningStateStore,
    request: CandidateImplementationRequest,
) -> str | None:
    session = state.get_session(request.candidate_planning_session_id)
    return session.snapshot.required_approval_level if session is not None else None


def _candidate_session_target_id(
    state: CandidatePlanningStateStore,
    request: CandidateImplementationRequest,
) -> str:
    session = state.get_session(request.candidate_planning_session_id)
    return session.snapshot.target_id if session is not None else ""


def _candidate_session_target_type(
    state: CandidatePlanningStateStore,
    request: CandidateImplementationRequest,
) -> str:
    session = state.get_session(request.candidate_planning_session_id)
    return session.snapshot.target_type if session is not None else ""


def _repository_matches_request(
    snapshot: RepositorySnapshot,
    request: CandidateImplementationRequest,
) -> bool:
    allowed_untracked = {
        "compose.execution-smoke.override.yaml",
    } if (
        request.execution_intent == RC1_VALIDATION_SMOKE_INTENT
        and is_supported_execution_intent(request.execution_intent)
    ) else set()
    return (
        snapshot.root == request.repository_root.resolve(strict=False)
        and snapshot.branch == request.repository_branch
        and snapshot.head_commit == request.repository_head
        and not snapshot.modified_files
        and not snapshot.staged_files
        and not any(
            not _is_log_path(path)
            and path not in allowed_untracked
            for path in snapshot.untracked_files
        )
    )


def _is_log_path(path: str | Path) -> bool:
    parts = Path(path).parts
    return bool(parts) and parts[0] == "logs"


def _failure(
    code: CandidateExecutionFailureCode,
    message: str,
    *,
    retryable: bool = False,
    should_block: bool = False,
) -> CandidateExecutionValidationResult:
    return CandidateExecutionValidationResult(
        approved=False,
        failure_code=code,
        message=message,
        retryable=retryable,
        should_block=should_block,
    )


def _evidence_mismatch(
    detail: str,
) -> CandidateExecutionValidationResult:
    return _failure(
        CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH,
        f"Candidate implementation approval does not match persisted workflow evidence: {detail}",
        should_block=True,
    )


def _candidate_stale() -> CandidateExecutionValidationResult:
    return _failure(
        CandidateExecutionFailureCode.CANDIDATE_STALE,
        "Candidate changed before implementation execution.",
        should_block=True,
    )


def _plan_stale() -> CandidateExecutionValidationResult:
    return _failure(
        CandidateExecutionFailureCode.PLAN_STALE,
        "Candidate plan changed before implementation execution.",
        should_block=True,
    )


def _repository_stale() -> CandidateExecutionValidationResult:
    return _failure(
        CandidateExecutionFailureCode.REPOSITORY_STALE,
        "Trusted repository changed before candidate implementation execution.",
        should_block=True,
    )
