from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.discovery.api_models import (
    DiscoveryCatalogEntryResponse,
    DiscoveryCatalogPageResponse,
    DiscoveryCompatibilityAssessmentResponse,
    DiscoveryMetadataResponse,
    DiscoveryProposalNavigationResponse,
    DiscoveryProposalPageResponse,
    DiscoveryRelationshipCollectionResponse,
    DiscoverySearchPageResponse,
    compatibility_assessment_to_response,
    entry_to_response,
    relationship_to_response,
    search_result_to_response,
)
from app.discovery.dynamic_projection import DiscoveryMergedItemProjection
from app.discovery.exceptions import DiscoveryCatalogError
from app.discovery.models import (
    CATALOG_SCHEMA_VERSION,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationshipType,
)
from app.discovery.proposals import (
    DiscoveryProposalDestinationKind,
    DiscoveryProposalStatus,
)
from app.models.contracts import APIError
from app.services.discovery import (
    DiscoveryCatalogUnavailableError,
    DiscoveryItemNotFoundError,
    get_discovery_service,
    paginate,
)
from app.services.discovery_compatibility import (
    DiscoveryCompatibilityContextUnavailableError,
    DiscoveryCompatibilityServiceError,
    get_discovery_compatibility_service,
)
from app.services.discovery_dynamic_projection import (
    get_discovery_projection_service,
    get_discovery_request_time,
)
from app.services.discovery_image_grounding import (
    ImageGroundingReadError,
    get_discovery_image_grounding_service,
)
from app.services.discovery_proposals import (
    DiscoveryProposalEvaluation,
    DiscoveryProposalNotFoundError,
    get_discovery_proposal_service,
)

from ..discovery.image_grounding_projection import (
    DiscoveryImageGroundingProjection,
    project_image_grounding,
)

router = APIRouter(prefix="/discovery", tags=["Discovery"])

ItemTypeFilters = Annotated[list[DiscoveryItemType] | None, Query(alias="type")]
StatusFilters = Annotated[list[DiscoveryItemStatus] | None, Query(alias="status")]
RelationshipTypeFilters = Annotated[
    list[DiscoveryRelationshipType] | None,
    Query(alias="relationship_type"),
]


def _tuple(values: list | None) -> tuple:
    return tuple(values or ())


def _catalog_unavailable(error: DiscoveryCatalogUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail="Discovery catalog is unavailable.")


def _item_not_found(error: DiscoveryItemNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


def _validation_error(error: ValidationError | ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail="Discovery query validation failed.")


def _compatibility_unavailable(
    error: DiscoveryCompatibilityContextUnavailableError,
) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Discovery compatibility context is unavailable.",
    )


def _proposal_response(
    evaluation: DiscoveryProposalEvaluation,
) -> DiscoveryProposalNavigationResponse:
    proposal = evaluation.proposal
    destination = DiscoveryProposalDestinationKind.DISCOVERY_DETAIL
    if (
        evaluation.status is DiscoveryProposalStatus.CURRENT
        and evaluation.effective_destination is not None
    ):
        destination = evaluation.effective_destination.kind
    if (
        destination is DiscoveryProposalDestinationKind.OPERATOR_MAINTENANCE_SELECTION
        and not evaluation.actionable_navigation
    ):
        destination = DiscoveryProposalDestinationKind.DISCOVERY_DETAIL
    return DiscoveryProposalNavigationResponse(
        proposal_id=proposal.proposal_id,
        destination_kind=destination,
        catalog_item_id=proposal.provenance.catalog_item_id,
        catalog_source_type=proposal.provenance.catalog_source_type,
        compatibility_status=proposal.compatibility.status,
        finding_reference_count=len(proposal.compatibility.finding_ids),
        evidence_reference_count=len(proposal.compatibility.evidence_ids),
        status=evaluation.status,
        reason=evaluation.reason,
        intent_hint=proposal.intent_hint,
        target_hints=proposal.target_hints,
        generated_at=proposal.generated_at.isoformat(),
        expires_at=proposal.expires_at.isoformat(),
        actionable_navigation=evaluation.actionable_navigation,
    )


