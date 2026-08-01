"""Candidate-planning intake service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.candidate_planning.models import (
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
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import AtlasCoreClientError
from app.core_client.models import CoreCandidatePlanningIntakeResponse
from app.persistence.snapshot import (
    AgentStatePersistenceCoordinator,
    CandidatePlanningSessionsState,
    StatePersistenceError,
)


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
        status=session.status,
        planning_allowed=session.status is CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        intake_status=session.snapshot.intake_status,
        intake_reason_codes=session.snapshot.intake_reason_codes,
        candidate_fingerprint=session.candidate_fingerprint,
        unsupported_reason=session.unsupported_reason,
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
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._core_client = core_client
        self._state_store = state_store
        self._state_persistence = state_persistence
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
