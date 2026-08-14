"""Candidate-planning intake routes."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.candidate_planning.models import (
    CandidateImplementationTranslationRequest,
    CandidateImplementationTranslationResponse,
    CandidatePlan,
    CandidatePlanningFailure,
    CandidatePlanningFailureCode,
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
    CandidatePlanResponse,
    CandidateWorkflowConversionRequest,
    CandidateWorkflowConversionResponse,
    CoreCandidatePlanningIntakeStatus,
    OperationalCandidatePlan,
)
from app.candidate_planning.service import (
    CandidatePlanningPredecessorNotFoundError,
    CandidatePlanningServiceError,
)
from app.workflow.models import WorkflowSession
from app.workflow.state import WorkflowStateStore

router = APIRouter(prefix="/candidate-planning", tags=["candidate-planning"])
logger = logging.getLogger(__name__)


def _candidate_workflows_for_session(
    workflow_state: WorkflowStateStore,
    session_id: str,
) -> tuple[WorkflowSession, ...]:
    """Find candidate workflows linked to a planning-session identifier."""

    _, _, _, sessions = workflow_state.export_snapshot()
    matches = tuple(
        session
        for session in sessions.values()
        if session.candidate_metadata is not None
        and session.candidate_metadata.candidate_planning_session_id == session_id
    )
    return tuple(sorted(matches, key=lambda session: session.identifier))


def _candidate_planning_lookup_conflict_error(
    session_id: str,
    workflows: tuple[WorkflowSession, ...],
) -> HTTPException:
    workflow_ids = tuple(sorted(workflow.identifier for workflow in workflows))
    logger.warning(
        "Duplicate candidate workflow linkage detected for planning session %s: %s",
        session_id,
        ", ".join(workflow_ids),
    )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "candidate_planning_session_conflict",
            "message": "Multiple workflows reference planning session {}: {}".format(
                session_id,
                ", ".join(workflow_ids),
            ),
        },
    )


def _candidate_planning_session_from_workflow(
    workflow_session: WorkflowSession,
) -> CandidatePlanResponse:
    metadata = workflow_session.candidate_metadata
    assert metadata is not None
    try:
        intake_status = CoreCandidatePlanningIntakeStatus(metadata.core_revalidation_status)
    except ValueError:
        logger.warning(
            "Unknown core_revalidation_status %s in metadata for planning session %s",
            metadata.core_revalidation_status,
            metadata.candidate_planning_session_id,
        )
        intake_status = CoreCandidatePlanningIntakeStatus.NOT_FOUND
    return CandidatePlanResponse(
        session_id=metadata.candidate_planning_session_id,
        candidate_id=metadata.candidate_id,
        status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
        planning_allowed=False,
        intake_status=intake_status,
        intake_reason_codes=(),
        candidate_fingerprint=metadata.candidate_fingerprint,
        unsupported_reason=None,
        plan=None,
        planning_failure=None,
    )


def _candidate_workflow_response_from_workflow(
    planning_session_id: str,
    workflow_session: WorkflowSession,
) -> CandidateWorkflowConversionResponse:
    metadata = workflow_session.candidate_metadata
    assert metadata is not None
    try:
        core_status = CoreCandidatePlanningIntakeStatus(metadata.core_revalidation_status)
    except ValueError:
        logger.warning(
            "Unknown core_revalidation_status %s in metadata for planning session %s",
            metadata.core_revalidation_status,
            planning_session_id,
        )
        core_status = None

    return CandidateWorkflowConversionResponse(
        candidate_planning_session_id=metadata.candidate_planning_session_id,
        candidate_id=metadata.candidate_id,
        candidate_fingerprint=metadata.candidate_fingerprint,
        candidate_plan_id=metadata.candidate_plan_id,
        candidate_plan_fingerprint=metadata.candidate_plan_fingerprint,
        workflow_session_id=workflow_session.identifier,
        workflow_status=workflow_session.state.value,
        implementation_approval_request_id=workflow_session.candidate_implementation_approval_id,
        conversion_status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
        core_revalidation_status=core_status,
        reason_codes=(),
        failure=None,
    )


class CandidatePlanningRequest(BaseModel):
    """Validated request for a side-effect-free candidate-planning session."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    expected_candidate_fingerprint: str | None = None

    def to_domain(self) -> CandidatePlanRequest:
        return CandidatePlanRequest(
            candidate_id=self.candidate_id,
            expected_candidate_fingerprint=self.expected_candidate_fingerprint,
        )


