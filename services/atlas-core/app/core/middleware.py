from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger


logger = get_logger("atlas.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (
                perf_counter() - started
            ) * 1000

            logger.exception(
                "%s %s failed after %.2f ms",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (
            perf_counter() - started
        ) * 1000

        logger.info(
            "%s %s %s %.2f ms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
