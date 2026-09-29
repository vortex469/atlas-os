"""Thread-free ASGI client for the managed Starlette/httpx test stack."""

from __future__ import annotations

import asyncio
from typing import Any, Self

import httpx
from fastapi import FastAPI


class ASGITestClient:
    """Synchronous facade over HTTPX's in-process ASGI transport.

    Starlette's threaded TestClient blocks in the installed test dependency
    stack before dispatching a request.  Keeping this adapter test-local avoids
    changing production behavior while still exercising the real ASGI app.
    """

    __test__ = False

    def __init__(self, app: FastAPI, *, base_url: str = "http://testserver") -> None:
        self.app = app
        self._base_url = base_url
        self.cookies = httpx.Cookies()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self._base_url,
                cookies=self.cookies,
            ) as client:
                response = await client.request(method, url, **kwargs)
                self.cookies.update(client.cookies)
                return response

        return asyncio.run(send())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        container = getattr(getattr(self.app, "state", None), "container", None)
        core_client = getattr(container, "core_client", None)
        if core_client is not None:
            asyncio.run(core_client.close())