class CandidatePlanningSuccessorRequest(BaseModel):
    """Validated request for planning a lineage successor session."""

    model_config = ConfigDict(extra="forbid")

    expected_candidate_fingerprint: str | None = None

    def to_domain(self) -> CandidatePlanRequest:
        return CandidatePlanRequest(
            candidate_id="",
            expected_candidate_fingerprint=self.expected_candidate_fingerprint,
        )


class CandidatePlanningFailureResponse(BaseModel):
    code: str
    message: str


class CandidateWorkflowRequest(BaseModel):
    """Validated request to create a workflow shell from a candidate plan."""

    model_config = ConfigDict(extra="forbid")

    expected_candidate_fingerprint: str | None = None
    expected_plan_fingerprint: str | None = None

    def to_domain(self) -> CandidateWorkflowConversionRequest:
        return CandidateWorkflowConversionRequest(
            expected_candidate_fingerprint=self.expected_candidate_fingerprint,
            expected_plan_fingerprint=self.expected_plan_fingerprint,
        )


class CandidateWorkflowResponse(BaseModel):
    """Serialized workflow-shell conversion response."""

    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str | None
    candidate_plan_id: str | None
    candidate_plan_fingerprint: str | None
    workflow_session_id: str | None
    workflow_status: str | None
    implementation_approval_request_id: str | None
    conversion_status: str
    core_revalidation_status: str | None
    reason_codes: tuple[str, ...]
    failure: CandidatePlanningFailureResponse | None = None


class CandidateImplementationRequest(BaseModel):
    """Validated request to translate a candidate workflow shell."""

    model_config = ConfigDict(extra="forbid")

    expected_candidate_fingerprint: str | None = None
    expected_plan_fingerprint: str | None = None
    expected_repository_head: str | None = None

    def to_domain(self) -> CandidateImplementationTranslationRequest:
        return CandidateImplementationTranslationRequest(
            expected_candidate_fingerprint=self.expected_candidate_fingerprint,
            expected_plan_fingerprint=self.expected_plan_fingerprint,
            expected_repository_head=self.expected_repository_head,
        )


class CandidateImplementationResponse(BaseModel):
    """Serialized candidate implementation translation response."""

    candidate_planning_session_id: str
    workflow_session_id: str | None
    translation_status: str
    implementation_request_id: str | None
    exact_approval_request_id: str | None
    candidate_fingerprint: str | None
    plan_fingerprint: str | None
    repository_head: str | None
    translator_version: str | None
    reason_codes: tuple[str, ...]
    failure: CandidatePlanningFailureResponse | None = None


class CandidatePlanApiResponse(BaseModel):
    identifier: str
    session_id: str
    candidate_id: str
    candidate_fingerprint: str
    title: str
    objective: str
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    proposed_steps: tuple[str, ...]
    likely_affected_components: tuple[str, ...]
    likely_affected_files: tuple[str, ...]
    verification_strategy: tuple[str, ...]
    rollback_considerations: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    created_at: str
    repository_branch: str | None
    repository_head: str | None
    revalidated_candidate_fingerprint: str


class OperationalVerificationApiResponse(BaseModel):
    pre_state: str
    expected_post_state: str
    identity_fingerprint: str
    health_requirement: str
    unknown_outcome_policy: str


