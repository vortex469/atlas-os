from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.core.exceptions import request_id_for
from app.operator_auth.dependencies import (
    OPERATOR_CSRF_HEADER,
    OPERATOR_SESSION_COOKIE,
    client_network_key,
    require_allowed_origin,
    require_authenticated_mutation,
    require_operator_mutation,
    resolve_operator_session,
)
from app.operator_auth.models import (
    OPERATIONAL_INTENT_CREATE,
    OperatorLoginRequest,
    OperatorLogoutResponse,
    OperatorPrincipal,
    OperatorProbeRequest,
    OperatorProbeResponse,
    OperatorSessionResponse,
)

MAX_OPERATOR_AUTH_BODY_BYTES = 8_192
router = APIRouter(prefix="/operator-auth", tags=["Operator Authentication"])
_require_probe_permission = require_operator_mutation(OPERATIONAL_INTENT_CREATE)
OperatorProbePrincipal = Annotated[OperatorPrincipal, Depends(_require_probe_permission)]


def _audit(
    request: Request,
    *,
    action: str,
    outcome: str,
    reason: str,
    principal: OperatorPrincipal | None = None,
) -> None:
    request.app.state.operator_security_audit.record(
        occurred_at=datetime.now(UTC),
        request_id=request_id_for(request),
        operator_id=principal.operator_id if principal else None,
        auth_method=principal.auth_method if principal else None,
        action=action,
        outcome=outcome,
        reason=reason,
    )


async def _strict_json(request: Request, model_type):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Operator request must use application/json.")
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) < 0 or int(declared) > MAX_OPERATOR_AUTH_BODY_BYTES:
                raise ValueError
        except ValueError as error:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Operator request is too large.") from error
    body = await request.body()
    if len(body) > MAX_OPERATOR_AUTH_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Operator request is too large.")
    try:
        return model_type.model_validate_json(body)
    except (ValidationError, json.JSONDecodeError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Operator request is invalid.") from error


def _enabled(request: Request) -> None:
    if not request.app.state.operator_auth_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Operator authentication is disabled.")


@router.post("/login", response_model=OperatorSessionResponse)
async def operator_login(request: Request, response: Response) -> OperatorSessionResponse:
    _enabled(request)
    require_allowed_origin(request)
    if not request.app.state.operator_login_rate_limiter.allow(client_network_key(request)):
        _audit(request, action="operator.login", outcome="rejected", reason="rate_limited")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Operator login rate limit exceeded.")
    login = await _strict_json(request, OperatorLoginRequest)
    credential = request.app.state.operator_credential_verifier.authenticate(
        login.operator_id, login.password
    )
    if credential is None:
        _audit(request, action="operator.login", outcome="rejected", reason="authentication_failed")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Operator authentication failed.")
    created = request.app.state.operator_session_store.create(credential)
    response.set_cookie(
        OPERATOR_SESSION_COOKIE,
        created.session_token,
        max_age=request.app.state.operator_session_store.lifetime_seconds,
        expires=created.expires_at,
        path="/api/v1/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.headers[OPERATOR_CSRF_HEADER] = created.csrf_token
    _audit(request, action="operator.login", outcome="accepted", reason="authenticated", principal=created.principal)
    return OperatorSessionResponse(principal=created.principal, expires_at=created.expires_at)


@router.get("/session", response_model=OperatorSessionResponse)
def operator_session(request: Request, response: Response) -> OperatorSessionResponse:
    _enabled(request)
    session = resolve_operator_session(request)
    response.headers[OPERATOR_CSRF_HEADER] = request.app.state.operator_session_store.rotate_csrf(session)
    return OperatorSessionResponse(principal=session.principal, expires_at=session.expires_at)


@router.post("/logout", response_model=OperatorLogoutResponse)
async def operator_logout(request: Request, response: Response) -> OperatorLogoutResponse:
    _enabled(request)
    principal = require_authenticated_mutation(request)
    await _strict_json(request, OperatorProbeRequest)
    session = request.state.operator_session
    request.app.state.operator_session_store.revoke(session)
    response.delete_cookie(OPERATOR_SESSION_COOKIE, path="/api/v1/", secure=True, httponly=True, samesite="strict")
    _audit(request, action="operator.logout", outcome="accepted", reason="revoked", principal=principal)
    return OperatorLogoutResponse()


@router.post("/probe", response_model=OperatorProbeResponse)
async def operator_probe(
    request: Request,
    principal: OperatorProbePrincipal,
) -> OperatorProbeResponse:
    _enabled(request)
    probe = await _strict_json(request, OperatorProbeRequest)
    _audit(
        request,
        action=probe.action,
        outcome="accepted",
        reason="authorized",
        principal=principal,
    )
    return OperatorProbeResponse(
        operator_id=principal.operator_id,
        permission=OPERATIONAL_INTENT_CREATE,
        action=probe.action,
    )
