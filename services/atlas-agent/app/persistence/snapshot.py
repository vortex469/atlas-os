"""File-backed aggregate state persistence for Atlas Agent."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, MutableMapping
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from inspect import signature
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    CommitApprovalMetadata,
    VerificationApprovalCheck,
    VerificationApprovalEnvironment,
)
from app.approval.repository import ApprovalRepository
from app.candidate_planning.models import (
    CandidateImplementationRequest,
    CandidatePlan,
    CandidatePlanningFailure,
    CandidatePlanningFailureCode,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    ComposeMutationSpecification,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.state import (
    CandidatePlanningStateSnapshot,
    CandidatePlanningStateStore,
)
from app.candidate_planning.verification import (
    CandidateReviewResult,
    CandidateVerificationCheckEvidence,
    CandidateVerificationEvidence,
    CandidateVerificationFailureCode,
    CandidateVerificationPlan,
)
from app.context.models import AgentContext
from app.execution.models import EnvironmentVariable, ExecutionResult, ExecutionStatus
from app.execution.worker_contracts import WorkerExecutionResult
from app.model_providers.models import ModelResponse
from app.planning.models import ImplementationPlan, PlanRisk, RoadmapCheckpoint
from app.repository.models import CommitRequest, CommitResult
from app.review.models import (
    ArchitectureAssessment,
    ReviewCategory,
    ReviewFinding,
    ReviewReport,
    ReviewSeverity,
    ReviewStatus,
    TestEvidence,
)
from app.verification.models import (
    VerificationCheck,
    VerificationCheckResult,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.models import (
    CandidateWorkflowMetadata,
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)
from app.workflow.state import WorkflowStateSnapshot, WorkflowStateStore

SCHEMA_VERSION = 1
APPLICATION = "atlas-agent"
SNAPSHOT_FILENAME = "atlas-agent-state.json"
_ENV_DIGEST_LENGTH = 64
_INTERRUPTION_REASONS = {
    WorkflowSessionState.EXECUTING: "implementation interrupted by process restart",
    WorkflowSessionState.VERIFYING: "verification or review interrupted by process restart",
    WorkflowSessionState.COMMITTING: "commit interrupted by process restart",
}
_WAITING_PURPOSES = {
    WorkflowSessionState.AWAITING_APPROVAL: ApprovalPurpose.IMPLEMENTATION,
    WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL: ApprovalPurpose.IMPLEMENTATION,
    WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL: ApprovalPurpose.VERIFICATION,
    WorkflowSessionState.AWAITING_COMMIT_APPROVAL: ApprovalPurpose.COMMIT,
}

T = TypeVar("T")


class StatePersistenceError(RuntimeError):
    """Raised when persisted Agent state cannot be loaded or written safely."""


class CandidateWorkflowState:
    """Mutable candidate workflow state used inside aggregate transactions."""

    def __init__(self, snapshot: WorkflowStateSnapshot) -> None:
        self.sprint, self.verification, self.review, sessions = snapshot
        self.sessions = dict(sessions)

    def create_session(self, session: WorkflowSession) -> None:
        if not session.identifier.strip():
            raise ValueError("Workflow session identifier must not be blank")
        if session.identifier in self.sessions:
            raise ValueError(
                "Workflow session identifier already exists: "
                f"{session.identifier}"
            )
        self.sessions[session.identifier] = session

    def delete_session(self, identifier: str) -> bool:
        return self.sessions.pop(identifier, None) is not None

    def get_session(self, identifier: str) -> WorkflowSession | None:
        return self.sessions.get(identifier)

    def transition_session(
        self,
        identifier: str,
        expected_state: WorkflowSessionState,
        new_state: WorkflowSessionState,
        **artifacts: object,
    ) -> bool:
        session = self.sessions.get(identifier)
        if session is None or session.state is not expected_state:
            return False
        self.sessions[identifier] = replace(session, state=new_state, **artifacts)
        return True

    def publish_sprint(self, status: SprintStatus) -> None:
        self.sprint = status

    def publish_verification(self, report: VerificationReport) -> None:
        self.verification = report

    def publish_review(self, report: ReviewReport) -> None:
        self.review = report

    def snapshot(self) -> WorkflowStateSnapshot:
        return (self.sprint, self.verification, self.review, dict(self.sessions))


class CandidateApprovalRepository:
    """Mutable candidate approval state used inside aggregate transactions."""

    def __init__(self, snapshot: MutableMapping[str, ApprovalResult]) -> None:
        self.storage = dict(snapshot)

    def save_request(self, request: ApprovalRequest) -> str:
        identifier = request.identifier
        if identifier in self.storage:
            raise ValueError(f"Approval request already exists: {identifier}")
        decision = ApprovalDecision(request=request, status=ApprovalStatus.PENDING)
        self.storage[identifier] = ApprovalResult(decision=decision)
        return identifier

    def get_request(self, identifier: str) -> ApprovalResult | None:
        return self.storage.get(identifier)

    def update_decision(self, identifier: str, decision: ApprovalDecision) -> bool:
        current = self.storage.get(identifier)
        if current is None:
            return False
        if current.decision.status is not ApprovalStatus.PENDING:
            return False
        if decision.request != current.decision.request:
            return False
        self.storage[identifier] = ApprovalResult(decision=decision)
        return True

    def supersede_pending_request(
        self,
        *,
        identifier: str,
        expected_request: ApprovalRequest,
        replacement_request: ApprovalRequest,
    ) -> bool:
        if replacement_request.identifier != identifier:
            return False
        current = self.storage.get(identifier)
        if current is None:
            return False
        if current.decision.status is not ApprovalStatus.PENDING:
            return False
        if current.decision.request != expected_request:
            return False
        decision = ApprovalDecision(request=replacement_request, status=ApprovalStatus.PENDING)
        self.storage[identifier] = ApprovalResult(decision=decision)
        return True

    def snapshot(self) -> dict[str, ApprovalResult]:
        return dict(self.storage)


class CandidatePlanningSessionsState:
    """Mutable candidate-planning session state used inside aggregate transactions."""

    def __init__(self, snapshot: CandidatePlanningStateSnapshot) -> None:
        self.sessions = dict(snapshot)

    def create_session(self, session: CandidatePlanningSession) -> None:
        if not session.identifier.strip():
            raise ValueError("Candidate planning session identifier must not be blank")
        if session.identifier in self.sessions:
            raise ValueError(
                "Candidate planning session identifier already exists: "
                f"{session.identifier}"
            )
        self.sessions[session.identifier] = session

    def get_session(self, identifier: str) -> CandidatePlanningSession | None:
        return self.sessions.get(identifier)

    def replace_session(self, session: CandidatePlanningSession) -> None:
        if not session.identifier.strip():
            raise ValueError("Candidate planning session identifier must not be blank")
        if session.identifier not in self.sessions:
            raise ValueError(
                "Candidate planning session identifier does not exist: "
                f"{session.identifier}"
            )
        self.sessions[session.identifier] = session

    def snapshot(self) -> CandidatePlanningStateSnapshot:
        return dict(self.sessions)


class AgentStatePersistenceCoordinator:
    """Own the unified file-backed workflow and approval snapshot."""

    def __init__(
        self,
        *,
        state_dir: Path,
        workflow_state: WorkflowStateStore,
        approval_repository: ApprovalRepository,
        candidate_planning_state: CandidatePlanningStateStore | None = None,
    ) -> None:
        self._state_dir = state_dir
        self._snapshot_path = state_dir / SNAPSHOT_FILENAME
        self._workflow_state = workflow_state
        self._approval_repository = approval_repository
        self._candidate_planning_state = candidate_planning_state
        self._lock = RLock()

    @property
    def snapshot_path(self) -> Path:
        """Return the canonical snapshot path."""

        return self._snapshot_path

    def initialize(self) -> None:
        """Validate the state directory and load persisted state if present."""

        with self._lock:
            self._prepare_state_dir()
            if not self._snapshot_path.exists():
                return
            payload = self._read_snapshot()
            workflow_snapshot, approval_snapshot, candidate_planning_snapshot = self._decode_payload(payload)
            workflow_candidate = CandidateWorkflowState(workflow_snapshot)
            approval_candidate = CandidateApprovalRepository(approval_snapshot)
            candidate_planning_candidate = CandidatePlanningSessionsState(candidate_planning_snapshot)
            transformed = self._recover_claimed_sessions(workflow_candidate)
            self._validate_aggregate(workflow_candidate, approval_candidate)
            if transformed:
                self._write_payload(
                    self._encode_payload(
                        workflow_candidate.snapshot(),
                        approval_candidate.snapshot(),
                        candidate_planning_candidate.snapshot(),
                    )
                )
            self._workflow_state.replace_snapshot(workflow_candidate.snapshot())
            self._approval_repository.replace_snapshot(approval_candidate.snapshot())
            if self._candidate_planning_state is not None:
                self._candidate_planning_state.replace_snapshot(candidate_planning_candidate.snapshot())

    def persist_current_state(self) -> None:
        """Persist the current live stores as one validated snapshot."""

        with self._lock:
            workflow_candidate = CandidateWorkflowState(
                self._workflow_state.export_snapshot()
            )
            approval_candidate = CandidateApprovalRepository(
                self._approval_repository.export_snapshot()
            )
            candidate_planning_candidate = CandidatePlanningSessionsState(
                self._candidate_planning_state.export_snapshot()
                if self._candidate_planning_state is not None
                else {}
            )
            self._commit_candidates(workflow_candidate, approval_candidate, candidate_planning_candidate)

    def mutate_workflow(self, mutation: Callable[[CandidateWorkflowState], T]) -> T:
        """Apply and persist one workflow-only mutation atomically."""

        return self.mutate_aggregate(lambda workflow, _approvals, _candidate_planning: mutation(workflow))

    def mutate_approval(self, mutation: Callable[[CandidateApprovalRepository], T]) -> T:
        """Apply and persist one approval-only mutation atomically."""

        return self.mutate_aggregate(lambda _workflow, approvals, _candidate_planning: mutation(approvals))

    def mutate_candidate_planning(
        self,
        mutation: Callable[[CandidatePlanningSessionsState], T],
    ) -> T:
        """Apply and persist one candidate-planning-only mutation atomically."""

        return self.mutate_aggregate(
            lambda _workflow, _approvals, candidate_planning: mutation(candidate_planning)
        )

    def mutate_aggregate(
        self,
        mutation: Callable[
            [CandidateWorkflowState, CandidateApprovalRepository, CandidatePlanningSessionsState],
            T,
        ],
    ) -> T:
        """Apply one aggregate mutation with durable rollback semantics."""

        with self._lock:
            workflow_candidate = CandidateWorkflowState(
                self._workflow_state.export_snapshot()
            )
            approval_candidate = CandidateApprovalRepository(
                self._approval_repository.export_snapshot()
            )
            candidate_planning_candidate = CandidatePlanningSessionsState(
                self._candidate_planning_state.export_snapshot()
                if self._candidate_planning_state is not None
                else {}
            )
            parameter_count = len(signature(mutation).parameters)
            if parameter_count == 2:
                result = mutation(workflow_candidate, approval_candidate)  # type: ignore[misc]
            else:
                result = mutation(
                    workflow_candidate,
                    approval_candidate,
                    candidate_planning_candidate,
                )
            self._commit_candidates(
                workflow_candidate,
                approval_candidate,
                candidate_planning_candidate,
            )
            return result

    def _commit_candidates(
        self,
        workflow_candidate: CandidateWorkflowState,
        approval_candidate: CandidateApprovalRepository,
        candidate_planning_candidate: CandidatePlanningSessionsState,
    ) -> None:
        self._validate_aggregate(workflow_candidate, approval_candidate)
        workflow_snapshot = workflow_candidate.snapshot()
        approval_snapshot = approval_candidate.snapshot()
        candidate_planning_snapshot = candidate_planning_candidate.snapshot()
        self._write_payload(
            self._encode_payload(
                workflow_snapshot,
                approval_snapshot,
                candidate_planning_snapshot,
            )
        )
        self._workflow_state.replace_snapshot(workflow_snapshot)
        self._approval_repository.replace_snapshot(approval_snapshot)
        if self._candidate_planning_state is not None:
            self._candidate_planning_state.replace_snapshot(candidate_planning_snapshot)

    def _prepare_state_dir(self) -> None:
        try:
            self._state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as exc:
            raise StatePersistenceError(
                f"Failed to create state directory: {self._state_dir}"
            ) from exc
        if not self._state_dir.is_dir():
            raise StatePersistenceError(
                f"State path is not a directory: {self._state_dir}"
            )
        if not os.access(self._state_dir, os.R_OK | os.W_OK | os.X_OK):
            raise StatePersistenceError(
                f"State directory is not readable and writable: {self._state_dir}"
            )

    def _read_snapshot(self) -> dict[str, Any]:
        try:
            with self._snapshot_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise StatePersistenceError("Persisted Agent state is corrupt JSON") from exc
        except OSError as exc:
            raise StatePersistenceError("Persisted Agent state cannot be read") from exc
        if not isinstance(payload, dict):
            raise StatePersistenceError("Persisted Agent state must be a JSON object")
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._prepare_state_dir()
        data = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        temp_path = self._snapshot_path.with_name(
            f".{self._snapshot_path.name}.{os.getpid()}.tmp"
        )
        try:
            with temp_path.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._snapshot_path)
            directory_fd = os.open(self._state_dir, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise StatePersistenceError("Persisted Agent state cannot be written") from exc

    def _encode_payload(
        self,
        workflow_snapshot: WorkflowStateSnapshot,
        approval_snapshot: dict[str, ApprovalResult],
        candidate_planning_snapshot: CandidatePlanningStateSnapshot | None = None,
    ) -> dict[str, Any]:
        sprint, verification, review, sessions = workflow_snapshot
        candidate_planning_snapshot = candidate_planning_snapshot or {}
        return {
            "application": APPLICATION,
            "approvals": {
                identifier: _encode_approval_result(result)
                for identifier, result in sorted(approval_snapshot.items())
            },
            "candidate_planning": {
                "sessions": {
                    identifier: _encode_candidate_planning_session(session)
                    for identifier, session in sorted(candidate_planning_snapshot.items())
                },
            },
            "schema_version": SCHEMA_VERSION,
            "workflow_state": {
                "review": _encode_review_report(review),
                "sessions": {
                    identifier: _encode_workflow_session(session)
                    for identifier, session in sorted(sessions.items())
                },
                "sprint": _encode_sprint_status(sprint),
                "verification": _encode_verification_report(verification),
            },
        }

    def _decode_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[WorkflowStateSnapshot, dict[str, ApprovalResult], CandidatePlanningStateSnapshot]:
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise StatePersistenceError("Persisted Agent state schema is unsupported")
        if payload.get("application") != APPLICATION:
            raise StatePersistenceError("Persisted Agent state application is invalid")
        workflow_state = _require_dict(payload, "workflow_state")
        approvals_payload = _require_dict(payload, "approvals")
        sessions_payload = _require_dict(workflow_state, "sessions")
        sessions = {
            identifier: _decode_workflow_session(session_payload)
            for identifier, session_payload in sessions_payload.items()
        }
        approvals = {
            identifier: _decode_approval_result(result_payload)
            for identifier, result_payload in approvals_payload.items()
        }
        candidate_planning_payload = payload.get("candidate_planning", {})
        if candidate_planning_payload is None:
            candidate_planning_payload = {}
        if not isinstance(candidate_planning_payload, dict):
            raise StatePersistenceError("Invalid candidate planning state")
        candidate_sessions_payload = candidate_planning_payload.get("sessions", {})
        if not isinstance(candidate_sessions_payload, dict):
            raise StatePersistenceError("Invalid candidate planning sessions")
        candidate_planning = {
            identifier: _decode_candidate_planning_session(session_payload)
            for identifier, session_payload in candidate_sessions_payload.items()
        }
        workflow_snapshot: WorkflowStateSnapshot = (
            _decode_sprint_status(workflow_state.get("sprint")),
            _decode_verification_report(workflow_state.get("verification")),
            _decode_review_report(workflow_state.get("review")),
            sessions,
        )
        return workflow_snapshot, approvals, candidate_planning

    def _recover_claimed_sessions(
        self,
        workflow_candidate: CandidateWorkflowState,
    ) -> bool:
        transformed = False
        for identifier, session in tuple(workflow_candidate.sessions.items()):
            reason = _INTERRUPTION_REASONS.get(session.state)
            if reason is None:
                continue
            workflow_candidate.sessions[identifier] = replace(
                session,
                state=WorkflowSessionState.BLOCKED,
                blocked_reason=reason,
            )
            transformed = True
        return transformed

    def _validate_aggregate(
        self,
        workflow: CandidateWorkflowState,
        approvals: CandidateApprovalRepository,
    ) -> None:
        for identifier, session in workflow.sessions.items():
            if identifier != session.identifier:
                raise StatePersistenceError("Workflow session key does not match identifier")
            purpose = _WAITING_PURPOSES.get(session.state)
            if purpose is None:
                continue
            approval_id = _approval_id_for(session.identifier, purpose)
            result = approvals.storage.get(approval_id)
            if result is None:
                raise StatePersistenceError("Waiting workflow is missing approval request")
            request = result.decision.request
            if request.workflow_id != session.identifier or request.purpose is not purpose:
                raise StatePersistenceError("Waiting workflow approval does not match")
            if purpose is ApprovalPurpose.COMMIT:
                _validate_commit_approval_matches_session(request, session)

        for identifier, result in approvals.storage.items():
            request = result.decision.request
            if identifier != request.identifier:
                raise StatePersistenceError("Approval key does not match request identifier")
            if result.decision.request != request:
                raise StatePersistenceError("Approval decision request mismatch")
            _validate_approval_request(request)
            if request.workflow_id is None:
                continue
            session = workflow.sessions.get(request.workflow_id)
            if session is None:
                raise StatePersistenceError("Workflow approval references missing workflow")


def _approval_id_for(workflow_id: str, purpose: ApprovalPurpose) -> str:
    if purpose is ApprovalPurpose.IMPLEMENTATION:
        return f"approval-{workflow_id}"
    if purpose is ApprovalPurpose.VERIFICATION:
        return f"approval-verification-{workflow_id}"
    return f"approval-commit-{workflow_id}"


def _validate_commit_approval_matches_session(
    request: ApprovalRequest,
    session: WorkflowSession,
) -> None:
    metadata = request.commit_metadata
    if metadata is None:
        raise StatePersistenceError("Commit approval metadata is missing")
    if session.reviewed_content_fingerprint != metadata.reviewed_content_fingerprint:
        raise StatePersistenceError("Commit approval fingerprint mismatch")
    if session.expected_branch != metadata.expected_branch:
        raise StatePersistenceError("Commit approval branch mismatch")
    if session.expected_head != metadata.expected_head:
        raise StatePersistenceError("Commit approval head mismatch")
    if tuple(sorted(session.reviewed_files)) != metadata.reviewed_files:
        raise StatePersistenceError("Commit approval reviewed files mismatch")
    if session.commit_request is None:
        raise StatePersistenceError("Commit approval session request is missing")
    if session.commit_request.message != metadata.commit_message:
        raise StatePersistenceError("Commit approval message mismatch")


def _validate_approval_request(request: ApprovalRequest) -> None:
    if request.purpose is ApprovalPurpose.COMMIT:
        if request.commit_metadata is None:
            raise StatePersistenceError("Commit approval metadata is required")
        _validate_digest(request.commit_metadata.reviewed_content_fingerprint)
    elif request.commit_metadata is not None:
        raise StatePersistenceError("Only commit approvals may contain commit metadata")
    for check in request.verification_checks:
        for variable in check.environment:
            _validate_digest(variable.value_digest)


def _validate_digest(value: str) -> None:
    if len(value) != _ENV_DIGEST_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise StatePersistenceError("Malformed SHA-256 digest metadata")


def _path(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _decode_path(value: Any) -> Path:
    if not isinstance(value, str):
        raise StatePersistenceError("Expected path string")
    return Path(value)


def _decode_optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    return _decode_path(value)


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise StatePersistenceError(f"Expected object field: {key}")
    return value


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise StatePersistenceError(f"Expected string field: {key}")
    return value


def _tuple_str(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise StatePersistenceError("Expected list of strings")
    if not all(isinstance(value, str) for value in values):
        raise StatePersistenceError("Expected list of strings")
    return tuple(values)


def _tuple_path(values: Any) -> tuple[Path, ...]:
    if not isinstance(values, list):
        raise StatePersistenceError("Expected list of paths")
    return tuple(_decode_path(value) for value in values)


def _encode_sprint_status(status: SprintStatus | None) -> dict[str, Any] | None:
    if status is None:
        return None
    return {
        "checkpoint_id": status.checkpoint_id,
        "goal": status.goal,
        "phase": status.phase.value,
        "title": status.title,
    }


def _decode_sprint_status(payload: Any) -> SprintStatus | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid sprint status")
    return SprintStatus(
        checkpoint_id=_require_str(payload, "checkpoint_id"),
        title=_require_str(payload, "title"),
        goal=_require_str(payload, "goal"),
        phase=SprintPhase(_require_str(payload, "phase")),
    )


def _encode_roadmap_checkpoint(checkpoint: RoadmapCheckpoint) -> dict[str, Any]:
    return {
        "affected_files": [_path(path) for path in checkpoint.affected_files],
        "goal": checkpoint.goal,
        "identifier": checkpoint.identifier,
        "required_tests": list(checkpoint.required_tests),
        "risks": list(checkpoint.risks),
        "scope_items": list(checkpoint.scope_items),
        "title": checkpoint.title,
    }


def _decode_roadmap_checkpoint(payload: dict[str, Any]) -> RoadmapCheckpoint:
    return RoadmapCheckpoint(
        identifier=_require_str(payload, "identifier"),
        title=_require_str(payload, "title"),
        goal=_require_str(payload, "goal"),
        scope_items=_tuple_str(payload.get("scope_items", [])),
        affected_files=_tuple_path(payload.get("affected_files", [])),
        required_tests=_tuple_str(payload.get("required_tests", [])),
        risks=_tuple_str(payload.get("risks", [])),
    )


def _encode_plan_risk(risk: PlanRisk) -> dict[str, Any]:
    return {"code": risk.code, "source": risk.source, "summary": risk.summary}


def _decode_plan_risk(payload: dict[str, Any]) -> PlanRisk:
    return PlanRisk(
        code=_require_str(payload, "code"),
        summary=_require_str(payload, "summary"),
        source=_require_str(payload, "source"),
    )


def _encode_plan(plan: ImplementationPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "affected_files": [_path(path) for path in plan.affected_files],
        "branch": plan.branch,
        "checkpoint_id": plan.checkpoint_id,
        "goal": plan.goal,
        "head_commit": plan.head_commit,
        "repository_root": _path(plan.repository_root),
        "required_tests": list(plan.required_tests),
        "risks": [_encode_plan_risk(risk) for risk in plan.risks],
        "scope_items": list(plan.scope_items),
        "title": plan.title,
    }


def _decode_plan(payload: dict[str, Any]) -> ImplementationPlan:
    return ImplementationPlan(
        checkpoint_id=_require_str(payload, "checkpoint_id"),
        title=_require_str(payload, "title"),
        goal=_require_str(payload, "goal"),
        repository_root=_decode_path(payload.get("repository_root")),
        branch=payload.get("branch"),
        head_commit=payload.get("head_commit"),
        scope_items=_tuple_str(payload.get("scope_items", [])),
        affected_files=_tuple_path(payload.get("affected_files", [])),
        required_tests=_tuple_str(payload.get("required_tests", [])),
        risks=tuple(_decode_plan_risk(item) for item in payload.get("risks", [])),
    )


def _decode_optional_plan(payload: Any) -> ImplementationPlan | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid implementation plan")
    return _decode_plan(payload)


def _encode_env(variable: EnvironmentVariable) -> dict[str, Any]:
    digest = variable.value_digest or sha256(variable.value.encode("utf-8")).hexdigest()
    return {"name": variable.name, "redacted": True, "value_sha256": digest}


def _decode_env(payload: dict[str, Any]) -> EnvironmentVariable:
    if payload.get("redacted") is True:
        digest = _require_str(payload, "value_sha256")
        _validate_digest(digest)
    else:
        # Backwards compatibility: older snapshots may still persist raw environment
        # values for verification checks. Reconstruct their digest and treat them as
        # redacted in memory so subsequent runs continue to require the same secret
        # at execution time.
        raw_value = payload.get("value")
        if not isinstance(raw_value, str):
            raise StatePersistenceError("Persisted environment value must be redacted")
        digest = sha256(raw_value.encode("utf-8")).hexdigest()

    return EnvironmentVariable(
        name=_require_str(payload, "name"),
        value="",
        value_digest=digest,
        redacted=True,
    )


def _encode_verification_check(check: VerificationCheck) -> dict[str, Any]:
    return {
        "argv": list(check.argv),
        "environment": [_encode_env(variable) for variable in check.environment],
        "identifier": check.identifier,
        "timeout_seconds": check.timeout_seconds,
        "working_directory": _path(check.working_directory),
    }


def _decode_verification_check(payload: dict[str, Any]) -> VerificationCheck:
    return VerificationCheck(
        identifier=_require_str(payload, "identifier"),
        argv=_tuple_str(payload.get("argv", [])),
        working_directory=_decode_path(payload.get("working_directory")),
        timeout_seconds=payload.get("timeout_seconds"),
        environment=tuple(
            _decode_env(item) for item in payload.get("environment", [])
        ),
    )


def _encode_architecture_assessment(assessment: ArchitectureAssessment) -> dict[str, Any]:
    return {
        "evidence": assessment.evidence,
        "identifier": assessment.identifier,
        "passed": assessment.passed,
        "recommendation": assessment.recommendation,
        "summary": assessment.summary,
    }


def _decode_architecture_assessment(payload: dict[str, Any]) -> ArchitectureAssessment:
    return ArchitectureAssessment(
        identifier=_require_str(payload, "identifier"),
        summary=_require_str(payload, "summary"),
        passed=bool(payload.get("passed")),
        evidence=_require_str(payload, "evidence"),
        recommendation=payload.get("recommendation"),
    )


def _encode_test_evidence(evidence: TestEvidence) -> dict[str, Any]:
    return {
        "check_identifier": evidence.check_identifier,
        "requirement": evidence.requirement,
    }


def _decode_test_evidence(payload: dict[str, Any]) -> TestEvidence:
    return TestEvidence(
        requirement=_require_str(payload, "requirement"),
        check_identifier=_require_str(payload, "check_identifier"),
    )


def _encode_workflow_request(request: WorkflowRequest | None) -> dict[str, Any] | None:
    if request is None:
        return None
    return {
        "architecture_assessments": [
            _encode_architecture_assessment(item)
            for item in request.architecture_assessments
        ],
        "checkpoint": _encode_roadmap_checkpoint(request.checkpoint),
        "execution_argv": list(request.execution_argv),
        "execution_identifier": request.execution_identifier,
        "execution_workdir": _path(request.execution_workdir),
        "repository_root": _path(request.repository_root),
        "review_identifier": request.review_identifier,
        "test_evidence": [
            _encode_test_evidence(item) for item in request.test_evidence
        ],
        "verification_checks": [
            _encode_verification_check(check)
            for check in request.verification_checks
        ],
    }


def _decode_workflow_request(payload: dict[str, Any]) -> WorkflowRequest:
    return WorkflowRequest(
        checkpoint=_decode_roadmap_checkpoint(_require_dict(payload, "checkpoint")),
        repository_root=_decode_path(payload.get("repository_root")),
        execution_identifier=_require_str(payload, "execution_identifier"),
        execution_argv=_tuple_str(payload.get("execution_argv", [])),
        execution_workdir=_decode_path(payload.get("execution_workdir")),
        verification_checks=tuple(
            _decode_verification_check(item)
            for item in payload.get("verification_checks", [])
        ),
        review_identifier=_require_str(payload, "review_identifier"),
        architecture_assessments=tuple(
            _decode_architecture_assessment(item)
            for item in payload.get("architecture_assessments", [])
        ),
        test_evidence=tuple(
            _decode_test_evidence(item) for item in payload.get("test_evidence", [])
        ),
    )


def _decode_optional_workflow_request(payload: Any) -> WorkflowRequest | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid workflow request")
    return _decode_workflow_request(payload)


def _encode_context(context: AgentContext | None) -> dict[str, Any] | None:
    return None if context is None else context.model_dump(mode="json")


def _decode_context(payload: Any) -> AgentContext | None:
    return None if payload is None else AgentContext.model_validate(payload)


def _encode_datetime(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _decode_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StatePersistenceError("Invalid datetime value")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise StatePersistenceError("Invalid datetime value") from exc


def _decode_datetime(value: Any) -> datetime:
    decoded = _decode_optional_datetime(value)
    if decoded is None:
        raise StatePersistenceError("Missing datetime value")
    return decoded


def _encode_candidate_snapshot(snapshot: CandidateSnapshot) -> dict[str, Any]:
    return {
        "candidate_fingerprint": snapshot.candidate_fingerprint,
        "candidate_id": snapshot.candidate_id,
        "catalog_item_id": snapshot.catalog_item_id,
        "compatibility_assessment_id": snapshot.compatibility_assessment_id,
        "compatibility_status": snapshot.compatibility_status,
        "constraints": list(snapshot.constraints),
        "evidence_ids": list(snapshot.evidence_ids),
        "execution_category": snapshot.execution_category,
        "execution_intent": snapshot.execution_intent,
        "expires_at": _encode_datetime(snapshot.expires_at),
        "intake_reason_codes": list(snapshot.intake_reason_codes),
        "intake_status": snapshot.intake_status.value,
        "intake_timestamp": _encode_datetime(snapshot.intake_timestamp),
        "rationale": snapshot.rationale,
        "recommendation_class": snapshot.recommendation_class,
        "relationship_ids": list(snapshot.relationship_ids),
        "required_approval_level": snapshot.required_approval_level,
        "source_recommendation_id": snapshot.source_recommendation_id,
        "source_subsystem": snapshot.source_subsystem,
        "target_id": snapshot.target_id,
        "target_type": snapshot.target_type,
        "mutation": _encode_compose_mutation(snapshot.mutation),
    }


def _decode_candidate_snapshot(payload: dict[str, Any]) -> CandidateSnapshot:
    return CandidateSnapshot(
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        source_recommendation_id=_require_str(payload, "source_recommendation_id"),
        source_subsystem=_require_str(payload, "source_subsystem"),
        recommendation_class=_require_str(payload, "recommendation_class"),
        catalog_item_id=payload.get("catalog_item_id"),
        target_id=_require_str(payload, "target_id"),
        target_type=_require_str(payload, "target_type"),
        execution_category=_require_str(payload, "execution_category"),
        execution_intent=_require_str(payload, "execution_intent"),
        required_approval_level=_require_str(payload, "required_approval_level"),
        rationale=_require_str(payload, "rationale"),
        constraints=_tuple_str(payload.get("constraints", [])),
        evidence_ids=_tuple_str(payload.get("evidence_ids", [])),
        compatibility_assessment_id=payload.get("compatibility_assessment_id"),
        compatibility_status=payload.get("compatibility_status"),
        relationship_ids=_tuple_str(payload.get("relationship_ids", [])),
        expires_at=_decode_optional_datetime(payload.get("expires_at")),
        intake_status=CoreCandidatePlanningIntakeStatus(_require_str(payload, "intake_status")),
        intake_reason_codes=_tuple_str(payload.get("intake_reason_codes", [])),
        intake_timestamp=_decode_datetime(payload.get("intake_timestamp")),
        mutation=_decode_compose_mutation(payload.get("mutation")),
    )


def _encode_compose_mutation(mutation: ComposeMutationSpecification | None) -> dict[str, Any] | None:
    if mutation is None:
        return None
    return {
        "file": _path(mutation.file),
        "service": mutation.service,
        "property": mutation.property,
        "operation": mutation.operation,
        "expected_value": mutation.expected_value,
        "desired_value": mutation.desired_value,
        "preservation_constraints": list(mutation.preservation_constraints),
    }


def _decode_compose_mutation(payload: Any) -> ComposeMutationSpecification | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid compose mutation specification")
    return ComposeMutationSpecification(
        file=_decode_path(payload.get("file")),
        service=_require_str(payload, "service"),
        property=_require_str(payload, "property"),
        operation=_require_str(payload, "operation"),
        expected_value=payload.get("expected_value"),
        desired_value=_require_str(payload, "desired_value"),
        preservation_constraints=_tuple_str(payload.get("preservation_constraints", [])),
    )


def _encode_candidate_planning_failure(
    failure: CandidatePlanningFailure | None,
) -> dict[str, Any] | None:
    if failure is None:
        return None
    return {"code": failure.code.value, "message": failure.message}


def _decode_candidate_planning_failure(
    payload: Any,
) -> CandidatePlanningFailure | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate planning failure")
    return CandidatePlanningFailure(
        code=CandidatePlanningFailureCode(_require_str(payload, "code")),
        message=_require_str(payload, "message"),
    )


def _encode_candidate_plan(plan: CandidatePlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "assumptions": list(plan.assumptions),
        "candidate_fingerprint": plan.candidate_fingerprint,
        "candidate_id": plan.candidate_id,
        "constraints": list(plan.constraints),
        "created_at": _encode_datetime(plan.created_at),
        "evidence_ids": list(plan.evidence_ids),
        "identifier": plan.identifier,
        "likely_affected_components": list(plan.likely_affected_components),
        "likely_affected_files": [_path(path) for path in plan.likely_affected_files],
        "objective": plan.objective,
        "proposed_steps": list(plan.proposed_steps),
        "repository_branch": plan.repository_branch,
        "repository_head": plan.repository_head,
        "repository_root": _path(plan.repository_root),
        "revalidated_candidate_fingerprint": plan.revalidated_candidate_fingerprint,
        "rollback_considerations": list(plan.rollback_considerations),
        "session_id": plan.session_id,
        "title": plan.title,
        "unresolved_questions": list(plan.unresolved_questions),
        "verification_strategy": list(plan.verification_strategy),
        "mutation": _encode_compose_mutation(plan.mutation),
    }


def _decode_candidate_plan(payload: Any) -> CandidatePlan | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate plan")
    return CandidatePlan(
        identifier=_require_str(payload, "identifier"),
        session_id=_require_str(payload, "session_id"),
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        title=_require_str(payload, "title"),
        objective=_require_str(payload, "objective"),
        assumptions=_tuple_str(payload.get("assumptions", [])),
        constraints=_tuple_str(payload.get("constraints", [])),
        proposed_steps=_tuple_str(payload.get("proposed_steps", [])),
        likely_affected_components=_tuple_str(
            payload.get("likely_affected_components", [])
        ),
        likely_affected_files=_tuple_path(payload.get("likely_affected_files", [])),
        verification_strategy=_tuple_str(payload.get("verification_strategy", [])),
        rollback_considerations=_tuple_str(payload.get("rollback_considerations", [])),
        unresolved_questions=_tuple_str(payload.get("unresolved_questions", [])),
        evidence_ids=_tuple_str(payload.get("evidence_ids", [])),
        created_at=_decode_datetime(payload.get("created_at")),
        repository_root=_decode_path(payload.get("repository_root")),
        repository_branch=payload.get("repository_branch"),
        repository_head=payload.get("repository_head"),
        revalidated_candidate_fingerprint=_require_str(
            payload,
            "revalidated_candidate_fingerprint",
        ),
        mutation=_decode_compose_mutation(payload.get("mutation")),
    )


def _encode_candidate_planning_session(session: CandidatePlanningSession) -> dict[str, Any]:
    return {
        "candidate_fingerprint": session.candidate_fingerprint,
        "candidate_id": session.candidate_id,
        "candidate_plan_fingerprint": session.candidate_plan_fingerprint,
        "created_at": _encode_datetime(session.created_at),
        "identifier": session.identifier,
        "exact_implementation_approval_request_id": session.exact_implementation_approval_request_id,
        "implementation_request_id": session.implementation_request_id,
        "implementation_translation_completed_at": _encode_datetime(
            session.implementation_translation_completed_at
        ),
        "implementation_translation_status": session.implementation_translation_status.value
        if session.implementation_translation_status is not None
        else None,
        "implementation_approval_request_id": session.implementation_approval_request_id,
        "last_revalidation_fingerprint": session.last_revalidation_fingerprint,
        "last_revalidation_status": session.last_revalidation_status.value
        if session.last_revalidation_status is not None
        else None,
        "plan": _encode_candidate_plan(session.plan),
        "planning_completed_at": _encode_datetime(session.planning_completed_at),
        "planning_failure": _encode_candidate_planning_failure(session.planning_failure),
        "planning_started_at": _encode_datetime(session.planning_started_at),
        "planning_status": session.planning_status.value,
        "predecessor_session_id": session.predecessor_session_id,
        "successor_session_id": session.successor_session_id,
        "snapshot": _encode_candidate_snapshot(session.snapshot),
        "status": session.status.value,
        "unsupported_reason": session.unsupported_reason,
        "workflow_conversion_completed_at": _encode_datetime(
            session.workflow_conversion_completed_at
        ),
        "workflow_conversion_status": session.workflow_conversion_status.value
        if session.workflow_conversion_status is not None
        else None,
        "workflow_session_id": session.workflow_session_id,
    }


def _decode_candidate_planning_session(payload: Any) -> CandidatePlanningSession:
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate planning session")
    return CandidatePlanningSession(
        identifier=_require_str(payload, "identifier"),
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        status=CandidatePlanningSessionStatus(_require_str(payload, "status")),
        snapshot=_decode_candidate_snapshot(_require_dict(payload, "snapshot")),
        created_at=_decode_datetime(payload.get("created_at")),
        unsupported_reason=payload.get("unsupported_reason"),
        planning_status=CandidatePlanningSessionStatus(
            payload.get("planning_status", CandidatePlanningSessionStatus.READY_FOR_PLANNING.value)
        ),
        plan=_decode_candidate_plan(payload.get("plan")),
        planning_failure=_decode_candidate_planning_failure(
            payload.get("planning_failure")
        ),
        planning_started_at=_decode_optional_datetime(payload.get("planning_started_at")),
        planning_completed_at=_decode_optional_datetime(
            payload.get("planning_completed_at")
        ),
        last_revalidation_fingerprint=payload.get("last_revalidation_fingerprint"),
        last_revalidation_status=CoreCandidatePlanningIntakeStatus(
            payload["last_revalidation_status"]
        )
        if payload.get("last_revalidation_status") is not None
        else None,
        workflow_session_id=payload.get("workflow_session_id"),
        implementation_approval_request_id=payload.get("implementation_approval_request_id"),
        candidate_plan_fingerprint=payload.get("candidate_plan_fingerprint"),
        workflow_conversion_status=CandidatePlanningSessionStatus(
            payload["workflow_conversion_status"]
        )
        if payload.get("workflow_conversion_status") is not None
        else None,
        workflow_conversion_completed_at=_decode_optional_datetime(
            payload.get("workflow_conversion_completed_at")
        ),
        implementation_request_id=payload.get("implementation_request_id"),
        exact_implementation_approval_request_id=payload.get(
            "exact_implementation_approval_request_id"
        ),
        implementation_translation_status=CandidatePlanningSessionStatus(
            payload["implementation_translation_status"]
        )
        if payload.get("implementation_translation_status") is not None
        else None,
        implementation_translation_completed_at=_decode_optional_datetime(
            payload.get("implementation_translation_completed_at")
        ),
        predecessor_session_id=payload.get("predecessor_session_id"),
        successor_session_id=payload.get("successor_session_id"),
    )


def _encode_model_response(response: ModelResponse | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return {
        "model": response.model,
        "provider_id": response.provider_id,
        "text": response.text,
    }


def _decode_model_response(payload: Any) -> ModelResponse | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid model response")
    return ModelResponse(
        text=_require_str(payload, "text"),
        model=_require_str(payload, "model"),
        provider_id=_require_str(payload, "provider_id"),
    )


def _encode_execution_result(result: ExecutionResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "argv": list(result.argv),
        "checkpoint_id": result.checkpoint_id,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
        "request_id": result.request_id,
        "return_code": result.return_code,
        "status": result.status.value,
        "stderr": result.stderr,
        "stdout": result.stdout,
        "working_directory": _path(result.working_directory),
        "worker_result": (
            result.worker_result.to_dict()
            if isinstance(result.worker_result, WorkerExecutionResult)
            else None
        ),
    }


def _decode_execution_result(payload: Any) -> ExecutionResult | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid execution result")
    return ExecutionResult(
        request_id=_require_str(payload, "request_id"),
        checkpoint_id=_require_str(payload, "checkpoint_id"),
        argv=_tuple_str(payload.get("argv", [])),
        working_directory=_decode_path(payload.get("working_directory")),
        status=ExecutionStatus(_require_str(payload, "status")),
        return_code=payload.get("return_code"),
        stdout=_require_str(payload, "stdout"),
        stderr=_require_str(payload, "stderr"),
        duration_seconds=float(payload.get("duration_seconds")),
        error=payload.get("error"),
        worker_result=(
            WorkerExecutionResult.from_dict(payload["worker_result"])
            if payload.get("worker_result") is not None
            else None
        ),
    )


def _encode_verification_check_result(
    result: VerificationCheckResult,
) -> dict[str, Any]:
    return {
        "argv": list(result.argv),
        "duration_seconds": result.duration_seconds,
        "error": result.error,
        "identifier": result.identifier,
        "return_code": result.return_code,
        "status": result.status.value,
        "stderr": result.stderr,
        "stdout": result.stdout,
        "working_directory": _path(result.working_directory),
    }


def _decode_verification_check_result(payload: dict[str, Any]) -> VerificationCheckResult:
    return VerificationCheckResult(
        identifier=_require_str(payload, "identifier"),
        argv=_tuple_str(payload.get("argv", [])),
        working_directory=_decode_path(payload.get("working_directory")),
        status=VerificationStatus(_require_str(payload, "status")),
        return_code=payload.get("return_code"),
        stdout=_require_str(payload, "stdout"),
        stderr=_require_str(payload, "stderr"),
        duration_seconds=float(payload.get("duration_seconds")),
        error=payload.get("error"),
    )


def _encode_verification_report(report: VerificationReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "context": _encode_context(report.context),
        "duration_seconds": report.duration_seconds,
        "repository_root": _path(report.repository_root),
        "results": [
            _encode_verification_check_result(result) for result in report.results
        ],
        "status": report.status.value,
    }


def _decode_verification_report(payload: Any) -> VerificationReport | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid verification report")
    return VerificationReport(
        repository_root=_decode_path(payload.get("repository_root")),
        results=tuple(
            _decode_verification_check_result(item)
            for item in payload.get("results", [])
        ),
        status=VerificationStatus(_require_str(payload, "status")),
        duration_seconds=float(payload.get("duration_seconds")),
        context=_decode_context(payload.get("context")),
    )


def _encode_review_finding(finding: ReviewFinding) -> dict[str, Any]:
    return {
        "category": finding.category.value,
        "code": finding.code,
        "evidence": finding.evidence,
        "recommendation": finding.recommendation,
        "severity": finding.severity.value,
        "summary": finding.summary,
    }


def _decode_review_finding(payload: dict[str, Any]) -> ReviewFinding:
    return ReviewFinding(
        code=_require_str(payload, "code"),
        category=ReviewCategory(_require_str(payload, "category")),
        severity=ReviewSeverity(_require_str(payload, "severity")),
        summary=_require_str(payload, "summary"),
        evidence=_require_str(payload, "evidence"),
        recommendation=_require_str(payload, "recommendation"),
    )


def _encode_review_report(report: ReviewReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "checkpoint_id": report.checkpoint_id,
        "findings": [_encode_review_finding(finding) for finding in report.findings],
        "recommendations": list(report.recommendations),
        "request_id": report.request_id,
        "status": report.status.value,
    }


def _decode_review_report(payload: Any) -> ReviewReport | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid review report")
    return ReviewReport(
        request_id=_require_str(payload, "request_id"),
        checkpoint_id=_require_str(payload, "checkpoint_id"),
        status=ReviewStatus(_require_str(payload, "status")),
        findings=tuple(
            _decode_review_finding(item) for item in payload.get("findings", [])
        ),
        recommendations=_tuple_str(payload.get("recommendations", [])),
    )


def _encode_commit_request(request: CommitRequest | None) -> dict[str, Any] | None:
    if request is None:
        return None
    return {
        "expected_branch": request.expected_branch,
        "expected_head": request.expected_head,
        "message": request.message,
        "paths": [_path(path) for path in request.paths],
        "repository_root": _path(request.repository_root),
    }


def _decode_commit_request(payload: Any) -> CommitRequest | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid commit request")
    return CommitRequest(
        repository_root=_decode_path(payload.get("repository_root")),
        expected_branch=payload.get("expected_branch"),
        expected_head=payload.get("expected_head"),
        paths=_tuple_path(payload.get("paths", [])),
        message=_require_str(payload, "message"),
    )


def _encode_commit_result(result: CommitResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "branch": result.branch,
        "commit_sha": result.commit_sha,
        "committed_files": [_path(path) for path in result.committed_files],
        "message": result.message,
        "parent_head": result.parent_head,
        "repository_root": _path(result.repository_root),
    }


def _decode_commit_result(payload: Any) -> CommitResult | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid commit result")
    return CommitResult(
        repository_root=_decode_path(payload.get("repository_root")),
        branch=payload.get("branch"),
        parent_head=payload.get("parent_head"),
        commit_sha=_require_str(payload, "commit_sha"),
        message=_require_str(payload, "message"),
        committed_files=_tuple_path(payload.get("committed_files", [])),
    )


def _encode_candidate_workflow_metadata(
    metadata: CandidateWorkflowMetadata | None,
) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return {
        "candidate_fingerprint": metadata.candidate_fingerprint,
        "candidate_id": metadata.candidate_id,
        "candidate_plan_fingerprint": metadata.candidate_plan_fingerprint,
        "candidate_plan_id": metadata.candidate_plan_id,
        "candidate_planning_session_id": metadata.candidate_planning_session_id,
        "catalog_item_id": metadata.catalog_item_id,
        "compatibility_assessment_id": metadata.compatibility_assessment_id,
        "compatibility_status": metadata.compatibility_status,
        "conversion_timestamp": _encode_datetime(metadata.conversion_timestamp),
        "core_revalidation_fingerprint": metadata.core_revalidation_fingerprint,
        "core_revalidation_status": metadata.core_revalidation_status,
        "evidence_ids": list(metadata.evidence_ids),
        "execution_category": metadata.execution_category,
        "execution_intent": metadata.execution_intent,
        "relationship_ids": list(metadata.relationship_ids),
        "source_recommendation_id": metadata.source_recommendation_id,
        "source_subsystem": metadata.source_subsystem,
        "target_id": metadata.target_id,
        "target_type": metadata.target_type,
    }


def _decode_candidate_workflow_metadata(
    payload: Any,
) -> CandidateWorkflowMetadata | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate workflow metadata")
    return CandidateWorkflowMetadata(
        candidate_planning_session_id=_require_str(payload, "candidate_planning_session_id"),
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        candidate_plan_id=_require_str(payload, "candidate_plan_id"),
        candidate_plan_fingerprint=_require_str(payload, "candidate_plan_fingerprint"),
        source_recommendation_id=_require_str(payload, "source_recommendation_id"),
        source_subsystem=_require_str(payload, "source_subsystem"),
        catalog_item_id=payload.get("catalog_item_id"),
        target_id=_require_str(payload, "target_id"),
        target_type=_require_str(payload, "target_type"),
        execution_category=_require_str(payload, "execution_category"),
        execution_intent=_require_str(payload, "execution_intent"),
        evidence_ids=_tuple_str(payload.get("evidence_ids", [])),
        compatibility_assessment_id=payload.get("compatibility_assessment_id"),
        compatibility_status=payload.get("compatibility_status"),
        relationship_ids=_tuple_str(payload.get("relationship_ids", [])),
        conversion_timestamp=_decode_datetime(payload.get("conversion_timestamp")),
        core_revalidation_status=_require_str(payload, "core_revalidation_status"),
        core_revalidation_fingerprint=_require_str(payload, "core_revalidation_fingerprint"),
    )


def _encode_candidate_implementation_request(
    request: CandidateImplementationRequest | None,
) -> dict[str, Any] | None:
    if request is None:
        return None
    return {
        "affected_files": [_path(path) for path in request.affected_files],
        "argv": list(request.argv),
        "candidate_fingerprint": request.candidate_fingerprint,
        "candidate_id": request.candidate_id,
        "candidate_plan_fingerprint": request.candidate_plan_fingerprint,
        "candidate_plan_id": request.candidate_plan_id,
        "candidate_planning_session_id": request.candidate_planning_session_id,
        "compatibility_assessment_id": request.compatibility_assessment_id,
        "compatibility_status": request.compatibility_status,
        "evidence_ids": list(request.evidence_ids),
        "execution_intent": request.execution_intent,
        "generated_at": _encode_datetime(request.generated_at),
        "identifier": request.identifier,
        "repository_branch": request.repository_branch,
        "repository_head": request.repository_head,
        "repository_root": _path(request.repository_root),
        "translator_version": request.translator_version,
        "workflow_session_id": request.workflow_session_id,
        "working_directory": _path(request.working_directory),
    }


def _decode_candidate_implementation_request(
    payload: Any,
) -> CandidateImplementationRequest | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate implementation request")
    return CandidateImplementationRequest(
        identifier=_require_str(payload, "identifier"),
        workflow_session_id=_require_str(payload, "workflow_session_id"),
        candidate_planning_session_id=_require_str(payload, "candidate_planning_session_id"),
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        candidate_plan_id=_require_str(payload, "candidate_plan_id"),
        candidate_plan_fingerprint=_require_str(payload, "candidate_plan_fingerprint"),
        execution_intent=_require_str(payload, "execution_intent"),
        repository_root=_decode_path(payload.get("repository_root")),
        repository_branch=payload.get("repository_branch"),
        repository_head=_require_str(payload, "repository_head"),
        argv=_tuple_str(payload.get("argv", [])),
        working_directory=_decode_path(payload.get("working_directory")),
        affected_files=_tuple_path(payload.get("affected_files", [])),
        evidence_ids=_tuple_str(payload.get("evidence_ids", [])),
        compatibility_assessment_id=payload.get("compatibility_assessment_id"),
        compatibility_status=payload.get("compatibility_status"),
        translator_version=_require_str(payload, "translator_version"),
        generated_at=_decode_datetime(payload.get("generated_at")),
    )


def _encode_candidate_verification_plan(plan: CandidateVerificationPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "identifier": plan.identifier,
        "workflow_session_id": plan.workflow_session_id,
        "candidate_planning_session_id": plan.candidate_planning_session_id,
        "candidate_id": plan.candidate_id,
        "candidate_fingerprint": plan.candidate_fingerprint,
        "candidate_plan_id": plan.candidate_plan_id,
        "candidate_plan_fingerprint": plan.candidate_plan_fingerprint,
        "implementation_request_id": plan.implementation_request_id,
        "execution_result_id": plan.execution_result_id,
        "repository_root": _path(plan.repository_root),
        "repository_branch": plan.repository_branch,
        "base_head": plan.base_head,
        "post_execution_head": plan.post_execution_head,
        "changed_files": [_path(path) for path in plan.changed_files],
        "changed_files_digest": plan.changed_files_digest,
        "approved_affected_files": [_path(path) for path in plan.approved_affected_files],
        "verification_checks": [_encode_verification_check(check) for check in plan.verification_checks],
        "verifier_version": plan.verifier_version,
        "generated_at": _encode_datetime(plan.generated_at),
    }


def _decode_candidate_verification_plan(payload: Any) -> CandidateVerificationPlan | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate verification plan")
    return CandidateVerificationPlan(
        identifier=_require_str(payload, "identifier"),
        workflow_session_id=_require_str(payload, "workflow_session_id"),
        candidate_planning_session_id=_require_str(payload, "candidate_planning_session_id"),
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        candidate_plan_id=_require_str(payload, "candidate_plan_id"),
        candidate_plan_fingerprint=_require_str(payload, "candidate_plan_fingerprint"),
        implementation_request_id=_require_str(payload, "implementation_request_id"),
        execution_result_id=_require_str(payload, "execution_result_id"),
        repository_root=_decode_path(payload.get("repository_root")),
        repository_branch=payload.get("repository_branch"),
        base_head=_require_str(payload, "base_head"),
        post_execution_head=_require_str(payload, "post_execution_head"),
        changed_files=_tuple_path(payload.get("changed_files", [])),
        changed_files_digest=_require_str(payload, "changed_files_digest"),
        approved_affected_files=_tuple_path(payload.get("approved_affected_files", [])),
        verification_checks=tuple(_decode_verification_check(item) for item in payload.get("verification_checks", [])),
        verifier_version=_require_str(payload, "verifier_version"),
        generated_at=_decode_datetime(payload.get("generated_at")),
    )


def _encode_candidate_verification_evidence(evidence: CandidateVerificationEvidence | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    return {
        "identifier": evidence.identifier,
        "verification_plan_id": evidence.verification_plan_id,
        "workflow_id": evidence.workflow_id,
        "candidate_id": evidence.candidate_id,
        "candidate_fingerprint": evidence.candidate_fingerprint,
        "plan_fingerprint": evidence.plan_fingerprint,
        "implementation_request_id": evidence.implementation_request_id,
        "changed_files_digest": evidence.changed_files_digest,
        "repository_branch": evidence.repository_branch,
        "repository_head": evidence.repository_head,
        "check_results": [
            {
                "identifier": item.identifier,
                "status": item.status.value,
                "return_code": item.return_code,
                "stdout_digest": item.stdout_digest,
                "stderr_digest": item.stderr_digest,
                "output_truncated": item.output_truncated,
                "duration_seconds": item.duration_seconds,
                "error": item.error,
            }
            for item in evidence.check_results
        ],
        "status": evidence.status.value,
        "started_at": _encode_datetime(evidence.started_at),
        "completed_at": _encode_datetime(evidence.completed_at),
        "verifier_version": evidence.verifier_version,
    }


def _decode_candidate_verification_evidence(payload: Any) -> CandidateVerificationEvidence | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate verification evidence")
    return CandidateVerificationEvidence(
        identifier=_require_str(payload, "identifier"),
        verification_plan_id=_require_str(payload, "verification_plan_id"),
        workflow_id=_require_str(payload, "workflow_id"),
        candidate_id=_require_str(payload, "candidate_id"),
        candidate_fingerprint=_require_str(payload, "candidate_fingerprint"),
        plan_fingerprint=_require_str(payload, "plan_fingerprint"),
        implementation_request_id=_require_str(payload, "implementation_request_id"),
        changed_files_digest=_require_str(payload, "changed_files_digest"),
        repository_branch=payload.get("repository_branch"),
        repository_head=payload.get("repository_head"),
        check_results=tuple(
            CandidateVerificationCheckEvidence(
                identifier=_require_str(item, "identifier"),
                status=VerificationStatus(_require_str(item, "status")),
                return_code=item.get("return_code"),
                stdout_digest=_require_str(item, "stdout_digest"),
                stderr_digest=_require_str(item, "stderr_digest"),
                output_truncated=bool(item.get("output_truncated")),
                duration_seconds=float(item.get("duration_seconds", 0.0)),
                error=item.get("error"),
            )
            for item in payload.get("check_results", [])
        ),
        status=VerificationStatus(_require_str(payload, "status")),
        started_at=_decode_datetime(payload.get("started_at")),
        completed_at=_decode_datetime(payload.get("completed_at")),
        verifier_version=_require_str(payload, "verifier_version"),
    )


def _encode_candidate_review_result(result: CandidateReviewResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "identifier": result.identifier,
        "verification_plan_id": result.verification_plan_id,
        "verification_evidence_id": result.verification_evidence_id,
        "workflow_id": result.workflow_id,
        "status": result.status.value,
        "failure_code": result.failure_code.value if result.failure_code else None,
        "reviewed_content_fingerprint": result.reviewed_content_fingerprint,
        "generated_at": _encode_datetime(result.generated_at),
    }


def _decode_candidate_review_result(payload: Any) -> CandidateReviewResult | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid candidate review result")
    failure_code = payload.get("failure_code")
    return CandidateReviewResult(
        identifier=_require_str(payload, "identifier"),
        verification_plan_id=_require_str(payload, "verification_plan_id"),
        verification_evidence_id=_require_str(payload, "verification_evidence_id"),
        workflow_id=_require_str(payload, "workflow_id"),
        status=ReviewStatus(_require_str(payload, "status")),
        failure_code=CandidateVerificationFailureCode(failure_code) if failure_code else None,
        reviewed_content_fingerprint=payload.get("reviewed_content_fingerprint"),
        generated_at=_decode_datetime(payload.get("generated_at")),
    )


def _encode_workflow_session(session: WorkflowSession) -> dict[str, Any]:
    return {
        "blocked_reason": session.blocked_reason,
        "candidate_implementation_approval_id": session.candidate_implementation_approval_id,
        "candidate_implementation_request": _encode_candidate_implementation_request(
            session.candidate_implementation_request
        ),
        "candidate_metadata": _encode_candidate_workflow_metadata(session.candidate_metadata),
        "candidate_review_result": _encode_candidate_review_result(
            session.candidate_review_result
        ),
        "candidate_verification_evidence": _encode_candidate_verification_evidence(
            session.candidate_verification_evidence
        ),
        "candidate_verification_plan": _encode_candidate_verification_plan(
            session.candidate_verification_plan
        ),
        "changed_files": [_path(path) for path in session.changed_files],
        "commit_request": _encode_commit_request(session.commit_request),
        "commit_result": _encode_commit_result(session.commit_result),
        "context": _encode_context(session.context),
        "execution_result": _encode_execution_result(session.execution_result),
        "worker_patch_applied": session.worker_patch_applied,
        "expected_branch": session.expected_branch,
        "expected_head": session.expected_head,
        "identifier": session.identifier,
        "plan": _encode_plan(session.plan),
        "planning_analysis": _encode_model_response(session.planning_analysis),
        "request": _encode_workflow_request(session.request),
        "review_analysis": _encode_model_response(session.review_analysis),
        "review_report": _encode_review_report(session.review_report),
        "reviewed_content_fingerprint": session.reviewed_content_fingerprint,
        "reviewed_files": [_path(path) for path in session.reviewed_files],
        "source": session.source.value,
        "state": session.state.value,
        "verification_report": _encode_verification_report(session.verification_report),
    }


def _decode_workflow_session(payload: Any) -> WorkflowSession:
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid workflow session")
    return WorkflowSession(
        identifier=_require_str(payload, "identifier"),
        request=_decode_optional_workflow_request(payload.get("request")),
        plan=_decode_optional_plan(payload.get("plan")),
        state=WorkflowSessionState(_require_str(payload, "state")),
        source=WorkflowSource(payload.get("source", WorkflowSource.ROADMAP.value)),
        candidate_metadata=_decode_candidate_workflow_metadata(
            payload.get("candidate_metadata")
        ),
        candidate_implementation_request=_decode_candidate_implementation_request(
            payload.get("candidate_implementation_request")
        ),
        candidate_implementation_approval_id=payload.get(
            "candidate_implementation_approval_id"
        ),
        planning_analysis=_decode_model_response(payload.get("planning_analysis")),
        review_analysis=_decode_model_response(payload.get("review_analysis")),
        context=_decode_context(payload.get("context")),
        execution_result=_decode_execution_result(payload.get("execution_result")),
        worker_patch_applied=bool(payload.get("worker_patch_applied", False)),
        changed_files=_tuple_path(payload.get("changed_files", [])),
        verification_report=_decode_verification_report(payload.get("verification_report")),
        candidate_verification_plan=_decode_candidate_verification_plan(
            payload.get("candidate_verification_plan")
        ),
        candidate_verification_evidence=_decode_candidate_verification_evidence(
            payload.get("candidate_verification_evidence")
        ),
        review_report=_decode_review_report(payload.get("review_report")),
        candidate_review_result=_decode_candidate_review_result(
            payload.get("candidate_review_result")
        ),
        commit_request=_decode_commit_request(payload.get("commit_request")),
        commit_result=_decode_commit_result(payload.get("commit_result")),
        reviewed_files=_tuple_path(payload.get("reviewed_files", [])),
        expected_branch=payload.get("expected_branch"),
        expected_head=payload.get("expected_head"),
        reviewed_content_fingerprint=payload.get("reviewed_content_fingerprint"),
        blocked_reason=payload.get("blocked_reason"),
    )


def _encode_verification_approval_environment(
    variable: VerificationApprovalEnvironment,
) -> dict[str, Any]:
    return {"name": variable.name, "value_digest": variable.value_digest}


def _decode_verification_approval_environment(
    payload: dict[str, Any],
) -> VerificationApprovalEnvironment:
    digest = _require_str(payload, "value_digest")
    _validate_digest(digest)
    return VerificationApprovalEnvironment(
        name=_require_str(payload, "name"),
        value_digest=digest,
    )


def _encode_verification_approval_check(
    check: VerificationApprovalCheck,
) -> dict[str, Any]:
    return {
        "command": list(check.command),
        "environment": [
            _encode_verification_approval_environment(variable)
            for variable in check.environment
        ],
        "identifier": check.identifier,
        "timeout_seconds": check.timeout_seconds,
        "working_directory": _path(check.working_directory),
    }


def _decode_verification_approval_check(payload: dict[str, Any]) -> VerificationApprovalCheck:
    return VerificationApprovalCheck(
        identifier=_require_str(payload, "identifier"),
        command=_tuple_str(payload.get("command", [])),
        working_directory=_decode_path(payload.get("working_directory")),
        timeout_seconds=payload.get("timeout_seconds"),
        environment=tuple(
            _decode_verification_approval_environment(item)
            for item in payload.get("environment", [])
        ),
    )


def _encode_commit_metadata(metadata: CommitApprovalMetadata | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return {
        "commit_message": metadata.commit_message,
        "expected_branch": metadata.expected_branch,
        "expected_head": metadata.expected_head,
        "reviewed_content_fingerprint": metadata.reviewed_content_fingerprint,
        "reviewed_files": [_path(path) for path in metadata.reviewed_files],
    }


def _decode_commit_metadata(payload: Any) -> CommitApprovalMetadata | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid commit metadata")
    fingerprint = _require_str(payload, "reviewed_content_fingerprint")
    _validate_digest(fingerprint)
    return CommitApprovalMetadata(
        expected_branch=payload.get("expected_branch"),
        expected_head=payload.get("expected_head"),
        reviewed_files=_tuple_path(payload.get("reviewed_files", [])),
        reviewed_content_fingerprint=fingerprint,
        commit_message=_require_str(payload, "commit_message"),
    )


def _encode_approval_request(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "checkpoint_id": request.checkpoint_id,
        "commit_metadata": _encode_commit_metadata(request.commit_metadata),
        "identifier": request.identifier,
        "purpose": request.purpose.value,
        "rationale": request.rationale,
        "requested_command": list(request.requested_command),
        "requested_tool": request.requested_tool,
        "requested_working_directory": _path(request.requested_working_directory),
        "title": request.title,
        "verification_checks": [
            _encode_verification_approval_check(check)
            for check in request.verification_checks
        ],
        "workflow_id": request.workflow_id,
    }


def _decode_approval_request(payload: dict[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        identifier=_require_str(payload, "identifier"),
        checkpoint_id=_require_str(payload, "checkpoint_id"),
        title=_require_str(payload, "title"),
        requested_tool=_require_str(payload, "requested_tool"),
        requested_command=_tuple_str(payload.get("requested_command", [])),
        rationale=_require_str(payload, "rationale"),
        workflow_id=payload.get("workflow_id"),
        requested_working_directory=_decode_optional_path(
            payload.get("requested_working_directory")
        ),
        purpose=ApprovalPurpose(_require_str(payload, "purpose")),
        verification_checks=tuple(
            _decode_verification_approval_check(item)
            for item in payload.get("verification_checks", [])
        ),
        commit_metadata=_decode_commit_metadata(payload.get("commit_metadata")),
    )


def _encode_approval_decision(decision: ApprovalDecision) -> dict[str, Any]:
    return {
        "reason": decision.reason,
        "request": _encode_approval_request(decision.request),
        "reviewer": decision.reviewer,
        "status": decision.status.value,
    }


def _decode_approval_decision(payload: dict[str, Any]) -> ApprovalDecision:
    return ApprovalDecision(
        request=_decode_approval_request(_require_dict(payload, "request")),
        status=ApprovalStatus(_require_str(payload, "status")),
        reviewer=payload.get("reviewer"),
        reason=payload.get("reason"),
    )


def _encode_approval_result(result: ApprovalResult) -> dict[str, Any]:
    return {"decision": _encode_approval_decision(result.decision)}


def _decode_approval_result(payload: Any) -> ApprovalResult:
    if not isinstance(payload, dict):
        raise StatePersistenceError("Invalid approval result")
    return ApprovalResult(
        decision=_decode_approval_decision(_require_dict(payload, "decision"))
    )