class OperationalCandidatePlanApiResponse(BaseModel):
    identifier: str
    session_id: str
    candidate_id: str
    candidate_fingerprint: str
    effect_kind: str
    execution_intent: str
    provider_id: str
    resource_id: str
    resource_type: str
    target_fingerprint: str
    target_version: str | None
    expected_pre_state: str
    intended_action: str
    disruption_scope: str
    verification: OperationalVerificationApiResponse
    failure_considerations: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    created_at: str
    revalidated_candidate_fingerprint: str


class CandidatePlanningResponse(BaseModel):
    """Serialized candidate-planning session response."""

    session_id: str | None
    candidate_id: str
    status: str
    planning_allowed: bool
    intake_status: str
    intake_reason_codes: tuple[str, ...] = ()
    candidate_fingerprint: str | None = None
    unsupported_reason: str | None = None
    plan: CandidatePlanApiResponse | None = None
    operational_plan: OperationalCandidatePlanApiResponse | None = None
    planning_failure: CandidatePlanningFailureResponse | None = None
    predecessor_session_id: str | None = None
    successor_session_id: str | None = None


class CandidatePlanningErrorDetail(BaseModel):
    code: str
    message: str


class CandidatePlanningErrorResponse(BaseModel):
    detail: CandidatePlanningErrorDetail


def _path(value: Path) -> str:
    return str(value)


def _plan_response(plan: CandidatePlan | None) -> CandidatePlanApiResponse | None:
    if plan is None:
        return None
    return CandidatePlanApiResponse(
        identifier=plan.identifier,
        session_id=plan.session_id,
        candidate_id=plan.candidate_id,
        candidate_fingerprint=plan.candidate_fingerprint,
        title=plan.title,
        objective=plan.objective,
        assumptions=plan.assumptions,
        constraints=plan.constraints,
        proposed_steps=plan.proposed_steps,
        likely_affected_components=plan.likely_affected_components,
        likely_affected_files=tuple(_path(path) for path in plan.likely_affected_files),
        verification_strategy=plan.verification_strategy,
        rollback_considerations=plan.rollback_considerations,
        unresolved_questions=plan.unresolved_questions,
        evidence_ids=plan.evidence_ids,
        created_at=plan.created_at.isoformat(),
        repository_branch=plan.repository_branch,
        repository_head=plan.repository_head,
        revalidated_candidate_fingerprint=plan.revalidated_candidate_fingerprint,
    )


def _operational_plan_response(
    plan: OperationalCandidatePlan | None,
) -> OperationalCandidatePlanApiResponse | None:
    if plan is None:
        return None
    return OperationalCandidatePlanApiResponse(
        identifier=plan.identifier,
        session_id=plan.session_id,
        candidate_id=plan.candidate_id,
        candidate_fingerprint=plan.candidate_fingerprint,
        effect_kind=plan.effect_kind.value,
        execution_intent=plan.execution_intent,
        provider_id=plan.provider_id,
        resource_id=plan.resource_id,
        resource_type=plan.resource_type,
        target_fingerprint=plan.target_fingerprint,
        target_version=plan.target_version,
        expected_pre_state=plan.expected_pre_state,
        intended_action=plan.intended_action,
        disruption_scope=plan.disruption_scope,
        verification=OperationalVerificationApiResponse(
            pre_state=plan.verification.pre_state,
            expected_post_state=plan.verification.expected_post_state,
            identity_fingerprint=plan.verification.identity_fingerprint,
            health_requirement=plan.verification.health_requirement,
            unknown_outcome_policy=plan.verification.unknown_outcome_policy,
        ),
        failure_considerations=plan.failure_considerations,
        evidence_ids=plan.evidence_ids,
        created_at=plan.created_at.isoformat(),
        revalidated_candidate_fingerprint=plan.revalidated_candidate_fingerprint,
    )


def _failure_response(
    failure: CandidatePlanningFailure | None,
) -> CandidatePlanningFailureResponse | None:
    if failure is None:
        return None
    return CandidatePlanningFailureResponse(
        code=failure.code.value,
        message=failure.message,
    )


