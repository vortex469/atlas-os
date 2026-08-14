"""Candidate-planning intake service."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.approval.models import (
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
)
from app.candidate_planning.conversion import (
    build_candidate_workflow_id,
    candidate_plan_fingerprint,
    validate_candidate_plan_safe,
)
from app.candidate_planning.implementation import (
    TRANSLATOR_VERSION,
    CandidateImplementationTranslator,
)
from app.candidate_planning.models import (
    CandidateImplementationTranslationRequest,
    CandidateImplementationTranslationResponse,
    CandidatePlanningContext,
    CandidatePlanningFailureCode,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
    CandidatePlanResponse,
    CandidateSnapshot,
    CandidateWorkflowConversionRequest,
    CandidateWorkflowConversionResponse,
    ComposeMutationSpecification,
    CoreCandidatePlanningIntakeStatus,
    OperationalTargetReference,
    build_candidate_planning_session_id,
    build_candidate_successor_planning_session_id,
    is_operational_planning_intent,
    is_supported_execution_intent,
)
from app.candidate_planning.operational import create_operational_plan
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
    CandidateApprovalRepository,
    CandidatePlanningSessionsState,
    CandidateWorkflowState,
    StatePersistenceError,
)
from app.planning.exceptions import PlanningValidationError
from app.repository.exceptions import RepositoryInspectionError
from app.repository.inspector import GitInspector
from app.workflow.models import (
    CandidateWorkflowMetadata,
    WorkflowEffectKind,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)

logger = logging.getLogger(__name__)


class CandidatePlanningServiceError(RuntimeError):
    """Sanitized candidate-planning service error."""

    def __init__(self, code: CandidatePlanningFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _ConflictingActiveSessionError(RuntimeError):
    """Raised when an active planning session exists for a different fingerprint."""


class CandidatePlanningPredecessorNotFoundError(RuntimeError):
    """Raised when a requested predecessor planning session does not exist."""


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
    mutation = candidate.mutation
    operational_target = candidate.operational_target
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
        effect_kind=WorkflowEffectKind(candidate.effect_kind),
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
        mutation=(
            ComposeMutationSpecification(
                file=Path(mutation.file),
                service=mutation.service,
                property=mutation.property,
                operation=mutation.operation,
                expected_value=mutation.expected_value,
                desired_value=mutation.desired_value,
                preservation_constraints=tuple(sorted(mutation.preservation_constraints)),
            )
            if mutation is not None
            else None
        ),
        operational_target=(
            OperationalTargetReference(
                provider_id=operational_target.provider_id,
                resource_id=operational_target.resource_id,
                resource_type=operational_target.resource_type,
                resource_fingerprint=operational_target.resource_fingerprint,
                resource_version=operational_target.resource_version,
                expected_state=operational_target.expected_state,
            )
            if operational_target is not None
            else None
        ),
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
        operational_plan=session.operational_plan,
        planning_failure=session.planning_failure,
        predecessor_session_id=session.predecessor_session_id,
        successor_session_id=session.successor_session_id,
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


def _create_or_reuse_successor_session(
    state: CandidatePlanningSessionsState,
    *,
    predecessor_session: CandidatePlanningSession,
    session: CandidatePlanningSession,
) -> CandidatePlanningSession:
    if predecessor_session.candidate_id != session.candidate_id:
        raise _ConflictingActiveSessionError

    if predecessor_session.successor_session_id is not None:
        existing_successor = state.get_session(predecessor_session.successor_session_id)
        if existing_successor is not None:
            if (
                existing_successor.predecessor_session_id == predecessor_session.identifier
                and existing_successor.identifier == session.identifier
            ):
                return existing_successor
            raise _ConflictingActiveSessionError

    existing_session = state.get_session(session.identifier)
    if existing_session is not None:
        if existing_session.predecessor_session_id == predecessor_session.identifier:
            return existing_session
        raise _ConflictingActiveSessionError

    if predecessor_session.successor_session_id is None:
        state.replace_session(
            replace(predecessor_session, successor_session_id=session.identifier)
        )
    state.create_session(replace(session, predecessor_session_id=predecessor_session.identifier))
    return replace(session, predecessor_session_id=predecessor_session.identifier)


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


def _conversion_failure(
    *,
    session_id: str,
    candidate_id: str,
    status: CandidatePlanningSessionStatus,
    code: CandidatePlanningFailureCode,
    message: str,
    candidate_fingerprint: str | None = None,
    plan_id: str | None = None,
    plan_fingerprint: str | None = None,
    core_status: CoreCandidatePlanningIntakeStatus | None = None,
) -> CandidateWorkflowConversionResponse:
    from app.candidate_planning.models import CandidatePlanningFailure

    return CandidateWorkflowConversionResponse(
        candidate_planning_session_id=session_id,
        candidate_id=candidate_id,
        candidate_fingerprint=candidate_fingerprint,
        candidate_plan_id=plan_id,
        candidate_plan_fingerprint=plan_fingerprint,
        workflow_session_id=None,
        workflow_status=None,
        implementation_approval_request_id=None,
        conversion_status=status,
        core_revalidation_status=core_status,
        reason_codes=(code.value,),
        failure=CandidatePlanningFailure(code=code, message=message),
    )


def _conversion_failure_from_session(
    session: CandidatePlanningSession,
    status: CandidatePlanningSessionStatus,
    code: CandidatePlanningFailureCode,
    message: str,
    *,
    plan_fingerprint: str | None = None,
    core_status: CoreCandidatePlanningIntakeStatus | None = None,
) -> CandidateWorkflowConversionResponse:
    return _conversion_failure(
        session_id=session.identifier,
        candidate_id=session.candidate_id,
        status=status,
        code=code,
        message=message,
        candidate_fingerprint=session.candidate_fingerprint,
        plan_id=session.plan.identifier if session.plan is not None else None,
        plan_fingerprint=plan_fingerprint,
        core_status=core_status,
    )


def _conversion_response_from_session(
    session: CandidatePlanningSession,
    *,
    status: CandidatePlanningSessionStatus,
    core_status: CoreCandidatePlanningIntakeStatus | None,
) -> CandidateWorkflowConversionResponse:
    return CandidateWorkflowConversionResponse(
        candidate_planning_session_id=session.identifier,
        candidate_id=session.candidate_id,
        candidate_fingerprint=session.candidate_fingerprint,
        candidate_plan_id=session.plan.identifier if session.plan is not None else None,
        candidate_plan_fingerprint=session.candidate_plan_fingerprint,
        workflow_session_id=session.workflow_session_id,
        workflow_status=WorkflowSessionState.AWAITING_APPROVAL.value
        if session.workflow_session_id is not None
        else None,
        implementation_approval_request_id=session.implementation_approval_request_id,
        conversion_status=status,
        core_revalidation_status=core_status,
        reason_codes=(),
    )


def _conversion_code_for_intake(
    status: CoreCandidatePlanningIntakeStatus,
) -> CandidatePlanningFailureCode:
    mapping = {
        CoreCandidatePlanningIntakeStatus.STALE: CandidatePlanningFailureCode.CANDIDATE_STALE,
        CoreCandidatePlanningIntakeStatus.EXPIRED: CandidatePlanningFailureCode.CANDIDATE_EXPIRED,
        CoreCandidatePlanningIntakeStatus.NOT_ELIGIBLE: CandidatePlanningFailureCode.CANDIDATE_NOT_ELIGIBLE,
        CoreCandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE: CandidatePlanningFailureCode.EVIDENCE_UNAVAILABLE,
        CoreCandidatePlanningIntakeStatus.NOT_FOUND: CandidatePlanningFailureCode.SESSION_NOT_FOUND,
    }
    return mapping.get(status, CandidatePlanningFailureCode.WORKFLOW_TRANSLATION_UNSUPPORTED)


def _implementation_failure(
    *,
    session_id: str,
    status: CandidatePlanningSessionStatus,
    code: CandidatePlanningFailureCode,
    message: str,
    workflow_id: str | None = None,
    candidate_fingerprint: str | None = None,
    plan_fingerprint: str | None = None,
    repository_head: str | None = None,
) -> CandidateImplementationTranslationResponse:
    from app.candidate_planning.models import CandidatePlanningFailure

    return CandidateImplementationTranslationResponse(
        candidate_planning_session_id=session_id,
        workflow_session_id=workflow_id,
        translation_status=status,
        implementation_request_id=None,
        exact_approval_request_id=None,
        candidate_fingerprint=candidate_fingerprint,
        plan_fingerprint=plan_fingerprint,
        repository_head=repository_head,
        translator_version=TRANSLATOR_VERSION,
        reason_codes=(code.value,),
        failure=CandidatePlanningFailure(code=code, message=message),
    )


def _implementation_response_from_session(
    session: CandidatePlanningSession,
    *,
    repository_head: str | None,
) -> CandidateImplementationTranslationResponse:
    return CandidateImplementationTranslationResponse(
        candidate_planning_session_id=session.identifier,
        workflow_session_id=session.workflow_session_id,
        translation_status=session.implementation_translation_status
        or CandidatePlanningSessionStatus.IMPLEMENTATION_READY,
        implementation_request_id=session.implementation_request_id,
        exact_approval_request_id=session.exact_implementation_approval_request_id,
        candidate_fingerprint=session.candidate_fingerprint,
        plan_fingerprint=session.candidate_plan_fingerprint,
        repository_head=repository_head,
        translator_version=TRANSLATOR_VERSION,
        reason_codes=(),
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
        implementation_translator: CandidateImplementationTranslator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._core_client = core_client
        self._state_store = state_store
        self._state_persistence = state_persistence
        self._repository_resolver = repository_resolver
        self._repository_inspector_factory = repository_inspector_factory
        self._planner = planner or UpdateComposeStackCandidatePlanner()
        self._implementation_translator = implementation_translator or CandidateImplementationTranslator()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._successor_lock = asyncio.Lock()

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
        if not _is_plannable_snapshot(snapshot):
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

    async def create_successor_planning_session(
        self,
        predecessor_session_id: str,
        request: CandidatePlanRequest,
    ) -> CandidatePlanResponse:
        """Create or reuse one successor while serializing lineage creation."""

        async with self._successor_lock:
            return await self._create_successor_planning_session(
                predecessor_session_id,
                request,
            )

    async def _create_successor_planning_session(
        self,
        predecessor_session_id: str,
        request: CandidatePlanRequest,
    ) -> CandidatePlanResponse:
        """Create a successor planning session for a candidate lineage."""

        predecessor = self._state_store.get_session(predecessor_session_id)
        if predecessor is None:
            raise CandidatePlanningPredecessorNotFoundError(predecessor_session_id)

        request = replace(request, candidate_id=predecessor.candidate_id)

        try:
            intake = await self._core_client.validate_candidate_planning_intake(
                predecessor.candidate_id,
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
        if not _is_plannable_snapshot(snapshot):
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

        successor_repository_head = self._resolve_repository_head(snapshot)

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
            predecessor_session_id=predecessor_session_id,
        )
        if successor_repository_head is not None:
            session = CandidatePlanningSession(
                identifier=build_candidate_successor_planning_session_id(
                    candidate_id=snapshot.candidate_id,
                    candidate_fingerprint=snapshot.candidate_fingerprint,
                    predecessor_session_id=predecessor.identifier,
                    repository_head=successor_repository_head,
                ),
                candidate_id=snapshot.candidate_id,
                candidate_fingerprint=snapshot.candidate_fingerprint,
                status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
                snapshot=snapshot,
                created_at=snapshot.intake_timestamp,
                predecessor_session_id=predecessor.identifier,
            )
        try:
            if self._state_persistence is not None:
                stored_session = self._state_persistence.mutate_candidate_planning(
                    lambda state: _create_or_reuse_successor_session(
                        state,
                        predecessor_session=predecessor,
                        session=session,
                    )
                )
            else:
                stored_session = self._store_create_or_reuse_successor(predecessor, session)
        except _ConflictingActiveSessionError:
            return _conflict_response(snapshot=snapshot)
        except (OSError, ValueError, StatePersistenceError) as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate planning session could not be persisted.",
            ) from error
        return _response_from_session(stored_session)

    def _resolve_repository_head(self, snapshot: CandidateSnapshot) -> str | None:
        if self._repository_resolver is None:
            return None

        repository_root = self._repository_resolver.resolve(
            target_id=snapshot.target_id,
            target_type=snapshot.target_type,
        )
        if repository_root is None:
            return None

        try:
            return self._repository_inspector_factory(repository_root).inspect().head_commit
        except (OSError, RepositoryInspectionError, ValueError):
            return None

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
        if not _is_plannable_snapshot(session.snapshot):
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
            operational_plan=decision.operational_plan,
            planning_failure=decision.failure,
            planning_completed_at=self._clock(),
            last_revalidation_fingerprint=(
                decision.plan.revalidated_candidate_fingerprint
                if decision.plan
                else decision.operational_plan.revalidated_candidate_fingerprint
                if decision.operational_plan
                else None
            ),
            last_revalidation_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING
            if decision.plan or decision.operational_plan
            else started.last_revalidation_status,
        )
        return _response_from_session(self._persist_session_update(completed))

    async def convert_plan_to_workflow_shell(
        self,
        session_id: str,
        request: CandidateWorkflowConversionRequest,
    ) -> CandidateWorkflowConversionResponse:
        """Convert one plan-ready candidate session into an approval-gated workflow shell."""

        session = self._state_store.get_session(session_id)
        if session is None:
            return _conversion_failure(
                session_id=session_id,
                candidate_id=session_id,
                status=CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                code=CandidatePlanningFailureCode.SESSION_NOT_FOUND,
                message="Candidate planning session was not found.",
            )
        if session.workflow_session_id is not None:
            return _conversion_response_from_session(
                session,
                status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
                core_status=session.last_revalidation_status,
            )
        if session.planning_status is not CandidatePlanningSessionStatus.PLAN_READY:
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.PLAN_NOT_READY,
                "Candidate plan is not ready for workflow conversion.",
            )
        if session.plan is None:
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.PLAN_NOT_READY,
                "Candidate planning session has no persisted plan.",
            )
        plan_fingerprint = candidate_plan_fingerprint(session.plan)
        if (
            request.expected_candidate_fingerprint is not None
            and request.expected_candidate_fingerprint != session.candidate_fingerprint
        ):
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.STALE_BEFORE_WORKFLOW,
                CandidatePlanningFailureCode.CANDIDATE_FINGERPRINT_MISMATCH,
                "Candidate fingerprint did not match the persisted session.",
                plan_fingerprint=plan_fingerprint,
            )
        if (
            request.expected_plan_fingerprint is not None
            and request.expected_plan_fingerprint != plan_fingerprint
        ):
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.PLAN_FINGERPRINT_MISMATCH,
                "Candidate plan fingerprint did not match the persisted plan.",
                plan_fingerprint=plan_fingerprint,
            )
        try:
            validate_candidate_plan_safe(session.plan)
        except ValueError:
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.PLAN_INTEGRITY_FAILED,
                "Candidate plan failed workflow-shell safety validation.",
                plan_fingerprint=plan_fingerprint,
            )
        try:
            intake_kwargs = {
                "expected_candidate_fingerprint": session.candidate_fingerprint,
            }
            if session.snapshot.operational_target is not None:
                intake_kwargs["expected_operational_target_fingerprint"] = (
                    session.snapshot.operational_target.resource_fingerprint
                )
            intake = await self._core_client.validate_candidate_planning_intake(
                session.candidate_id, **intake_kwargs
            )
        except AtlasCoreClientError as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE,
                "Atlas Core planning intake is unavailable.",
            ) from error
        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            code = _conversion_code_for_intake(CoreCandidatePlanningIntakeStatus(intake.status))
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.STALE_BEFORE_WORKFLOW,
                code,
                "Atlas Core did not accept candidate workflow revalidation.",
                plan_fingerprint=plan_fingerprint,
                core_status=CoreCandidatePlanningIntakeStatus(intake.status),
            )
        try:
            snapshot = _snapshot_from_intake(intake, intake_timestamp=self._clock())
        except CandidatePlanningServiceError:
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.WORKFLOW_TRANSLATION_UNSUPPORTED,
                "Atlas Core returned an invalid planning-intake response.",
                plan_fingerprint=plan_fingerprint,
            )
        if not _matches_workflow_snapshot(session.snapshot, snapshot):
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.STALE_BEFORE_WORKFLOW,
                CandidatePlanningFailureCode.CANDIDATE_STALE,
                "Candidate changed before workflow conversion.",
                plan_fingerprint=plan_fingerprint,
                core_status=snapshot.intake_status,
            )
        if snapshot.candidate_fingerprint != session.candidate_fingerprint:
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.STALE_BEFORE_WORKFLOW,
                CandidatePlanningFailureCode.CANDIDATE_FINGERPRINT_MISMATCH,
                "Candidate fingerprint changed before workflow conversion.",
                plan_fingerprint=plan_fingerprint,
                core_status=snapshot.intake_status,
            )
        if not is_supported_execution_intent(session.snapshot.execution_intent):
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.UNSUPPORTED_INTENT,
                "Atlas Agent cannot convert this execution intent yet.",
                plan_fingerprint=plan_fingerprint,
                core_status=snapshot.intake_status,
            )
        resolver = self._repository_resolver
        if resolver is None or resolver.resolve(
            target_id=session.snapshot.target_id,
            target_type=session.snapshot.target_type,
        ) is None:
            return _conversion_failure_from_session(
                session,
                CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED,
                CandidatePlanningFailureCode.REPOSITORY_MAPPING_UNAVAILABLE,
                "Candidate target does not map to a trusted Agent repository.",
                plan_fingerprint=plan_fingerprint,
                core_status=snapshot.intake_status,
            )
        return self._persist_workflow_shell(
            session,
            plan_fingerprint=plan_fingerprint,
            revalidated=snapshot,
        )

    def _persist_workflow_shell(
        self,
        session: CandidatePlanningSession,
        *,
        plan_fingerprint: str,
        revalidated: CandidateSnapshot,
    ) -> CandidateWorkflowConversionResponse:
        if self._state_persistence is None:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate workflow shell requires aggregate persistence.",
            )
        assert session.plan is not None
        workflow_id = build_candidate_workflow_id(
            candidate_planning_session_id=session.identifier,
            candidate_fingerprint=session.candidate_fingerprint,
            plan_fingerprint=plan_fingerprint,
        )
        approval_id = f"approval-{workflow_id}"
        converted_at = self._clock()
        metadata = CandidateWorkflowMetadata(
            candidate_planning_session_id=session.identifier,
            candidate_id=session.candidate_id,
            candidate_fingerprint=session.candidate_fingerprint,
            candidate_plan_id=session.plan.identifier,
            candidate_plan_fingerprint=plan_fingerprint,
            source_recommendation_id=session.snapshot.source_recommendation_id,
            source_subsystem=session.snapshot.source_subsystem,
            catalog_item_id=session.snapshot.catalog_item_id,
            target_id=session.snapshot.target_id,
            target_type=session.snapshot.target_type,
            execution_category=session.snapshot.execution_category,
            execution_intent=session.snapshot.execution_intent,
            evidence_ids=session.snapshot.evidence_ids,
            compatibility_assessment_id=session.snapshot.compatibility_assessment_id,
            compatibility_status=session.snapshot.compatibility_status,
            relationship_ids=session.snapshot.relationship_ids,
            conversion_timestamp=converted_at,
            core_revalidation_status=revalidated.intake_status.value,
            core_revalidation_fingerprint=revalidated.candidate_fingerprint,
            effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
        )
        workflow = WorkflowSession(
            identifier=workflow_id,
            request=None,
            plan=None,
            state=WorkflowSessionState.AWAITING_APPROVAL,
            effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
            source=WorkflowSource.CANDIDATE,
            candidate_metadata=metadata,
        )
        approval = ApprovalRequest(
            identifier=approval_id,
            workflow_id=workflow_id,
            checkpoint_id=session.plan.identifier,
            title=f"Approve candidate workflow shell for {session.plan.title}",
            requested_tool="atlas-agent",
            requested_command=(),
            requested_working_directory=session.plan.repository_root,
            rationale=(
                "Approve preparation of future implementation work from the reviewed "
                "candidate plan. No executable command is approved by this request."
            ),
            purpose=ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL,
        )

        def mutate(
            workflow_state: CandidateWorkflowState,
            approvals: CandidateApprovalRepository,
            candidate_planning: CandidatePlanningSessionsState,
        ) -> CandidatePlanningSession:
            current = candidate_planning.get_session(session.identifier)
            if current is None:
                raise ValueError("Candidate planning session disappeared during conversion")
            if current.workflow_session_id is not None:
                return current
            if current.planning_status is not CandidatePlanningSessionStatus.PLAN_READY:
                raise ValueError("Candidate planning session is no longer plan-ready")
            if current.plan is None:
                raise ValueError("Candidate planning session no longer has a plan")
            if candidate_plan_fingerprint(current.plan) != plan_fingerprint:
                raise ValueError("Candidate plan fingerprint changed during conversion")
            workflow_state.create_session(workflow)
            approvals.save_request(approval)
            updated = replace(
                current,
                workflow_session_id=workflow_id,
                implementation_approval_request_id=approval_id,
                candidate_plan_fingerprint=plan_fingerprint,
                workflow_conversion_status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
                workflow_conversion_completed_at=converted_at,
                last_revalidation_fingerprint=revalidated.candidate_fingerprint,
                last_revalidation_status=revalidated.intake_status,
            )
            candidate_planning.replace_session(updated)
            return updated

        try:
            updated_session = self._state_persistence.mutate_aggregate(mutate)
        except (OSError, ValueError, StatePersistenceError) as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate workflow shell could not be persisted.",
            ) from error
        return _conversion_response_from_session(
            updated_session,
            status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
            core_status=revalidated.intake_status,
        )

    async def translate_workflow_shell_to_implementation(
        self,
        session_id: str,
        request: CandidateImplementationTranslationRequest,
    ) -> CandidateImplementationTranslationResponse:
        """Create or return one exact implementation request and approval."""

        session = self._state_store.get_session(session_id)
        if session is None:
            return _implementation_failure(
                session_id=session_id,
                status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                code=CandidatePlanningFailureCode.SESSION_NOT_FOUND,
                message="Candidate planning session was not found.",
            )
        if session.implementation_request_id is not None:
            return _implementation_response_from_session(
                session,
                repository_head=session.plan.repository_head if session.plan else None,
            )
        if session.workflow_session_id is None:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=None,
                status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                code=CandidatePlanningFailureCode.WORKFLOW_NOT_FOUND,
                message="Candidate workflow shell was not found.",
                candidate_fingerprint=session.candidate_fingerprint,
            )
        if session.plan is None or session.planning_status is not CandidatePlanningSessionStatus.PLAN_READY:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                code=CandidatePlanningFailureCode.PLAN_NOT_READY,
                message="Candidate plan is not ready for implementation translation.",
                candidate_fingerprint=session.candidate_fingerprint,
            )
        plan_fingerprint = candidate_plan_fingerprint(session.plan)
        if plan_fingerprint != session.candidate_plan_fingerprint:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=CandidatePlanningFailureCode.PLAN_FINGERPRINT_MISMATCH,
                message="Candidate plan fingerprint changed before implementation translation.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        if (
            request.expected_candidate_fingerprint is not None
            and request.expected_candidate_fingerprint != session.candidate_fingerprint
        ):
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=CandidatePlanningFailureCode.CANDIDATE_FINGERPRINT_MISMATCH,
                message="Candidate fingerprint did not match the persisted session.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        if (
            request.expected_plan_fingerprint is not None
            and request.expected_plan_fingerprint != plan_fingerprint
        ):
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=CandidatePlanningFailureCode.PLAN_FINGERPRINT_MISMATCH,
                message="Candidate plan fingerprint did not match the persisted plan.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        try:
            intake = await self._core_client.validate_candidate_planning_intake(
                session.candidate_id,
                expected_candidate_fingerprint=session.candidate_fingerprint,
            )
        except AtlasCoreClientError as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE,
                "Atlas Core planning intake is unavailable.",
            ) from error
        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=_conversion_code_for_intake(CoreCandidatePlanningIntakeStatus(intake.status)),
                message="Atlas Core did not accept candidate implementation revalidation.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        try:
            snapshot = _snapshot_from_intake(intake, intake_timestamp=self._clock())
        except CandidatePlanningServiceError:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                code=CandidatePlanningFailureCode.WORKFLOW_TRANSLATION_UNSUPPORTED,
                message="Atlas Core returned an invalid planning-intake response.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        if not _matches_workflow_snapshot(session.snapshot, snapshot):
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=CandidatePlanningFailureCode.CANDIDATE_STALE,
                message="Candidate changed before implementation translation.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        if snapshot.candidate_fingerprint != session.candidate_fingerprint:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=CandidatePlanningFailureCode.CANDIDATE_FINGERPRINT_MISMATCH,
                message="Candidate fingerprint changed before implementation translation.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        resolver = self._repository_resolver
        repository_root = resolver.resolve(
            target_id=session.snapshot.target_id,
            target_type=session.snapshot.target_type,
        ) if resolver is not None else None
        if repository_root is None:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.IMPLEMENTATION_NOT_SUPPORTED,
                code=CandidatePlanningFailureCode.REPOSITORY_MAPPING_UNAVAILABLE,
                message="Candidate target does not map to a trusted Agent repository.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
            )
        try:
            repository_snapshot = self._repository_inspector_factory(repository_root).inspect()
        except (OSError, RepositoryInspectionError, ValueError) as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.REPOSITORY_INSPECTION_FAILED,
                "Trusted repository could not be inspected for implementation translation.",
            ) from error
        if request.expected_repository_head is not None and request.expected_repository_head != repository_snapshot.head_commit:
            return _implementation_failure(
                session_id=session.identifier,
                workflow_id=session.workflow_session_id,
                status=CandidatePlanningSessionStatus.STALE_BEFORE_IMPLEMENTATION,
                code=CandidatePlanningFailureCode.REPOSITORY_STALE,
                message="Trusted repository HEAD did not match the expected value.",
                candidate_fingerprint=session.candidate_fingerprint,
                plan_fingerprint=plan_fingerprint,
                repository_head=repository_snapshot.head_commit,
            )
        return self._persist_implementation_translation(
            session,
            repository_snapshot=repository_snapshot,
        )

    def _persist_implementation_translation(
        self,
        session: CandidatePlanningSession,
        *,
        repository_snapshot,
    ) -> CandidateImplementationTranslationResponse:
        if self._state_persistence is None:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate implementation translation requires aggregate persistence.",
            )

        def mutate(
            workflow_state: CandidateWorkflowState,
            approvals: CandidateApprovalRepository,
            candidate_planning: CandidatePlanningSessionsState,
        ) -> CandidateImplementationTranslationResponse:
            current = candidate_planning.get_session(session.identifier)
            if current is None:
                return _implementation_failure(
                    session_id=session.identifier,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                    code=CandidatePlanningFailureCode.SESSION_NOT_FOUND,
                    message="Candidate planning session disappeared during translation.",
                )
            workflow_id = current.workflow_session_id
            if workflow_id is None:
                return _implementation_failure(
                    session_id=current.identifier,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                    code=CandidatePlanningFailureCode.WORKFLOW_NOT_FOUND,
                    message="Candidate workflow shell was not found.",
                    candidate_fingerprint=current.candidate_fingerprint,
                )
            workflow = workflow_state.get_session(workflow_id)
            if workflow is None:
                return _implementation_failure(
                    session_id=current.identifier,
                    workflow_id=workflow_id,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                    code=CandidatePlanningFailureCode.WORKFLOW_NOT_FOUND,
                    message="Candidate workflow shell was not found.",
                    candidate_fingerprint=current.candidate_fingerprint,
                )
            if workflow.source is not WorkflowSource.CANDIDATE:
                return _implementation_failure(
                    session_id=current.identifier,
                    workflow_id=workflow_id,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_NOT_SUPPORTED,
                    code=CandidatePlanningFailureCode.WORKFLOW_NOT_CANDIDATE,
                    message="Workflow is not candidate-derived.",
                    candidate_fingerprint=current.candidate_fingerprint,
                )
            if workflow.candidate_implementation_request is not None:
                return _implementation_response_from_session(
                    current,
                    repository_head=workflow.candidate_implementation_request.repository_head,
                )
            if workflow.state is not WorkflowSessionState.AWAITING_APPROVAL:
                return _implementation_failure(
                    session_id=current.identifier,
                    workflow_id=workflow_id,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                    code=CandidatePlanningFailureCode.WORKFLOW_STATE_INVALID,
                    message="Candidate workflow is not awaiting implementation translation.",
                    candidate_fingerprint=current.candidate_fingerprint,
                )
            decision = self._implementation_translator.translate(
                session=current,
                workflow=workflow,
                repository=repository_snapshot,
                generated_at=self._clock(),
            )
            if decision.request is None:
                assert decision.failure is not None
                return _implementation_failure(
                    session_id=current.identifier,
                    workflow_id=workflow_id,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_NOT_SUPPORTED
                    if decision.failure.code is CandidatePlanningFailureCode.IMPLEMENTATION_NOT_SUPPORTED
                    else CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                    code=decision.failure.code,
                    message=decision.failure.message,
                    candidate_fingerprint=current.candidate_fingerprint,
                    plan_fingerprint=current.candidate_plan_fingerprint,
                    repository_head=repository_snapshot.head_commit,
                )
            exact_approval = ApprovalRequest(
                identifier=f"approval-implementation-{workflow_id}",
                workflow_id=workflow_id,
                checkpoint_id=decision.request.identifier,
                title="Approve exact candidate implementation request",
                requested_tool=decision.request.argv[0],
                requested_command=decision.request.argv,
                requested_working_directory=decision.request.working_directory,
                rationale=(
                    "Approve the exact immutable candidate implementation request. "
                    f"candidate_fingerprint={decision.request.candidate_fingerprint} "
                    f"plan_fingerprint={decision.request.candidate_plan_fingerprint} "
                    f"repository_head={decision.request.repository_head} "
                    f"translator={decision.request.translator_version}."
                ),
                purpose=ApprovalPurpose.IMPLEMENTATION,
            )
            existing_approval = approvals.get_request(exact_approval.identifier)
            if existing_approval is None:
                approvals.save_request(exact_approval)
            elif existing_approval.decision.request == exact_approval:
                # Idempotent: do not mutate if the request already exists and is
                # the same exact approval request.
                pass
            elif existing_approval.decision.status is ApprovalStatus.PENDING:
                if not approvals.supersede_pending_request(
                    identifier=exact_approval.identifier,
                    expected_request=existing_approval.decision.request,
                    replacement_request=exact_approval,
                ):
                    return _implementation_failure(
                        session_id=current.identifier,
                        workflow_id=workflow_id,
                        status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                        code=CandidatePlanningFailureCode.APPROVAL_CREATION_FAILED,
                        message="Exact implementation approval could not replace an existing pending approval request.",
                        candidate_fingerprint=current.candidate_fingerprint,
                        plan_fingerprint=current.candidate_plan_fingerprint,
                        repository_head=repository_snapshot.head_commit,
                    )
            else:
                return _implementation_failure(
                    session_id=current.identifier,
                    workflow_id=workflow_id,
                    status=CandidatePlanningSessionStatus.IMPLEMENTATION_TRANSLATION_FAILED,
                    code=CandidatePlanningFailureCode.APPROVAL_CREATION_FAILED,
                    message="Implementation approval request id is already in use.",
                    candidate_fingerprint=current.candidate_fingerprint,
                    plan_fingerprint=current.candidate_plan_fingerprint,
                    repository_head=repository_snapshot.head_commit,
                )
            updated_workflow = replace(
                workflow,
                state=WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
                candidate_implementation_request=decision.request,
                candidate_implementation_approval_id=exact_approval.identifier,
            )
            workflow_state.sessions[workflow_id] = updated_workflow
            updated_session = replace(
                current,
                implementation_request_id=decision.request.identifier,
                exact_implementation_approval_request_id=exact_approval.identifier,
                implementation_translation_status=CandidatePlanningSessionStatus.IMPLEMENTATION_READY,
                implementation_translation_completed_at=decision.request.generated_at,
            )
            candidate_planning.replace_session(updated_session)
            return _implementation_response_from_session(
                updated_session,
                repository_head=decision.request.repository_head,
            )

        try:
            return self._state_persistence.mutate_aggregate(mutate)
        except (OSError, ValueError, StatePersistenceError) as error:
            raise CandidatePlanningServiceError(
                CandidatePlanningFailureCode.PERSISTENCE_FAILED,
                "Candidate implementation translation could not be persisted.",
            ) from error

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

    def _store_create_or_reuse_successor(
        self,
        predecessor_session: CandidatePlanningSession,
        session: CandidatePlanningSession,
    ) -> CandidatePlanningSession:
        state = CandidatePlanningSessionsState(self._state_store.export_snapshot())
        updated = _create_or_reuse_successor_session(
            state,
            predecessor_session=predecessor_session,
            session=session,
        )
        self._state_store.replace_snapshot(state.snapshot())
        return updated

    async def _plan_started_session(self, session: CandidatePlanningSession):
        try:
            intake_kwargs = {
                "expected_candidate_fingerprint": session.candidate_fingerprint,
            }
            if session.snapshot.operational_target is not None:
                intake_kwargs["expected_operational_target_fingerprint"] = (
                    session.snapshot.operational_target.resource_fingerprint
                )
            intake = await self._core_client.validate_candidate_planning_intake(
                session.candidate_id, **intake_kwargs
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
        if session.snapshot.operational_target is not None:
            try:
                return create_operational_plan(
                    session,
                    created_at=self._clock(),
                    revalidated_candidate_fingerprint=snapshot.candidate_fingerprint,
                )
            except ValueError:
                return unsupported_decision(
                    CandidatePlanningFailureCode.PLANNING_VALIDATION_FAILED,
                    "Operational candidate plan could not be generated.",
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
                    mutation=snapshot.mutation,
                ),
                snapshot=repository_snapshot,
            )
        except ValueError as error:
            mutation = session.snapshot.mutation
            logger.warning(
                "Candidate planner rejected a plan",
                extra={
                    "session_id": session.identifier,
                    "candidate_id": session.candidate_id,
                    "execution_intent": session.snapshot.execution_intent,
                    "recommendation_class": session.snapshot.recommendation_class,
                    "target_id": session.snapshot.target_id,
                    "target_type": session.snapshot.target_type,
                    "mutation_file": str(mutation.file) if mutation is not None else None,
                    "mutation_operation": mutation.operation if mutation is not None else None,
                    "exception_type": type(error).__name__,
                    "exception_message": str(error),
                },
                exc_info=True,
            )
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
            CoreCandidatePlanningIntakeStatus.TARGET_UNAVAILABLE: CandidatePlanningFailureCode.TARGET_UNAVAILABLE,
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
    matches = (
        expected.candidate_id == actual.candidate_id
        and expected.target_id == actual.target_id
        and expected.target_type == actual.target_type
        and expected.execution_intent == actual.execution_intent
    )
    if not matches:
        return False
    if expected.operational_target is not None or actual.operational_target is not None:
        return expected.operational_target == actual.operational_target
    return True


def _is_plannable_snapshot(snapshot: CandidateSnapshot) -> bool:
    if is_supported_execution_intent(snapshot.execution_intent):
        return True
    return (
        snapshot.effect_kind is WorkflowEffectKind.OPERATIONAL_ACTION
        and snapshot.operational_target is not None
        and is_operational_planning_intent(snapshot.execution_intent)
    )


def _matches_workflow_snapshot(
    expected: CandidateSnapshot,
    actual: CandidateSnapshot,
) -> bool:
    return (
        _matches_session_snapshot(expected, actual)
        and expected.required_approval_level == actual.required_approval_level
    )
