from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.execution_candidates.api_models import (
    ExecutionCandidatePageResponse,
    ExecutionCandidateResponse,
    candidate_to_response,
)
from app.execution_candidates.models import (
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionIntent,
)
from app.models.contracts import APIError
from app.services.execution_candidates import (
    ExecutionCandidateCollectionError,
    ExecutionCandidateNotFoundError,
    collect_current_execution_candidates,
    filter_candidates,
    get_current_execution_candidate,
    paginate_candidates,
)

router = APIRouter(
    prefix="/execution-candidates",
    tags=["Execution Candidates"],
)

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
    statuses: StatusFilters = None,
    categories: CategoryFilters = None,
    intents: IntentFilters = None,
    source_subsystems: Annotated[list[str] | None, Query(alias="source_subsystem")] = None,
    target_ids: Annotated[list[str] | None, Query(alias="target_id")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExecutionCandidatePageResponse:
    try:
        candidates = await collect_current_execution_candidates()
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
    "/{candidate_id}",
    response_model=ExecutionCandidateResponse,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read a current execution candidate",
)
async def get_execution_candidate(candidate_id: str) -> ExecutionCandidateResponse:
    try:
        candidate = await get_current_execution_candidate(candidate_id)
    except ExecutionCandidateNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Execution candidate is not present in the current projection.",
        ) from error
    except ExecutionCandidateCollectionError as error:
        raise _collection_unavailable(error) from error
    return candidate_to_response(candidate)
