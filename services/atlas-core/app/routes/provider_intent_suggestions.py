"""Authenticated read-only Provider Intent suggestion endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.models.contracts import APIError
from app.models.provider_intent_suggestions import (
    ProviderMonitoringIntentSuggestionV1,
)
from app.operator_auth.dependencies import resolve_operator_session
from app.operator_auth.sessions import ResolvedOperatorSession
from app.provider_intents.suggestions import (
    project_provider_monitoring_intent_suggestions,
)
from app.providers import ProviderNotFoundError
from app.services.provider_management import get_provider_management_descriptor
from app.services.provider_resources import ProviderResourceOperationError

router = APIRouter(prefix="/providers", tags=["Provider Intent Suggestions"])


@router.get(
    "/{provider_id}/management/operator/monitoring-suggestions",
    response_model=tuple[ProviderMonitoringIntentSuggestionV1, ...],
    responses={
        401: {"model": APIError},
        404: {"model": APIError},
        503: {"model": APIError},
    },
)
async def get_provider_monitoring_intent_suggestions(
    _session: Annotated[
        ResolvedOperatorSession, Depends(resolve_operator_session)
    ],
    provider_id: str = Path(min_length=1),
) -> tuple[ProviderMonitoringIntentSuggestionV1, ...]:
    """Derive fresh advisory suggestions without permission or side effects."""

    try:
        descriptor = await get_provider_management_descriptor(provider_id)
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error
    except ProviderResourceOperationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if descriptor.provider_id != provider_id:
        return ()
    return project_provider_monitoring_intent_suggestions(descriptor)
