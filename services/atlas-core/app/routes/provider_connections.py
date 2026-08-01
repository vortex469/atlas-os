from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Request

from app.models.connections import (
    ProviderConnectionSchema,
    TestProviderConnectionRequest,
    TestProviderConnectionResult,
    UpdateProviderConnectionRequest,
    UpdateProviderConnectionResult,
)
from app.models.contracts import APIError
from app.services.provider_connections import (
    ProviderConnectionConfirmationRequiredError,
    ProviderConnectionNotSupportedError,
    ProviderConnectionOperationError,
    ProviderConnectionProviderNotFoundError,
    ProviderConnectionReadOnlyError,
    ProviderConnectionService,
    ProviderConnectionValidationError,
)

router = APIRouter(prefix="/providers", tags=["provider connections"])


@router.get(
    "/{provider_id}/connection",
    response_model=ProviderConnectionSchema,
    responses={
        404: {"model": APIError},
        501: {"model": APIError},
        503: {"model": APIError},
    },
    summary="Read a provider connection schema",
    description="Returns sanitized provider connection fields. Secret values are never returned.",
)
def get_provider_connection_schema(
    provider_id: str = Path(min_length=1),
) -> ProviderConnectionSchema:
    try:
        return ProviderConnectionService().connection_schema(provider_id)
    except ProviderConnectionProviderNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'.") from error
    except ProviderConnectionNotSupportedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Provider connection schema is unavailable.") from error


@router.post(
    "/{provider_id}/connection/test",
    response_model=TestProviderConnectionResult,
    responses={
        404: {"model": APIError},
        409: {"model": APIError},
        422: {"model": APIError},
        501: {"model": APIError},
        503: {"model": APIError},
    },
    summary="Test provider connection values",
    description=(
        "Tests candidate connection values without persisting them. confirmed=true is "
        "required for live tests and secret-bearing requests. Omitted secret fields keep "
        "existing values. Empty secret replacements are rejected. Docker is read-only."
    ),
)
async def test_provider_connection(
    http_request: Request,
    request: TestProviderConnectionRequest,
    provider_id: str = Path(min_length=1),
) -> TestProviderConnectionResult:
    try:
        return await ProviderConnectionService().test_connection(
            provider_id,
            request,
            request_id=getattr(http_request.state, "request_id", None),
        )
    except ProviderConnectionProviderNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'.") from error
    except ProviderConnectionConfirmationRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProviderConnectionValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderConnectionNotSupportedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except ProviderConnectionOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.put(
    "/{provider_id}/connection",
    response_model=UpdateProviderConnectionResult,
    responses={
        404: {"model": APIError},
        409: {"model": APIError},
        422: {"model": APIError},
        501: {"model": APIError},
        503: {"model": APIError},
    },
    summary="Update provider connection values",
    description=(
        "Persists provider connection values transactionally and rebuilds one provider. "
        "confirmed=true is required. Omitted secret fields keep existing values. Empty "
        "secret replacements are rejected. Docker is read-only."
    ),
)
async def update_provider_connection(
    http_request: Request,
    request: UpdateProviderConnectionRequest,
    provider_id: str = Path(min_length=1),
) -> UpdateProviderConnectionResult:
    try:
        return await ProviderConnectionService().update_connection(
            provider_id,
            request,
            request_id=getattr(http_request.state, "request_id", None),
        )
    except ProviderConnectionProviderNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'.") from error
    except ProviderConnectionConfirmationRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProviderConnectionReadOnlyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProviderConnectionValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderConnectionNotSupportedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
    except ProviderConnectionOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
