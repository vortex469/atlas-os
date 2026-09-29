"""Regression tests for the agent's scoped ASGI test client."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from asgi_test_client import ASGITestClient


def test_lifespan_requests_and_shutdown_share_one_event_loop() -> None:
    events: list[str] = []
    resource: dict[str, object] = {}

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        resource["loop"] = asyncio.get_running_loop()
        resource["active"] = True
        events.append("startup")
        try:
            yield
        finally:
            assert asyncio.get_running_loop() is resource["loop"]
            assert resource["active"] is True
            resource["active"] = False
            events.append("shutdown")

    app = FastAPI(lifespan=lifespan)

    @app.get("/resource")
    async def use_resource() -> dict[str, bool]:
        assert asyncio.get_running_loop() is resource["loop"]
        assert resource["active"] is True
        return {"active": True}

    with ASGITestClient(app) as client:
        assert client.get("/resource").json() == {"active": True}
        assert client.get("/resource").json() == {"active": True}

    assert events == ["startup", "shutdown"]
    assert resource["active"] is False
