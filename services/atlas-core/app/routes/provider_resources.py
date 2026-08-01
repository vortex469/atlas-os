from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Request

from app.models.contracts import APIError
from app.models.resources import (
    ProviderResourceCollection,
    UpdateResourceExpectationRequest,
    UpdateResourceExpectationResult,
)
from app.providers import ProviderNotFoundError
from app.services.provider_resources import (
    ProviderResourceConfirmationRequiredError,
    ProviderResourceInvalidExpectationError,
    ProviderResourceOperationError,
    ProviderResourcePolicyWriteError,
    ProviderResourcesNotSupportedError,
    list_provider_resources,
    refresh_provider_resources,
    update_provider_resource_expectation,
)

router = APIRouter(prefix="/providers", tags=["provider resources"])


@router.get(
    "/{provider_id}/resources",
    response_model=ProviderResourceCollection,
    responses={
        404: {"model": APIError},
        501: {"model": APIError},
        503: {"model": APIError},
    },
)
async def get_provider_resources(
    provider_id: str = Path(min_length=1),
) -> ProviderResourceCollection:
    try:
        return await list_provider_resources(provider_id)
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error
    except ProviderResourcesNotSupportedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except ProviderResourceOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post(
    "/{provider_id}/discovery/refresh",
    response_model=ProviderResourceCollection,
    responses={
        404: {"model": APIError},
        501: {"model": APIError},
        503: {"model": APIError},
    },
)
async def refresh_provider_discovery(
    provider_id: str = Path(min_length=1),
) -> ProviderResourceCollection:
    try:
        return await refresh_provider_resources(provider_id)
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error
    except ProviderResourcesNotSupportedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except ProviderResourceOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.put(
    "/{provider_id}/resources/{resource_id}/expectation",
    response_model=UpdateResourceExpectationResult,
    responses={
        404: {"model": APIError},
        409: {"model": APIError},
        422: {"model": APIError},
        501: {"model": APIError},
        503: {"model": APIError},
    },
)
async def update_provider_resource_intent(
    http_request: Request,
    request: UpdateResourceExpectationRequest,
    provider_id: str = Path(min_length=1),
    resource_id: str = Path(min_length=1),
) -> UpdateResourceExpectationResult:
    try:
        return await update_provider_resource_expectation(
            provider_id=provider_id,
            resource_id=resource_id,
            expectation=request.expectation,
            confirmed=request.confirmed,
            request_id=getattr(http_request.state, "request_id", None),
        )
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error
    except ProviderResourceConfirmationRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProviderResourceInvalidExpectationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderResourcesNotSupportedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except ProviderResourcePolicyWriteError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
