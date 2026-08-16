"""Public and authenticated read-only provider-management descriptors."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.models.contracts import APIError
from app.models.provider_management import (
    ProviderManagementDescriptor,
    ProviderManagementDescriptorV3,
)
from app.operator_auth.dependencies import resolve_operator_session
from app.operator_auth.models import PROVIDER_INTENT_UPDATE
from app.operator_auth.sessions import ResolvedOperatorSession
from app.providers import ProviderNotFoundError
from app.services.provider_management import (
    get_authenticated_provider_management_descriptor,
    get_provider_management_descriptor,
)
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


@router.get(
    "/{provider_id}/management/operator",
    response_model=ProviderManagementDescriptorV3,
    responses={
        401: {"model": APIError},
        404: {"model": APIError},
        503: {"model": APIError},
    },
)
async def get_authenticated_provider_management(
    session: Annotated[ResolvedOperatorSession, Depends(resolve_operator_session)],
    provider_id: str = Path(min_length=1),
) -> ProviderManagementDescriptorV3:
    try:
        return await get_authenticated_provider_management_descriptor(
            provider_id,
            caller_has_provider_intent_update=(
                PROVIDER_INTENT_UPDATE in session.principal.permissions
            ),
        )
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error
    except ProviderResourceOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
