from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("atlas.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = (
            request.headers.get("X-Request-ID")
            or uuid4().hex
        )
        request.state.request_id = request_id

        started = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (
                perf_counter() - started
            ) * 1000

            logger.exception(
                "%s %s failed after %.2f ms request_id=%s",
                request.method,
                request.url.path,
                elapsed_ms,
                request_id,
            )
            raise

        elapsed_ms = (
            perf_counter() - started
        ) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s %s %.2f ms request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response
