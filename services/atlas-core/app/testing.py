import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import httpx
from fastapi import FastAPI


class ASGITestClient:
    """Synchronous facade over HTTPX's thread-free ASGI transport."""

    def __init__(self, app: FastAPI) -> None:
        self._app = app

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        async def run_sync_inline(
            function: Callable[..., Any],
            *args: Any,
            **_: Any,
        ) -> Any:
            return function(*args)

        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            with patch(
                "anyio.to_thread.run_sync",
                run_sync_inline,
            ):
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    return await client.request(
                        method,
                        url,
                        **kwargs,
                    )

        return asyncio.run(send())

    def get(
        self,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(
        self,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return self.request("POST", url, **kwargs)
