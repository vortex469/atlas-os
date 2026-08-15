from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.execution_candidates.api_models import (
    ExecutionCandidatePageResponse,
    ExecutionCandidateResponse,
    OperatorIntentCreationResponse,
    candidate_to_response,
)
from app.execution_candidates.models import (
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionIntent,
)
from app.execution_candidates.operational_capabilities import (
    OperationalCapabilityCollection,
    project_operational_capabilities,
)
from app.execution_candidates.operator_intent_selector import (
    OperatorIntentResourceCollection,
    OperatorIntentResourceCollectionError,
    collect_operator_intent_resources,
    resolve_operational_resource_selector,
)
from app.execution_candidates.operator_intents import (
    OperatorOperationalIntentRequest,
    create_operator_intent,
)
from app.models.contracts import APIError
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import OPERATIONAL_INTENT_CREATE, OperatorPrincipal
from app.providers import ProviderNotFoundError
from app.routes.operator_auth import read_strict_operator_json
from app.services.execution_candidates import (
    ExecutionCandidateCollectionError,
    ExecutionCandidateNotFoundError,
    collect_current_execution_candidates,
    filter_candidates,
    get_current_execution_candidate,
    paginate_candidates,
)
from app.services.provider_resources import (
    OperationalTargetResolutionError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    resolve_operational_target,
)

router = APIRouter(
    prefix="/execution-candidates",
    tags=["Execution Candidates"],
)
_require_intent_creation = require_operator_mutation(OPERATIONAL_INTENT_CREATE)
_require_intent_read = require_operator_permission(OPERATIONAL_INTENT_CREATE)
OperatorIntentPrincipal = Annotated[OperatorPrincipal, Depends(_require_intent_creation)]
OperatorIntentReadPrincipal = Annotated[OperatorPrincipal, Depends(_require_intent_read)]

StatusFilters = Annotated[list[ExecutionCandidateStatus] | None, Query(alias="status")]
CategoryFilters = Annotated[list[ExecutionCategory] | None, Query(alias="category")]
IntentFilters = Annotated[list[ExecutionIntent] | None, Query(alias="intent")]


def _tuple(values: list | None) -> tuple:
    return tuple(values or ())


def _collection_unavailable(error: ExecutionCandidateCollectionError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Execution candidates are unavailable.",
    )


@router.get(
    "",
    response_model=ExecutionCandidatePageResponse,
    responses={503: {"model": APIError}},
    summary="List current execution candidates",
)
async def list_execution_candidates(
    request: Request,
    statuses: StatusFilters = None,
    categories: CategoryFilters = None,
    intents: IntentFilters = None,
    source_subsystems: Annotated[list[str] | None, Query(alias="source_subsystem")] = None,
    target_ids: Annotated[list[str] | None, Query(alias="target_id")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExecutionCandidatePageResponse:
    try:
        store = getattr(request.app.state, "operator_intent_store", None)
        if store is None:
            candidates = await collect_current_execution_candidates()
        else:
            candidates = await collect_current_execution_candidates(
                operator_intent_store=store
            )
    except ExecutionCandidateCollectionError as error:
        raise _collection_unavailable(error) from error

    filtered = filter_candidates(
        candidates,
        statuses=_tuple(statuses),
        categories=_tuple(categories),
        intents=_tuple(intents),
        source_subsystems=_tuple(source_subsystems),
        target_ids=_tuple(target_ids),
    )
    page, total, has_more = paginate_candidates(filtered, limit=limit, offset=offset)
    return ExecutionCandidatePageResponse(
        candidates=tuple(candidate_to_response(candidate) for candidate in page),
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/operator-intents/capabilities",
    response_model=OperationalCapabilityCollection,
    summary="Describe closed operational capabilities",
)
async def list_operator_intent_capabilities(
    principal: OperatorIntentReadPrincipal,
    request: Request,
) -> OperationalCapabilityCollection:
    del principal
    return project_operational_capabilities(
        request.app.state.operational_dispatch_service
    )


@router.get(
    "/operator-intents/capabilities/{selector_id}/resources",
    response_model=OperatorIntentResourceCollection,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="List resources through a fixed operational selector",
)
async def list_capability_resources(
    selector_id: str,
    principal: OperatorIntentReadPrincipal,
) -> OperatorIntentResourceCollection:
    del principal
    selector = resolve_operational_resource_selector(selector_id)
    if selector is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Operational resource selector was not found.",
        )
    try:
        return await selector.collect()
    except OperatorIntentResourceCollectionError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Operator-intent resources are temporarily unavailable.",
        ) from error


@router.get(
    "/operator-intents/resources",
    response_model=OperatorIntentResourceCollection,
    responses={503: {"model": APIError}},
    summary="List sanitized authoritative operator-intent resources",
)
async def list_operator_intent_resources(
    principal: OperatorIntentReadPrincipal,
) -> OperatorIntentResourceCollection:
    del principal
    try:
        return await collect_operator_intent_resources()
    except OperatorIntentResourceCollectionError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Operator-intent resources are temporarily unavailable.",
        ) from error


@router.get(
    "/{candidate_id}",
    response_model=ExecutionCandidateResponse,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read a current execution candidate",
)
async def get_execution_candidate(candidate_id: str, request: Request) -> ExecutionCandidateResponse:
    try:
        store = getattr(request.app.state, "operator_intent_store", None)
        if store is None:
            candidate = await get_current_execution_candidate(candidate_id)
        else:
            candidate = await get_current_execution_candidate(
                candidate_id,
                operator_intent_store=store,
            )
    except ExecutionCandidateNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Execution candidate is not present in the current projection.",
        ) from error
    except ExecutionCandidateCollectionError as error:
        raise _collection_unavailable(error) from error
    return candidate_to_response(candidate)


@router.post(
    "/operator-intents",
    response_model=OperatorIntentCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or reuse an authenticated operator maintenance candidate",
)
async def create_operator_intent_candidate(
    request: Request,
    principal: OperatorIntentPrincipal,
) -> OperatorIntentCreationResponse:
    intent_request = await read_strict_operator_json(
        request, OperatorOperationalIntentRequest
    )
    store = request.app.state.operator_intent_store
    store.append_audit(
        event="intent_requested",
        reason="authenticated_request",
        occurred_at=datetime.now(UTC),
        operator_id=principal.operator_id,
    )
    try:
        result = await create_operator_intent(
            intent_request,
            operator_id=principal.operator_id,
            store=store,
            resolver=resolve_operational_target,
        )
        return OperatorIntentCreationResponse(
            outcome=result.outcome,
            candidate_id=result.candidate_id,
            candidate=candidate_to_response(result.candidate),
        )
    except OperationalTargetResolutionError as error:
        store.append_audit(
            event="intent_rejected",
            reason=type(error).__name__,
            occurred_at=datetime.now(UTC),
            operator_id=principal.operator_id,
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Operator intent target is not currently eligible.",
        ) from error
    except (
        ProviderNotFoundError,
        ProviderResourceOperationError,
        ProviderResourcesNotSupportedError,
    ) as error:
        store.append_audit(
            event="intent_rejected",
            reason=type(error).__name__,
            occurred_at=datetime.now(UTC),
            operator_id=principal.operator_id,
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Operator intent target is temporarily unavailable.",
        ) from error
    except ValueError as error:
        store.append_audit(
            event="intent_rejected",
            reason=type(error).__name__,
            occurred_at=datetime.now(UTC),
            operator_id=principal.operator_id,
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Operator intent target is not currently eligible.",
        ) from error
