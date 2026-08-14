from __future__ import annotations

import ipaddress
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.exceptions import request_id_for
from app.operator_auth.models import SUPPORTED_OPERATOR_PERMISSIONS, OperatorPrincipal
from app.operator_auth.sessions import ResolvedOperatorSession

OPERATOR_SESSION_COOKIE = "atlas_operator_session"
OPERATOR_CSRF_HEADER = "X-Atlas-CSRF-Token"


def _reject_audit(
    request: Request,
    *,
    action: str,
    reason: str,
    principal: OperatorPrincipal | None = None,
) -> None:
    audit = getattr(request.app.state, "operator_security_audit", None)
    if audit is None:
        return
    audit.record(
        occurred_at=datetime.now(UTC),
        request_id=request_id_for(request),
        operator_id=principal.operator_id if principal else None,
        auth_method=principal.auth_method if principal else None,
        action=action,
        outcome="rejected",
        reason=reason,
    )


def client_network_key(request: Request) -> str:
    raw = request.client.host if request.client is not None else "unknown"
    try:
        return f"client:{ipaddress.ip_address(raw).compressed}"
    except ValueError:
        return "client:unknown"


def require_allowed_origin(request: Request) -> None:
    if not getattr(request.app.state, "operator_auth_enabled", False):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Operator authentication is disabled.")
    origin = request.headers.get("Origin")
    if not origin or origin == "null":
        _reject_audit(request, action="operator.origin", reason="origin_missing_or_null")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator request origin is not allowed.")
    try:
        parsed = urlsplit(origin)
    except ValueError as error:
        _reject_audit(request, action="operator.origin", reason="origin_malformed")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Operator request origin is not allowed."
        ) from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or origin.rstrip("/") not in request.app.state.operator_auth_trusted_origins
    ):
        _reject_audit(request, action="operator.origin", reason="origin_not_allowed")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator request origin is not allowed.")


def resolve_operator_session(request: Request) -> ResolvedOperatorSession:
    if not getattr(request.app.state, "operator_auth_enabled", False):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Operator authentication is disabled.")
    session = request.app.state.operator_session_store.resolve(
        request.cookies.get(OPERATOR_SESSION_COOKIE)
    )
    if session is None:
        _reject_audit(request, action="operator.session", reason="session_invalid")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Operator authentication is required.")
    request.state.operator_principal = session.principal
    request.state.operator_session = session
    return session


def require_operator_permission(permission: str) -> Callable[[Request], OperatorPrincipal]:
    if permission not in SUPPORTED_OPERATOR_PERMISSIONS:
        raise ValueError("unsupported operator permission")

    def dependency(request: Request) -> OperatorPrincipal:
        session = resolve_operator_session(request)
        if permission not in session.principal.permissions:
            _reject_audit(
                request,
                action=permission,
                reason="permission_missing",
                principal=session.principal,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator permission is required.")
        return session.principal

    return dependency


def require_operator_mutation(permission: str) -> Callable[[Request], OperatorPrincipal]:
    permission_dependency = require_operator_permission(permission)

    def dependency(request: Request) -> OperatorPrincipal:
        require_allowed_origin(request)
        principal = permission_dependency(request)
        session = request.state.operator_session
        if not request.app.state.operator_session_store.verify_csrf(
            session, request.headers.get(OPERATOR_CSRF_HEADER)
        ):
            _reject_audit(
                request,
                action=permission,
                reason="csrf_invalid",
                principal=principal,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator CSRF validation failed.")
        if not request.app.state.operator_mutation_rate_limiter.allow(
            f"operator:{principal.operator_id}"
        ):
            _reject_audit(
                request,
                action=permission,
                reason="rate_limited",
                principal=principal,
            )
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Operator mutation rate limit exceeded.")
        return principal

    return dependency


def require_authenticated_mutation(request: Request) -> OperatorPrincipal:
    require_allowed_origin(request)
    session = resolve_operator_session(request)
    if not request.app.state.operator_session_store.verify_csrf(
        session, request.headers.get(OPERATOR_CSRF_HEADER)
    ):
        _reject_audit(
            request,
            action="operator.logout",
            reason="csrf_invalid",
            principal=session.principal,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator CSRF validation failed.")
    return session.principal
