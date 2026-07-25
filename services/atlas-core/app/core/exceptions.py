from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("atlas.exceptions")


STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_server_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}


def request_id_for(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request_id_for(request)

    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status_code,
        headers=response_headers,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "status": status_code,
                    "details": {} if details is None else details,
                },
                "request_id": request_id,
            }
        ),
    )


async def http_exception_handler(
    request: Request,
    exception: HTTPException,
) -> JSONResponse:
    detail = exception.detail

    if isinstance(detail, str):
        message = detail
        details: Any = {}
    else:
        message = "The request could not be completed."
        details = detail

    return error_response(
        request,
        status_code=exception.status_code,
        code=STATUS_CODES.get(
            exception.status_code,
            "http_error",
        ),
        message=message,
        details=details,
        headers=exception.headers,
    )


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details={
            "errors": exception.errors(),
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled exception for request %s",
        request_id_for(request),
        exc_info=exception,
    )

    return error_response(
        request,
        status_code=500,
        code="internal_server_error",
        message="An unexpected internal error occurred.",
    )
