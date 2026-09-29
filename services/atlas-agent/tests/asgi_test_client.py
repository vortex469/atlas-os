"""Thread-free ASGI client for the managed Starlette/httpx test stack."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable
from contextlib import suppress
from typing import Any, Self

import httpx
from fastapi import FastAPI


class ASGITestClient:
    """Synchronous client whose scoped lifecycle shares one event loop."""

    __test__ = False

    def __init__(self, app: FastAPI, *, base_url: str = "http://testserver") -> None:
        self.app = app
        self._base_url = base_url
        self.cookies = httpx.Cookies()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: httpx.AsyncClient | None = None
        self._lifespan_task: asyncio.Task[None] | None = None
        self._lifespan_receive: asyncio.Queue[dict[str, Any]] | None = None
        self._lifespan_send: asyncio.Queue[dict[str, Any]] | None = None
        self._entered = False
        self._request_lock = threading.RLock()

    def _run(self, operation: Awaitable[Any]) -> Any:
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("ASGI test client is not active")
        return self._loop.run_until_complete(operation)

    async def _receive_lifespan_message(self) -> dict[str, Any]:
        assert self._lifespan_receive is not None
        return await self._lifespan_receive.get()

    async def _send_lifespan_message(self, message: dict[str, Any]) -> None:
        assert self._lifespan_send is not None
        await self._lifespan_send.put(message)

    async def _run_lifespan(self) -> None:
        await self.app(
            {
                "type": "lifespan",
                "asgi": {"version": "3.0", "spec_version": "2.0"},
            },
            self._receive_lifespan_message,
            self._send_lifespan_message,
        )

    async def _wait_for_lifespan(self, event: str) -> None:
        assert self._lifespan_send is not None
        message = await self._lifespan_send.get()
        if message["type"] == f"lifespan.{event}.failed":
            raise RuntimeError(message.get("message", f"lifespan {event} failed"))
        if message["type"] != f"lifespan.{event}.complete":
            raise RuntimeError(f"unexpected lifespan message: {message['type']}")

    async def _startup(self) -> None:
        self._lifespan_receive = asyncio.Queue()
        self._lifespan_send = asyncio.Queue()
        self._lifespan_task = asyncio.create_task(self._run_lifespan())
        await self._lifespan_receive.put({"type": "lifespan.startup"})
        await self._wait_for_lifespan("startup")
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url=self._base_url,
            cookies=self.cookies,
        )

    async def _shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._lifespan_task is not None:
            assert self._lifespan_receive is not None
            await self._lifespan_receive.put({"type": "lifespan.shutdown"})
            await self._wait_for_lifespan("shutdown")
            await self._lifespan_task
            self._lifespan_task = None

    async def _cancel_lifespan_task(self) -> None:
        if self._lifespan_task is not None and not self._lifespan_task.done():
            self._lifespan_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._lifespan_task
        self._lifespan_task = None

    async def _send_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        client = self._client
        if client is None:
            raise RuntimeError("ASGI test client must be used as a context manager")
        response = await client.request(method, url, **kwargs)
        self.cookies.update(client.cookies)
        return response

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if not self._entered:
            with self._request_lock:
                client = ASGITestClient(self.app, base_url=self._base_url)
                client.cookies.update(self.cookies)
            with client:
                response = client.request(method, url, **kwargs)
            with self._request_lock:
                self.cookies.update(client.cookies)
            return response
        with self._request_lock:
            return self._run(self._send_request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def __enter__(self) -> Self:
        if self._entered:
            raise RuntimeError("ASGI test client is already active")
        self._loop = asyncio.new_event_loop()
        self._entered = True
        try:
            self._run(self._startup())
        except BaseException:
            self._run(self._cancel_lifespan_task())
            self._entered = False
            self._loop.close()
            self._loop = None
            raise
        return self

    def __exit__(self, *_: object) -> None:
        try:
            self._run(self._shutdown())
        finally:
            if self._lifespan_task is not None:
                self._run(self._cancel_lifespan_task())
            self._entered = False
            assert self._loop is not None
            self._loop.close()
            self._loop = None