def _to_response(response: CandidatePlanResponse) -> CandidatePlanningResponse:
    return CandidatePlanningResponse(
        session_id=response.session_id,
        candidate_id=response.candidate_id,
        status=response.status.value,
        planning_allowed=response.planning_allowed,
        intake_status=response.intake_status.value,
        intake_reason_codes=response.intake_reason_codes,
        candidate_fingerprint=response.candidate_fingerprint,
        unsupported_reason=response.unsupported_reason,
        plan=_plan_response(response.plan),
        operational_plan=_operational_plan_response(response.operational_plan),
        planning_failure=_failure_response(response.planning_failure),
        predecessor_session_id=response.predecessor_session_id,
        successor_session_id=response.successor_session_id,
    )


def _workflow_response(
    response: CandidateWorkflowConversionResponse,
) -> CandidateWorkflowResponse:
    return CandidateWorkflowResponse(
        candidate_planning_session_id=response.candidate_planning_session_id,
        candidate_id=response.candidate_id,
        candidate_fingerprint=response.candidate_fingerprint,
        candidate_plan_id=response.candidate_plan_id,
        candidate_plan_fingerprint=response.candidate_plan_fingerprint,
        workflow_session_id=response.workflow_session_id,
        workflow_status=response.workflow_status,
        implementation_approval_request_id=response.implementation_approval_request_id,
        conversion_status=response.conversion_status.value,
        core_revalidation_status=response.core_revalidation_status.value
        if response.core_revalidation_status is not None
        else None,
        reason_codes=response.reason_codes,
        failure=_failure_response(response.failure),
    )


def _implementation_response(
    response: CandidateImplementationTranslationResponse,
) -> CandidateImplementationResponse:
    return CandidateImplementationResponse(
        candidate_planning_session_id=response.candidate_planning_session_id,
        workflow_session_id=response.workflow_session_id,
        translation_status=response.translation_status.value,
        implementation_request_id=response.implementation_request_id,
        exact_approval_request_id=response.exact_approval_request_id,
        candidate_fingerprint=response.candidate_fingerprint,
        plan_fingerprint=response.plan_fingerprint,
        repository_head=response.repository_head,
        translator_version=response.translator_version,
        reason_codes=response.reason_codes,
        failure=_failure_response(response.failure),
    )


@router.post(
    "",
    response_model=CandidatePlanningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse}},
)
async def create_candidate_planning_session(
    request: Request,
    planning_request: CandidatePlanningRequest,
) -> CandidatePlanningResponse:
    """Create or reuse a planning-only session from an authoritative Core candidate."""

    try:
        response = await request.app.state.container.candidate_planning_service.create_planning_session(
            planning_request.to_domain()
        )
    except CandidatePlanningServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc
    return _to_response(response)


@router.get("/{session_id}", response_model=CandidatePlanningResponse)
async def get_candidate_planning_session(
    request: Request,
    session_id: str,
) -> CandidatePlanningResponse:
    """Return a current candidate-planning session without side effects."""

    session = request.app.state.container.candidate_planning_service.get_session(session_id)
    if session is None:
        workflows = _candidate_workflows_for_session(
            request.app.state.container.workflow_state,
            session_id,
        )
        if len(workflows) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if len(workflows) > 1:
            raise _candidate_planning_lookup_conflict_error(session_id, workflows)

        workflow_session = workflows[0]
        logger.warning(
            "Recovered orphaned planning session %s from candidate workflow %s",
            session_id,
            workflow_session.identifier,
        )
        return _to_response(_candidate_planning_session_from_workflow(workflow_session))
    return _to_response(
        CandidatePlanResponse(
            session_id=session.identifier,
            candidate_id=session.candidate_id,
            status=session.planning_status,
            planning_allowed=session.status.value == "ready_for_planning",
            intake_status=session.snapshot.intake_status,
            intake_reason_codes=session.snapshot.intake_reason_codes,
            candidate_fingerprint=session.candidate_fingerprint,
            unsupported_reason=session.unsupported_reason,
            plan=session.plan,
            planning_failure=session.planning_failure,
        )
    )


