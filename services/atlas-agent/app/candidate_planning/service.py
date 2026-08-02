"""Candidate-planning intake service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.candidate_planning.models import (
    CandidatePlanningContext,
    CandidatePlanningFailureCode,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
    CandidatePlanResponse,
    CandidateSnapshot,
    CoreCandidatePlanningIntakeStatus,
    build_candidate_planning_session_id,
    is_supported_execution_intent,
)
from app.candidate_planning.planner import (
    RepositoryResolver,
    UpdateComposeStackCandidatePlanner,
    unsupported_decision,
)
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import AtlasCoreClientError
from app.core_client.models import CoreCandidatePlanningIntakeResponse
from app.persistence.snapshot import (
    AgentStatePersistenceCoordinator,
    CandidatePlanningSessionsState,
    StatePersistenceError,
)
from app.planning.exceptions import PlanningValidationError
from app.repository.exceptions import RepositoryInspectionError
from app.repository.inspector import GitInspector


class CandidatePlanningServiceError(RuntimeError):
    """Sanitized candidate-planning service error."""

    def __init__(self, code: CandidatePlanningFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _ConflictingActiveSessionError(RuntimeError):
    """Raised when an active planning session exists for a different fingerprint."""


def _snapshot_from_intake(
    intake: CoreCandidatePlanningIntakeResponse,
    *,
    intake_timestamp: datetime,
) -> CandidateSnapshot:
    if intake.current_candidate is None:
        raise CandidatePlanningServiceError(
            CandidatePlanningFailureCode.MISSING_CANDIDATE_SNAPSHOT,
            "Atlas Core accepted planning intake without a candidate snapshot.",
        )
    if intake.current_candidate_fingerprint is None:
        raise CandidatePlanningServiceError(
            CandidatePlanningFailureCode.MISSING_CANDIDATE_FINGERPRINT,
            "Atlas Core accepted planning intake without a candidate fingerprint.",
        )
    candidate = intake.current_candidate
    return CandidateSnapshot(
        candidate_id=candidate.id,
        candidate_fingerprint=intake.current_candidate_fingerprint,
        source_recommendation_id=candidate.source_recommendation_id,
        source_subsystem=candidate.source_subsystem,
        recommendation_class=candidate.recommendation_class,
        catalog_item_id=candidate.catalog_item_id,
        target_id=candidate.target_id,
        target_type=candidate.target_type,
        execution_category=candidate.execution_category,
        execution_intent=candidate.execution_intent,
        required_approval_level=candidate.required_approval_level,
        rationale=candidate.rationale,
        constraints=tuple(sorted(candidate.constraints)),
        evidence_ids=tuple(sorted(candidate.evidence_ids)),
        compatibility_assessment_id=candidate.compatibility_assessment_id,
        compatibility_status=candidate.compatibility_status,
        relationship_ids=tuple(sorted(candidate.relationship_ids)),
        expires_at=candidate.expires_at,
        intake_status=CoreCandidatePlanningIntakeStatus(intake.status),
        intake_reason_codes=tuple(sorted(intake.reason_codes)),
        intake_timestamp=intake_timestamp,
    )


def _response_from_session(session: CandidatePlanningSession) -> CandidatePlanResponse:
    return CandidatePlanResponse(
        session_id=session.identifier,
        candidate_id=session.candidate_id,
        status=session.planning_status,
        planning_allowed=session.status is CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        intake_status=session.snapshot.intake_status,
        intake_reason_codes=session.snapshot.intake_reason_codes,
        candidate_fingerprint=session.candidate_fingerprint,
        unsupported_reason=session.unsupported_reason,
        plan=session.plan,
        planning_failure=session.planning_failure,
    )


def _conflict_response(*, snapshot: CandidateSnapshot) -> CandidatePlanResponse:
    return CandidatePlanResponse(
        session_id=None,
        candidate_id=snapshot.candidate_id,
        status=CandidatePlanningSessionStatus.INTAKE_REJECTED,
        planning_allowed=False,
        intake_status=snapshot.intake_status,
        intake_reason_codes=(
            CandidatePlanningFailureCode.CONFLICTING_ACTIVE_SESSION.value,
        ),
        candidate_fingerprint=snapshot.candidate_fingerprint,
    )


def _create_or_reuse_session(
    state: CandidatePlanningSessionsState,
    session: CandidatePlanningSession,
) -> CandidatePlanningSession:
    existing = tuple(
        candidate
        for candidate in state.sessions.values()
        if candidate.candidate_id == session.candidate_id
    )
    for candidate in existing:
        if candidate.candidate_fingerprint == session.candidate_fingerprint:
            return candidate
    if existing:
        raise _ConflictingActiveSessionError
    state.create_session(session)
    return session


def _rejection_response(
    *,
    request: CandidatePlanRequest,
    intake: CoreCandidatePlanningIntakeResponse,
) -> CandidatePlanResponse:
    return CandidatePlanResponse(
        session_id=None,
        candidate_id=request.candidate_id,
        status=CandidatePlanningSessionStatus.INTAKE_REJECTED,
        planning_allowed=False,
        intake_status=CoreCandidatePlanningIntakeStatus(intake.status),
        intake_reason_codes=tuple(sorted(intake.reason_codes)),
        candidate_fingerprint=intake.current_candidate_fingerprint,
    )


class CandidatePlanningService:
    """Create planning-only sessions from authoritative Atlas Core intake."""

    def __init__(
        self,
        *,
        core_client: AtlasCoreClient,
        state_store: CandidatePlanningStateStore,
        state_persistence: AgentStatePersistenceCoordinator | None = None,
        repository_resolver: RepositoryResolver | None = None,
        repository_inspector_factory: Callable[[Path], GitInspector] = GitInspector,
        planner: UpdateComposeStackCandidatePlanner | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._core_client = core_client
        self._state_store = state_store
        self._state_persistence = state_persistence
        self._repository_resolver = repository_resolver
        self._repository_inspector_factory = repository_inspector_factory
        self._planner = planner or UpdateComposeStackCandidatePlanner()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_planning_session(
        self,
        request: CandidatePlanRequest,
    ) -> CandidatePlanResponse:
        """Validate Core intake and create or reuse a planning-only session."""

        try:
            intake = await self._core_client.validate_candidate_planning_intake(
                request.candidate_id,
                expected_candidate_fingerprint=request.expected_candidate_fingerprint,
            )
        except AtlasCoreClientError as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE,
                "Atlas Core planning intake is unavailable.",
            ) from error

        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            return _rejection_response(request=request, intake=intake)

        snapshot = _snapshot_from_intake(intake, intake_timestamp=self._clock())
        if not is_supported_execution_intent(snapshot.execution_intent):
            return CandidatePlanResponse(
                session_id=None,
                candidate_id=request.candidate_id,
                status=CandidatePlanningSessionStatus.UNSUPPORTED_INTENT,
                planning_allowed=False,
                intake_status=snapshot.intake_status,
                intake_reason_codes=snapshot.intake_reason_codes,
                candidate_fingerprint=snapshot.candidate_fingerprint,
                unsupported_reason="Atlas Agent cannot plan this execution intent yet.",
            )

        session = CandidatePlanningSession(
            identifier=build_candidate_planning_session_id(
                candidate_id=snapshot.candidate_id,
                candidate_fingerprint=snapshot.candidate_fingerprint,
            ),
            candidate_id=snapshot.candidate_id,
            candidate_fingerprint=snapshot.candidate_fingerprint,
            status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
            snapshot=snapshot,
            created_at=snapshot.intake_timestamp,
        )
        try:
            if self._state_persistence is not None:
                stored_session = self._state_persistence.mutate_candidate_planning(
                    lambda state: _create_or_reuse_session(state, session)
                )
            else:
                stored_session = self._store_create_or_reuse(session)
        except _ConflictingActiveSessionError:
            return _conflict_response(snapshot=snapshot)
        except (OSError, ValueError, StatePersistenceError) as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate planning session could not be persisted.",
            ) from error
        return _response_from_session(stored_session)

    def get_session(self, session_id: str) -> CandidatePlanningSession | None:
        """Return the current candidate-planning session, if present."""

        return self._state_store.get_session(session_id)

    def get_plan(self, session_id: str):
        """Return the current candidate plan, if present."""

        session = self.get_session(session_id)
        return None if session is None else session.plan

    async def generate_plan(self, session_id: str) -> CandidatePlanResponse:
        """Generate or reuse one read-only plan for a candidate-planning session."""

        session = self._state_store.get_session(session_id)
        if session is None:
            return CandidatePlanResponse(
                session_id=None,
                candidate_id=session_id,
                status=CandidatePlanningSessionStatus.PLANNING_FAILED,
                planning_allowed=False,
                intake_status=CoreCandidatePlanningIntakeStatus.NOT_FOUND,
                intake_reason_codes=(CandidatePlanningFailureCode.SESSION_NOT_FOUND.value,),
            )
        if session.planning_status is CandidatePlanningSessionStatus.PLAN_READY:
            return _response_from_session(session)
        if session.planning_status is CandidatePlanningSessionStatus.STALE_BEFORE_PLANNING:
            return _response_from_session(session)
        if session.status is not CandidatePlanningSessionStatus.READY_FOR_PLANNING:
            updated = self._with_failure(
                session,
                CandidatePlanningSessionStatus.PLANNING_FAILED,
                CandidatePlanningFailureCode.INVALID_SESSION_STATUS,
                "Candidate planning session is not ready for planning.",
            )
            return _response_from_session(self._persist_session_update(updated))
        if not is_supported_execution_intent(session.snapshot.execution_intent):
            updated = self._with_failure(
                session,
                CandidatePlanningSessionStatus.PLANNING_NOT_SUPPORTED,
                CandidatePlanningFailureCode.UNSUPPORTED_INTENT,
                "Atlas Agent cannot plan this execution intent yet.",
            )
            return _response_from_session(self._persist_session_update(updated))

        started = self._persist_session_update(
            replace(
                session,
                planning_status=CandidatePlanningSessionStatus.PLANNING,
                planning_started_at=self._clock(),
                planning_failure=None,
            )
        )
        decision = await self._plan_started_session(started)
        completed = replace(
            started,
            planning_status=decision.status,
            plan=decision.plan,
            planning_failure=decision.failure,
            planning_completed_at=self._clock(),
            last_revalidation_fingerprint=(
                decision.plan.revalidated_candidate_fingerprint if decision.plan else None
            ),
            last_revalidation_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING
            if decision.plan
            else started.last_revalidation_status,
        )
        return _response_from_session(self._persist_session_update(completed))

    def _store_create_or_reuse(
        self,
        session: CandidatePlanningSession,
    ) -> CandidatePlanningSession:
        existing = self._state_store.find_active_for_candidate(session.candidate_id)
        for candidate in existing:
            if candidate.candidate_fingerprint == session.candidate_fingerprint:
                return candidate
        if existing:
            raise _ConflictingActiveSessionError
        self._state_store.create_session(session)
        return session

    async def _plan_started_session(self, session: CandidatePlanningSession):
        try:
            intake = await self._core_client.validate_candidate_planning_intake(
                session.candidate_id,
                expected_candidate_fingerprint=session.candidate_fingerprint,
            )
        except AtlasCoreClientError:
            return unsupported_decision(
                CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE,
                "Atlas Core planning intake is unavailable.",
            )
        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            return self._decision_for_rejected_intake(intake)
        try:
            snapshot = _snapshot_from_intake(intake, intake_timestamp=self._clock())
        except CandidatePlanningServiceError:
            return unsupported_decision(
                CandidatePlanningFailureCode.PLANNING_VALIDATION_FAILED,
                "Atlas Core returned an invalid planning-intake response.",
            )
        if not _matches_session_snapshot(session.snapshot, snapshot):
            return unsupported_decision(
                CandidatePlanningFailureCode.CANDIDATE_STALE,
                "Candidate changed before planning.",
            )
        if snapshot.candidate_fingerprint != session.candidate_fingerprint:
            return unsupported_decision(
                CandidatePlanningFailureCode.CANDIDATE_STALE,
                "Candidate fingerprint changed before planning.",
            )
        resolver = self._repository_resolver
        if resolver is None:
            return unsupported_decision(
                CandidatePlanningFailureCode.REPOSITORY_MAPPING_UNAVAILABLE,
                "No trusted repository resolver is configured for candidate planning.",
            )
        repository_root = resolver.resolve(
            target_id=session.snapshot.target_id,
            target_type=session.snapshot.target_type,
        )
        if repository_root is None:
            return unsupported_decision(
                CandidatePlanningFailureCode.REPOSITORY_MAPPING_UNAVAILABLE,
                "Candidate target does not map to a trusted Agent repository.",
            )
        try:
            repository_snapshot = self._repository_inspector_factory(repository_root).inspect()
        except (OSError, RepositoryInspectionError, ValueError):
            return unsupported_decision(
                CandidatePlanningFailureCode.REPOSITORY_INSPECTION_FAILED,
                "Trusted repository could not be inspected for candidate planning.",
            )
        try:
            plan = self._planner.create_plan(
                context=CandidatePlanningContext(
                    session_id=session.identifier,
                    candidate_id=session.candidate_id,
                    candidate_fingerprint=session.candidate_fingerprint,
                    source_recommendation_id=session.snapshot.source_recommendation_id,
                    source_subsystem=session.snapshot.source_subsystem,
                    recommendation_class=session.snapshot.recommendation_class,
                    catalog_item_id=session.snapshot.catalog_item_id,
                    target_id=session.snapshot.target_id,
                    target_type=session.snapshot.target_type,
                    execution_category=session.snapshot.execution_category,
                    execution_intent=session.snapshot.execution_intent,
                    rationale=session.snapshot.rationale,
                    constraints=session.snapshot.constraints,
                    evidence_ids=session.snapshot.evidence_ids,
                    compatibility_assessment_id=session.snapshot.compatibility_assessment_id,
                    compatibility_status=session.snapshot.compatibility_status,
                    relationship_ids=session.snapshot.relationship_ids,
                    repository_root=repository_snapshot.root,
                    repository_branch=repository_snapshot.branch,
                    repository_head=repository_snapshot.head_commit,
                    planning_timestamp=self._clock(),
                    revalidated_candidate_fingerprint=snapshot.candidate_fingerprint,
                ),
                snapshot=repository_snapshot,
            )
        except ValueError:
            return unsupported_decision(
                CandidatePlanningFailureCode.UNSAFE_PLAN_CONTENT,
                "Candidate plan contained unsafe content.",
            )
        except PlanningValidationError:
            return unsupported_decision(
                CandidatePlanningFailureCode.PLANNING_VALIDATION_FAILED,
                "Candidate plan could not be generated.",
            )
        from app.candidate_planning.planner import planning_decision_for_plan

        return planning_decision_for_plan(plan)

    def _decision_for_rejected_intake(self, intake: CoreCandidatePlanningIntakeResponse):
        status = CoreCandidatePlanningIntakeStatus(intake.status)
        mapping = {
            CoreCandidatePlanningIntakeStatus.STALE: CandidatePlanningFailureCode.CANDIDATE_STALE,
            CoreCandidatePlanningIntakeStatus.EXPIRED: CandidatePlanningFailureCode.CANDIDATE_EXPIRED,
            CoreCandidatePlanningIntakeStatus.NOT_ELIGIBLE: CandidatePlanningFailureCode.CANDIDATE_NOT_ELIGIBLE,
            CoreCandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE: CandidatePlanningFailureCode.EVIDENCE_UNAVAILABLE,
            CoreCandidatePlanningIntakeStatus.NOT_FOUND: CandidatePlanningFailureCode.SESSION_NOT_FOUND,
        }
        return unsupported_decision(
            mapping.get(status, CandidatePlanningFailureCode.PLANNING_VALIDATION_FAILED),
            "Atlas Core did not accept candidate planning revalidation.",
        )

    def _with_failure(
        self,
        session: CandidatePlanningSession,
        status: CandidatePlanningSessionStatus,
        code: CandidatePlanningFailureCode,
        message: str,
    ) -> CandidatePlanningSession:
        from app.candidate_planning.models import CandidatePlanningFailure

        return replace(
            session,
            planning_status=status,
            planning_failure=CandidatePlanningFailure(code=code, message=message),
            planning_completed_at=self._clock(),
        )

    def _persist_session_update(
        self,
        session: CandidatePlanningSession,
    ) -> CandidatePlanningSession:
        try:
            if self._state_persistence is not None:
                return self._state_persistence.mutate_candidate_planning(
                    lambda state: _replace_session(state, session)
                )
            self._state_store.replace_session(session)
            return session
        except (OSError, ValueError, StatePersistenceError) as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate planning session could not be persisted.",
            ) from error


def _replace_session(
    state: CandidatePlanningSessionsState,
    session: CandidatePlanningSession,
) -> CandidatePlanningSession:
    state.replace_session(session)
    return session


def _matches_session_snapshot(
    expected: CandidateSnapshot,
    actual: CandidateSnapshot,
) -> bool:
    return (
        expected.candidate_id == actual.candidate_id
        and expected.target_id == actual.target_id
        and expected.target_type == actual.target_type
        and expected.execution_intent == actual.execution_intent
    )