@router.get(
    "/proposals",
    response_model=DiscoveryProposalPageResponse,
    responses={503: {"model": APIError}},
    summary="List evaluated advisory Discovery proposals",
)
def list_discovery_proposals(
    target: Annotated[str, Query(min_length=1, max_length=120)] = "atlas",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DiscoveryProposalPageResponse:
    try:
        evaluations = get_discovery_proposal_service().list_evaluations(
            target=target,
            limit=limit,
        )
    except (
        DiscoveryCatalogUnavailableError,
        DiscoveryCompatibilityServiceError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail="Discovery proposals are unavailable.",
        ) from error
    except (ValidationError, ValueError) as error:
        raise _validation_error(error) from error
    return DiscoveryProposalPageResponse(
        proposals=tuple(_proposal_response(value) for value in evaluations),
        total=len(evaluations),
        limit=limit,
    )


@router.get(
    "/proposals/{proposal_id}",
    response_model=DiscoveryProposalNavigationResponse,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read one evaluated advisory Discovery proposal",
)
def get_discovery_proposal(
    proposal_id: str,
    target: Annotated[str, Query(min_length=1, max_length=120)] = "atlas",
) -> DiscoveryProposalNavigationResponse:
    try:
        evaluation = get_discovery_proposal_service().get_evaluation(
            proposal_id,
            target=target,
        )
    except DiscoveryProposalNotFoundError as error:
        raise HTTPException(
            status_code=404, detail="Discovery proposal was not found."
        ) from error
    except (
        DiscoveryCatalogUnavailableError,
        DiscoveryCompatibilityServiceError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail="Discovery proposals are unavailable.",
        ) from error
    return _proposal_response(evaluation)


@router.get(
    "",
    response_model=DiscoveryMetadataResponse,
    responses={503: {"model": APIError}},
    summary="Read Discovery Center status",
)
def discovery_metadata() -> DiscoveryMetadataResponse:
    try:
        catalog_loaded, entry_count = get_discovery_service().metadata()
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error
    return DiscoveryMetadataResponse(
        catalog_loaded=catalog_loaded,
        entry_count=entry_count,
        schema_version=CATALOG_SCHEMA_VERSION,
    )


@router.get(
    "/items",
    response_model=DiscoveryCatalogPageResponse,
    responses={503: {"model": APIError}},
    summary="List Discovery catalog items",
)
def list_discovery_items(
    item_types: ItemTypeFilters = None,
    statuses: StatusFilters = None,
    tags: Annotated[list[str] | None, Query(alias="tag")] = None,
    capabilities: Annotated[list[str] | None, Query(alias="capability")] = None,
    relationship_types: RelationshipTypeFilters = None,
    relationship_targets: Annotated[
        list[str] | None,
        Query(alias="relationship_target"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DiscoveryCatalogPageResponse:
    try:
        entries = get_discovery_service().list_entries(
            item_types=_tuple(item_types),
            statuses=_tuple(statuses),
            tags=_tuple(tags),
            capabilities=_tuple(capabilities),
            relationship_types=_tuple(relationship_types),
            relationship_targets=_tuple(relationship_targets),
        )
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error
    except (ValidationError, ValueError) as error:
        raise _validation_error(error) from error

    page, total, has_more = paginate(entries, limit=limit, offset=offset)
    return DiscoveryCatalogPageResponse(
        entries=tuple(entry_to_response(entry) for entry in page),
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/items/{item_id}",
    response_model=DiscoveryCatalogEntryResponse,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read a Discovery catalog item",
)
def get_discovery_item(item_id: str) -> DiscoveryCatalogEntryResponse:
    try:
        return entry_to_response(get_discovery_service().get_entry(item_id))
    except DiscoveryItemNotFoundError as error:
        raise _item_not_found(error) from error
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error


@router.get(
    "/items/{item_id}/image-grounding",
    response_model=DiscoveryImageGroundingProjection,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read local image grounding for a Discovery catalog item",
)
def get_discovery_item_image_grounding(
    item_id: str,
) -> DiscoveryImageGroundingProjection:
    try:
        read_model = get_discovery_image_grounding_service().get(item_id)
        return project_image_grounding(read_model)
    except ImageGroundingReadError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Discovery item '{item_id}' was not found.",
        ) from error
    except (DiscoveryCatalogError, ValidationError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Image grounding is unavailable.",
        ) from error


@router.get(
    "/items/{item_id}/evidence",
    response_model=DiscoveryMergedItemProjection,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read curated and dynamic Discovery evidence",
)
def get_discovery_item_evidence(item_id: str) -> DiscoveryMergedItemProjection:
    try:
        return get_discovery_projection_service().get_item_projection(
            item_id,
            now=get_discovery_request_time(),
        )
    except DiscoveryItemNotFoundError as error:
        raise _item_not_found(error) from error
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error


@router.get(
    "/items/{item_id}/relationships",
    response_model=DiscoveryRelationshipCollectionResponse,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read direct Discovery item relationships",
)
def get_discovery_item_relationships(
    item_id: str,
    relationship_type: Annotated[
        DiscoveryRelationshipType | None, Query(alias="type")
    ] = None,
) -> DiscoveryRelationshipCollectionResponse:
    try:
        incoming, outgoing = get_discovery_service().relationships(
            item_id,
            relationship_type,
        )
    except DiscoveryItemNotFoundError as error:
        raise _item_not_found(error) from error
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error

    return DiscoveryRelationshipCollectionResponse(
        item_id=item_id,
        incoming=tuple(relationship_to_response(item) for item in incoming),
        outgoing=tuple(relationship_to_response(item) for item in outgoing),
    )


@router.get(
    "/items/{item_id}/compatibility",
    response_model=DiscoveryCompatibilityAssessmentResponse,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read deterministic Discovery item compatibility",
)
def get_discovery_item_compatibility(
    item_id: str,
    target: Annotated[str, Query(min_length=1, max_length=120)] = "atlas",
) -> DiscoveryCompatibilityAssessmentResponse:
    try:
        assessment = get_discovery_compatibility_service().assess_item(
            item_id,
            target=target,
        )
    except DiscoveryItemNotFoundError as error:
        raise _item_not_found(error) from error
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error
    except DiscoveryCompatibilityContextUnavailableError as error:
        raise _compatibility_unavailable(error) from error

    return compatibility_assessment_to_response(assessment)


@router.get(
    "/search",
    response_model=DiscoverySearchPageResponse,
    responses={503: {"model": APIError}},
    summary="Search Discovery catalog items deterministically",
)
def search_discovery_items(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    item_types: ItemTypeFilters = None,
    statuses: StatusFilters = None,
    tags: Annotated[list[str] | None, Query(alias="tag")] = None,
    capabilities: Annotated[list[str] | None, Query(alias="capability")] = None,
    relationship_types: RelationshipTypeFilters = None,
    relationship_targets: Annotated[
        list[str] | None,
        Query(alias="relationship_target"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DiscoverySearchPageResponse:
    try:
        results = get_discovery_service().search(
            text=q,
            item_types=_tuple(item_types),
            statuses=_tuple(statuses),
            tags=_tuple(tags),
            capabilities=_tuple(capabilities),
            relationship_types=_tuple(relationship_types),
            relationship_targets=_tuple(relationship_targets),
        )
    except DiscoveryCatalogUnavailableError as error:
        raise _catalog_unavailable(error) from error
    except (ValidationError, ValueError) as error:
        raise _validation_error(error) from error

    page, total, has_more = paginate(results, limit=limit, offset=offset)
    return DiscoverySearchPageResponse(
        results=tuple(search_result_to_response(result) for result in page),
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )
