"""Authenticated HTTP boundary for live-verified Provider Intent mutation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi import Path as APIPath

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.contracts import APIError
from app.models.provider_intents import (
    ProviderIntentCoordinateMutationResult,
    ProviderIntentMutationRequest,
)
from app.operator_auth.dependencies import require_operator_mutation
from app.operator_auth.models import PROVIDER_INTENT_UPDATE, OperatorPrincipal
from app.provider_intents.mutation import (
    ProviderIntentMutationFailureReason,
    ProviderIntentMutationServiceError,
    mutate_provider_monitoring_intent,
)
from app.provider_intents.target_resolver import (
    ProviderIntentTargetFailureReason,
    ProviderIntentTargetResolutionError,
)
from app.routes.operator_auth import read_strict_operator_json

router = APIRouter(prefix="/providers", tags=["Provider Intent Mutation"])
logger = get_logger("atlas.provider_intent_mutation")
_require_provider_intent_update = require_operator_mutation(PROVIDER_INTENT_UPDATE)
ProviderIntentMutationPrincipal = Annotated[
    OperatorPrincipal,
    Depends(_require_provider_intent_update),
]

_TARGET_STATUS = {
    ProviderIntentTargetFailureReason.PROVIDER_NOT_FOUND: 404,
    ProviderIntentTargetFailureReason.COORDINATE_NOT_FOUND: 404,
    ProviderIntentTargetFailureReason.UNSUPPORTED_PROVIDER: 422,
    ProviderIntentTargetFailureReason.UNSUPPORTED_RESOURCE_TYPE: 422,
    ProviderIntentTargetFailureReason.INVALID_COORDINATE: 422,
    ProviderIntentTargetFailureReason.COORDINATE_AMBIGUOUS: 409,
    ProviderIntentTargetFailureReason.RESOURCE_MISSING: 409,
    ProviderIntentTargetFailureReason.IDENTITY_UNAVAILABLE: 409,
    ProviderIntentTargetFailureReason.FINGERPRINT_MISMATCH: 409,
    ProviderIntentTargetFailureReason.PROVIDER_READ_UNAVAILABLE: 503,
}
_SERVICE_STATUS = {
    ProviderIntentMutationFailureReason.MUTATION_NOT_ACTIVATED: 503,
    ProviderIntentMutationFailureReason.STORE_MIGRATION_REQUIRED: 503,
    ProviderIntentMutationFailureReason.STORE_UNAVAILABLE: 503,
    ProviderIntentMutationFailureReason.CAS_CONFLICT: 409,
    ProviderIntentMutationFailureReason.REQUEST_CONFLICT: 409,
    ProviderIntentMutationFailureReason.INVALID_REQUEST: 422,
}


def _record_security_outcome(
    http_request: Request,
    *,
    principal: OperatorPrincipal,
    request_id: str,
    outcome: str,
    reason: str,
    required: bool,
) -> None:
    try:
        http_request.app.state.operator_security_audit.record(
            occurred_at=datetime.now(UTC),
            request_id=request_id,
            operator_id=principal.operator_id,
            auth_method=principal.auth_method,
            action=PROVIDER_INTENT_UPDATE,
            outcome=outcome,
            reason=reason,
        )
    except Exception as error:
        logger.error(
            "Provider Intent security audit write failed",
            extra={"provider_intent_security_audit_required": required},
        )
        if required:
            raise HTTPException(
                status_code=503,
                detail="security_audit_unavailable",
            ) from error


@router.put(
    "/{provider_id}/management/resources/{resource_type}/{resource_id}/monitoring-intent",
    response_model=ProviderIntentCoordinateMutationResult,
    responses={
        401: {"model": APIError},
        403: {"model": APIError},
        404: {"model": APIError},
        409: {"model": APIError},
        413: {"model": APIError},
        415: {"model": APIError},
        422: {"model": APIError},
        429: {"model": APIError},
        503: {"model": APIError},
    },
)
async def put_provider_monitoring_intent(
    http_request: Request,
    http_response: Response,
    principal: ProviderIntentMutationPrincipal,
    provider_id: str = APIPath(min_length=1, max_length=100),
    resource_type: str = APIPath(min_length=1, max_length=100),
    resource_id: str = APIPath(min_length=1, max_length=200),
) -> ProviderIntentCoordinateMutationResult:
    request = await read_strict_operator_json(
        http_request, ProviderIntentMutationRequest
    )
    try:
        result = await mutate_provider_monitoring_intent(
            operator_id=principal.operator_id,
            provider_id=provider_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request=request,
            activation=settings.provider_intents.activation,
            store_path=Path(settings.provider_intents.database),
        )
    except ProviderIntentTargetResolutionError as error:
        _record_security_outcome(
            http_request,
            principal=principal,
            request_id=request.request_id,
            outcome="rejected",
            reason=error.reason.value,
            required=False,
        )
        raise HTTPException(
            status_code=_TARGET_STATUS[error.reason],
            detail=error.reason.value,
        ) from error
    except ProviderIntentMutationServiceError as error:
        _record_security_outcome(
            http_request,
            principal=principal,
            request_id=request.request_id,
            outcome="rejected",
            reason=error.reason.value,
            required=False,
        )
        raise HTTPException(
            status_code=_SERVICE_STATUS[error.reason],
            detail=error.reason.value,
        ) from error
    _record_security_outcome(
        http_request,
        principal=principal,
        request_id=request.request_id,
        outcome="accepted",
        reason=result.outcome,
        required=True,
    )
    http_response.status_code = 201 if result.outcome == "created" else 200
    return result
