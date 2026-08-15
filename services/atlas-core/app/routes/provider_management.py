"""Read-only public provider-management descriptor route."""

from fastapi import APIRouter, HTTPException, Path

from app.models.contracts import APIError
from app.models.provider_management import ProviderManagementDescriptor
from app.providers import ProviderNotFoundError
from app.services.provider_management import get_provider_management_descriptor
from app.services.provider_resources import ProviderResourceOperationError

router = APIRouter(prefix="/providers", tags=["provider management"])


@router.get(
    "/{provider_id}/management",
    response_model=ProviderManagementDescriptor,
    responses={
        404: {"model": APIError},
        503: {"model": APIError},
    },
)
async def get_provider_management(
    provider_id: str = Path(min_length=1),
) -> ProviderManagementDescriptor:
    try:
        return await get_provider_management_descriptor(provider_id)
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error
    except ProviderResourceOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
