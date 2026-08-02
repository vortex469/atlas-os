"""Deterministic candidate workflow implementation translation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.candidate_planning.conversion import (
    candidate_plan_fingerprint,
    validate_candidate_plan_safe,
)
from app.candidate_planning.models import (
    CandidateImplementationRequest,
    CandidatePlanningFailure,
    CandidatePlanningFailureCode,
    CandidatePlanningSession,
)
from app.execution.models import ExecutionRequest
from app.execution.policy import ToolPolicy
from app.planning.models import ImplementationPlan
from app.repository.models import RepositorySnapshot
from app.workflow.models import WorkflowSession

TRANSLATOR_VERSION = "candidate-update-compose-stack-v1"
_SUPPORTED_INTENT = "update-compose-stack"
_ALLOWED_TARGETS = frozenset({"atlas-compose", "atlas-repository"})
_ALLOWED_AFFECTED_FILES = frozenset({Path("compose.production.yaml")})


@dataclass(frozen=True, slots=True)
class CandidateImplementationDecision:
    """Result of deterministic candidate implementation translation."""

    request: CandidateImplementationRequest | None = None
    failure: CandidatePlanningFailure | None = None


class CandidateImplementationTranslator:
    """Translate a candidate workflow shell into one exact request for approval."""

    def __init__(self, *, tool_policy: ToolPolicy | None = None) -> None:
        self._tool_policy = tool_policy or ToolPolicy()

    def translate(
        self,
        *,
        session: CandidatePlanningSession,
        workflow: WorkflowSession,
        repository: RepositorySnapshot,
        generated_at: datetime,
    ) -> CandidateImplementationDecision:
        """Return an immutable implementation request or a controlled failure."""

        if session.plan is None:
            return _failure(
                CandidatePlanningFailureCode.PLAN_NOT_READY,
                "Candidate plan is not available for implementation translation.",
            )
        if workflow.candidate_metadata is None:
            return _failure(
                CandidatePlanningFailureCode.WORKFLOW_NOT_CANDIDATE,
                "Workflow is missing candidate audit metadata.",
            )
        if session.snapshot.execution_intent != _SUPPORTED_INTENT:
            return _failure(
                CandidatePlanningFailureCode.IMPLEMENTATION_NOT_SUPPORTED,
                "Atlas Agent cannot translate this candidate intent yet.",
            )
        if session.snapshot.target_type != "repository" or session.snapshot.target_id not in _ALLOWED_TARGETS:
            return _failure(
                CandidatePlanningFailureCode.IMPLEMENTATION_NOT_SUPPORTED,
                "Candidate target is not supported for implementation translation.",
            )
        if repository.head_commit is None:
            return _failure(
                CandidatePlanningFailureCode.REPOSITORY_STALE,
                "Trusted repository HEAD is unavailable.",
            )
        if repository.head_commit != session.plan.repository_head:
            return _failure(
                CandidatePlanningFailureCode.REPOSITORY_STALE,
                "Trusted repository HEAD differs from the reviewed candidate plan.",
            )
        if repository.branch != session.plan.repository_branch:
            return _failure(
                CandidatePlanningFailureCode.REPOSITORY_STALE,
                "Trusted repository branch differs from the reviewed candidate plan.",
            )
        try:
            validate_candidate_plan_safe(session.plan)
            affected_files = _validate_affected_files(session.plan.likely_affected_files)
        except ValueError:
            return _failure(
                CandidatePlanningFailureCode.UNSAFE_TRANSLATION,
                "Candidate plan is not safe for implementation translation.",
            )
        plan_fingerprint = candidate_plan_fingerprint(session.plan)
        identifier = implementation_request_id(
            workflow_id=workflow.identifier,
            candidate_id=session.candidate_id,
            candidate_fingerprint=session.candidate_fingerprint,
            plan_fingerprint=plan_fingerprint,
            repository_head=repository.head_commit,
            translator_version=TRANSLATOR_VERSION,
        )
        argv = _argv_for_candidate(session=session, affected_files=affected_files)
        request = CandidateImplementationRequest(
            identifier=identifier,
            workflow_session_id=workflow.identifier,
            candidate_planning_session_id=session.identifier,
            candidate_id=session.candidate_id,
            candidate_fingerprint=session.candidate_fingerprint,
            candidate_plan_id=session.plan.identifier,
            candidate_plan_fingerprint=plan_fingerprint,
            execution_intent=session.snapshot.execution_intent,
            repository_root=repository.root,
            repository_branch=repository.branch,
            repository_head=repository.head_commit,
            argv=argv,
            working_directory=repository.root,
            affected_files=affected_files,
            evidence_ids=session.snapshot.evidence_ids,
            compatibility_assessment_id=session.snapshot.compatibility_assessment_id,
            compatibility_status=session.snapshot.compatibility_status,
            translator_version=TRANSLATOR_VERSION,
            generated_at=generated_at,
        )
        policy_result = self._tool_policy.validate(_execution_request_for_validation(request))
        if not hasattr(policy_result, "argv"):
            return _failure(
                CandidatePlanningFailureCode.UNSAFE_TRANSLATION,
                "Translated implementation request was rejected by execution policy.",
            )
        return CandidateImplementationDecision(request=request)


def implementation_request_id(
    *,
    workflow_id: str,
    candidate_id: str,
    candidate_fingerprint: str,
    plan_fingerprint: str,
    repository_head: str,
    translator_version: str,
) -> str:
    """Build a deterministic implementation request ID."""

    digest = hashlib.sha256(
        f"{workflow_id}\0{candidate_id}\0{candidate_fingerprint}\0"
        f"{plan_fingerprint}\0{repository_head}\0{translator_version}".encode()
    ).hexdigest()
    return f"candidate-implementation-v1-{digest}"


def _validate_affected_files(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    if not paths:
        raise ValueError("Candidate implementation requires affected files.")
    normalized: list[Path] = []
    for path in paths:
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Candidate affected files must be repository-relative.")
        normalized.append(path)
    result = tuple(sorted(set(normalized), key=lambda item: item.as_posix()))
    if set(result) != _ALLOWED_AFFECTED_FILES:
        raise ValueError("Candidate affected files are not allowlisted.")
    return result


def _argv_for_candidate(
    *,
    session: CandidatePlanningSession,
    affected_files: tuple[Path, ...],
) -> tuple[str, ...]:
    assert session.plan is not None
    prompt = "\n".join(
        (
            "Atlas Agent candidate implementation request.",
            "Implement only the approved update-compose-stack candidate.",
            f"Candidate ID: {session.candidate_id}",
            f"Candidate fingerprint: {session.candidate_fingerprint}",
            f"Candidate plan ID: {session.plan.identifier}",
            f"Candidate plan fingerprint: {candidate_plan_fingerprint(session.plan)}",
            f"Target: {session.snapshot.target_type}:{session.snapshot.target_id}",
            "Affected repository files: "
            + ", ".join(path.as_posix() for path in affected_files),
            "Preserve unrelated services and configuration.",
            "Do not modify runtime data, secrets, logs, or jcode directories.",
            "Stop after preparing the repository change for later verification and review.",
        )
    )
    return ("codex", "implement", prompt)


def _execution_request_for_validation(
    request: CandidateImplementationRequest,
) -> ExecutionRequest:
    plan = ImplementationPlan(
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
    return ExecutionRequest(
        identifier=request.identifier,
        plan=plan,
        argv=request.argv,
        working_directory=request.working_directory,
    )


def _failure(
    code: CandidatePlanningFailureCode,
    message: str,
) -> CandidateImplementationDecision:
    return CandidateImplementationDecision(
        failure=CandidatePlanningFailure(code=code, message=message)
    )