@router.post(
    "/{session_id}/plan",
    response_model=CandidatePlanningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse}},
)
async def generate_candidate_plan(
    request: Request,
    session_id: str,
) -> CandidatePlanningResponse:
    """Generate or return one deterministic read-only plan for a candidate session."""

    try:
        response = await request.app.state.container.candidate_planning_service.generate_plan(
            session_id
        )
    except CandidatePlanningServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc
    if response.session_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _to_response(response)


@router.get("/{session_id}/plan", response_model=CandidatePlanApiResponse)
async def get_candidate_plan(
    request: Request,
    session_id: str,
) -> CandidatePlanApiResponse:
    """Return an existing candidate plan without generating a new one."""

    plan = request.app.state.container.candidate_planning_service.get_plan(session_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return _plan_response(plan)


@router.post(
    "/{session_id}/workflow",
    response_model=CandidateWorkflowResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": CandidatePlanningErrorResponse},
        status.HTTP_409_CONFLICT: {"model": CandidatePlanningErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse},
    },
)
async def create_candidate_workflow_shell(
    request: Request,
    session_id: str,
    conversion_request: CandidateWorkflowRequest | None = None,
) -> CandidateWorkflowResponse:
    """Create or return an approval-gated workflow shell without executable commands."""

    try:
        response = await request.app.state.container.candidate_planning_service.convert_plan_to_workflow_shell(
            session_id,
            (conversion_request or CandidateWorkflowRequest()).to_domain(),
        )
    except CandidatePlanningServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc

    if (
        response.failure is not None
        and response.failure.code == CandidatePlanningFailureCode.SESSION_NOT_FOUND
        and response.conversion_status
        is CandidatePlanningSessionStatus.WORKFLOW_CONVERSION_FAILED
    ):
        workflows = _candidate_workflows_for_session(
            request.app.state.container.workflow_state,
            session_id,
        )
        if len(workflows) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if len(workflows) > 1:
            raise _candidate_planning_lookup_conflict_error(session_id, workflows)

        workflow_session = workflows[0]
        logger.warning(
            "Recovered orphaned planning session %s from candidate workflow %s",
            session_id,
            workflow_session.identifier,
        )
        return _workflow_response(
            _candidate_workflow_response_from_workflow(session_id, workflow_session),
        )

    return _workflow_response(response)


@router.post(
    "/{session_id}/implementation",
    response_model=CandidateImplementationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse}},
)
async def translate_candidate_implementation(
    request: Request,
    session_id: str,
    implementation_request: CandidateImplementationRequest | None = None,
) -> CandidateImplementationResponse:
    """Create or return one exact candidate implementation request for approval."""

    try:
        response = await request.app.state.container.candidate_planning_service.translate_workflow_shell_to_implementation(
            session_id,
            (implementation_request or CandidateImplementationRequest()).to_domain(),
        )
    except CandidatePlanningServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc
    return _implementation_response(response)


@router.post(
    "/{session_id}/successor",
    response_model=CandidatePlanningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": CandidatePlanningErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse},
    },
)
async def create_planning_successor(
    request: Request,
    session_id: str,
    successor_request: CandidatePlanningSuccessorRequest | None = None,
) -> CandidatePlanningResponse:
    """Create a direct successor planning session for an existing session lineage."""

    try:
        response = await request.app.state.container.candidate_planning_service.create_successor_planning_session(
            session_id,
            (successor_request or CandidatePlanningSuccessorRequest()).to_domain(),
        )
    except CandidatePlanningPredecessorNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "session_not_found", "message": "Predecessor session not found."},
        ) from error
    except CandidatePlanningServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": error.code.value, "message": error.message},
        ) from error
    return _to_response(response)
