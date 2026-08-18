from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread

import httpx
import pytest

from app.discovery.dynamic_projection import (
    MERGED_ITEM_SCHEMA,
    DynamicCacheState,
    DynamicDiscoveryCacheReader,
    DynamicDiscoveryProjectionService,
    DynamicSourceReadSnapshot,
)
from app.discovery.dynamic_sources import FRIGATE_ADAPTER_ID
from app.discovery.test_dynamic_projection import (
    FakeReader,
    catalog,
    entry,
    initialized,
    p1_record,
)
from app.main import app
from app.routes import discovery as route_module
from app.services import discovery_dynamic_projection as dependency_module
from app.services.discovery import DiscoveryItemNotFoundError
from app.testing import ASGITestClient

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
PATH = "/api/v1/discovery/items/frigate/evidence"
client = ASGITestClient(app)


def projection_service(reader, *, entries=None) -> DynamicDiscoveryProjectionService:
    return DynamicDiscoveryProjectionService(
        catalog(*(entries or (entry(),))),
        reader,
    )


def install(
    monkeypatch: pytest.MonkeyPatch,
    service: DynamicDiscoveryProjectionService,
    *,
    now: datetime = NOW,
) -> None:
    monkeypatch.setattr(
        route_module, "get_discovery_projection_service", lambda: service
    )
    monkeypatch.setattr(route_module, "get_discovery_request_time", lambda: now)


def request_body() -> dict:
    response = client.get(PATH)
    assert response.status_code == 200
    return response.json()


def bounded_request(path: str = PATH) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as async_client:
            return await async_client.get(path)

    return asyncio.run(send())


def test_known_mapped_item_with_absent_cache_is_curated_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FakeReader(
        {
            FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )
        }
    )
    install(monkeypatch, projection_service(reader))

    body = request_body()

    assert body["schema_version"] == MERGED_ITEM_SCHEMA
    assert body["catalog_item_id"] == "frigate"
    assert body["curated"]["item"]["id"] == "frigate"
    assert body["dynamic_claims"] == []
    assert body["source_states"] == [
        {
            "source_id": FRIGATE_ADAPTER_ID,
            "health": None,
            "cache_state": "absent",
        }
    ]
    assert body["conflict_state"] == "none"
    assert reader.calls == [(FRIGATE_ADAPTER_ID, NOW)]


def test_production_dependency_handles_missing_cache_without_creating_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = tmp_path / "missing" / "discovery"
    monkeypatch.setattr(dependency_module, "DISCOVERY_CACHE_ROOT", cache_root)
    monkeypatch.setattr(
        dependency_module, "get_discovery_service", lambda: catalog(entry())
    )
    monkeypatch.setattr(route_module, "get_discovery_request_time", lambda: NOW)

    response = client.get(PATH)

    assert response.status_code == 200
    assert response.json()["source_states"][0]["cache_state"] == "absent"
    assert response.json()["dynamic_claims"] == []
    assert not cache_root.exists()


@pytest.mark.parametrize(
    ("age", "expected_freshness", "claim_count"),
    [
        (timedelta(hours=1), "fresh", 1),
        (timedelta(hours=25), "stale", 1),
        (timedelta(days=31), None, 0),
    ],
)
def test_valid_cache_freshness_states_are_projected_without_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    age: timedelta,
    expected_freshness: str | None,
    claim_count: int,
) -> None:
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(retrieved_at=NOW - age),))
    install(
        monkeypatch,
        projection_service(DynamicDiscoveryCacheReader(store)),
    )

    body = request_body()

    assert body["source_states"][0]["cache_state"] == "available"
    assert body["source_states"][0]["health"] is None
    assert len(body["dynamic_claims"]) == claim_count
    if expected_freshness is not None:
        assert body["dynamic_claims"][0]["freshness"] == expected_freshness
    assert body["conflict_state"] == "none"


def test_corrupt_cache_returns_bounded_curated_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(),))
    current = store.sources_path / FRIGATE_ADAPTER_ID / "current.json"
    current.write_text('{"broken":', encoding="utf-8")
    install(monkeypatch, projection_service(DynamicDiscoveryCacheReader(store)))

    body = request_body()

    assert body["dynamic_claims"] == []
    assert body["source_states"][0]["cache_state"] == "corrupt"
    assert body["conflict_state"] == "none"


@pytest.mark.parametrize("failure", [PermissionError, OSError, RuntimeError])
def test_inaccessible_cache_read_is_bounded_as_corrupt(
    monkeypatch: pytest.MonkeyPatch,
    failure: type[Exception],
) -> None:
    class FailingStore:
        def read_current(self, source_id: str):
            raise failure("/secret/cache/root bearer-token")

    install(
        monkeypatch,
        projection_service(DynamicDiscoveryCacheReader(FailingStore())),
    )

    response = client.get(PATH)

    assert response.status_code == 200
    assert response.json()["source_states"][0]["cache_state"] == "corrupt"
    assert response.json()["dynamic_claims"] == []
    assert "/secret/cache/root" not in response.text
    assert "bearer-token" not in response.text


def test_unmapped_curated_item_never_reads_dynamic_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailReader:
        def read_source(self, source_id: str, *, now: datetime):
            raise AssertionError("unmapped item must not read cache")

    install(
        monkeypatch,
        projection_service(FailReader(), entries=(entry("immich"),)),
    )

    response = client.get("/api/v1/discovery/items/immich/evidence")

    assert response.status_code == 200
    assert response.json()["dynamic_claims"] == []
    assert response.json()["source_states"] == []


def test_unknown_item_preserves_sanitized_404_and_does_not_read_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailReader:
        def read_source(self, source_id: str, *, now: datetime):
            raise AssertionError("unknown item must be rejected before cache lookup")

    install(monkeypatch, projection_service(FailReader()))

    response = client.get("/api/v1/discovery/items/missing/evidence")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Discovery item 'missing' was not found.",
        "status": 404,
        "details": {},
    }


def test_equivalent_timezone_clock_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FakeReader(
        {
            FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )
        }
    )
    install(
        monkeypatch,
        projection_service(reader),
        now=NOW.astimezone(timezone(timedelta(hours=5, minutes=30))),
    )

    request_body()

    assert reader.calls == [(FRIGATE_ADAPTER_ID, NOW)]


def test_naive_request_clock_fails_closed_without_synthesizing_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FakeReader(
        {
            FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )
        }
    )
    install(monkeypatch, projection_service(reader), now=NOW.replace(tzinfo=None))

    response = bounded_request()

    assert response.status_code == 500
    assert response.json()["error"]["message"] == (
        "An unexpected internal error occurred."
    )
    assert reader.calls == []
    assert "timezone-aware" not in response.text


def test_clock_failure_does_not_leak_raw_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "/opt/atlas/data/cache/discovery Authorization: Bearer clock-secret"

    def fail_clock() -> datetime:
        raise RuntimeError(secret)

    monkeypatch.setattr(
        route_module,
        "get_discovery_projection_service",
        lambda: projection_service(FakeReader({})),
    )
    monkeypatch.setattr(route_module, "get_discovery_request_time", fail_clock)

    response = bounded_request()

    assert response.status_code == 500
    assert secret not in response.text
    assert response.json()["error"]["code"] == "internal_server_error"


def test_repeated_get_is_byte_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = FakeReader(
        {
            FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )
        }
    )
    install(monkeypatch, projection_service(reader))

    first = client.get(PATH)
    second = client.get(PATH)

    assert first.content == second.content


def test_get_has_no_network_refresh_publish_or_initialize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FakeReader(
        {
            FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )
        }
    )
    install(monkeypatch, projection_service(reader))

    def forbidden(*args, **kwargs):
        raise AssertionError("GET crossed a forbidden side-effect boundary")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("socket.getaddrinfo", forbidden)
    monkeypatch.setattr(
        "app.discovery.dynamic_cache.DiscoveryCacheStore.initialize", forbidden
    )
    monkeypatch.setattr(
        "app.discovery.dynamic_cache.DiscoveryCacheStore.publish", forbidden
    )
    monkeypatch.setattr(
        "app.discovery.dynamic_refresh.RefreshCoordinator.refresh",
        forbidden,
    )
    monkeypatch.setattr(
        "app.discovery.dynamic_sources.FrigateGitHubLatestReleaseAdapter.fetch",
        forbidden,
    )

    assert request_body()["source_states"][0]["cache_state"] == "absent"


def test_anonymous_get_needs_no_csrf_or_write_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FakeReader(
        {
            FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )
        }
    )
    install(monkeypatch, projection_service(reader))

    response = client.get(PATH)

    assert response.status_code == 200
    assert "set-cookie" not in response.headers


def test_response_does_not_disclose_private_cache_or_transport_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(),))
    install(
        monkeypatch,
        projection_service(DynamicDiscoveryCacheReader(store)),
        now=NOW + timedelta(seconds=1),
    )

    encoded = json.dumps(request_body(), sort_keys=True)

    for forbidden in (
        "private-etag",
        "api_version",
        "etag",
        "generation",
        "checksum",
        "cache_root",
        "headers",
        "credentials",
        str(tmp_path),
        "api.github.com",
    ):
        assert forbidden not in encoded.lower()


def test_openapi_exposes_exact_get_only_contract() -> None:
    path = "/api/v1/discovery/items/{item_id}/evidence"
    operation = app.openapi()["paths"][path]

    assert set(operation) == {"get"}
    get = operation["get"]
    assert "requestBody" not in get
    assert "security" not in get
    assert [parameter["in"] for parameter in get.get("parameters", [])] == ["path"]
    assert get["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DiscoveryMergedItemProjection"
    }
    model = app.openapi()["components"]["schemas"]["DiscoveryMergedItemProjection"]
    assert model["properties"]["schema_version"]["const"] == MERGED_ITEM_SCHEMA


def test_legacy_item_json_and_openapi_do_not_gain_evidence_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(route_module, "get_discovery_service", lambda: catalog(entry()))

    response = client.get("/api/v1/discovery/items/frigate")

    assert response.status_code == 200
    assert set(response.json()) == {"schema_version", "item", "provenance", "metadata"}
    assert (
        not {
            "dynamic_claims",
            "source_states",
            "conflict_state",
        }
        & response.json().keys()
    )
    legacy = app.openapi()["paths"]["/api/v1/discovery/items/{item_id}"]["get"]
    assert legacy["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DiscoveryCatalogEntryResponse"
    }


def test_only_get_method_is_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    for method in ("post", "put", "patch", "delete"):
        response = client.request(method.upper(), PATH)
        assert response.status_code == 405


@pytest.mark.parametrize(
    "item_path",
    ["frigate%2Fevidence", "%2E%2E%5Cpath", "https:%2F%2Fevil.example"],
)
def test_path_shaped_unknown_items_cannot_select_cache_or_source(
    monkeypatch: pytest.MonkeyPatch,
    item_path: str,
) -> None:
    class FailReader:
        def read_source(self, source_id: str, *, now: datetime):
            raise AssertionError("malformed item path reached dynamic lookup")

    install(monkeypatch, projection_service(FailReader()))

    response = client.get(f"/api/v1/discovery/items/{item_path}/evidence")

    assert response.status_code == 404
    assert FRIGATE_ADAPTER_ID not in response.text
    assert "/opt/atlas/data/cache/discovery" not in response.text


def test_concurrent_publication_returns_one_complete_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(version="0.15.0"),))
    install(
        monkeypatch,
        projection_service(DynamicDiscoveryCacheReader(store)),
        now=NOW + timedelta(seconds=1),
    )
    started = Event()
    release = Event()

    def pause_after_generation(stage: str) -> None:
        if stage == "before_current_pointer_replace":
            started.set()
            release.wait(timeout=5)

    thread = Thread(
        target=lambda: store.publish(
            FRIGATE_ADAPTER_ID,
            (p1_record(version="0.16.1", retrieved_at=NOW + timedelta(seconds=1)),),
            failure_hook=pause_after_generation,
        )
    )
    thread.start()
    assert started.wait(timeout=5)
    holder = []
    reader = Thread(target=lambda: holder.append(client.get(PATH)))
    reader.start()
    release.set()
    thread.join(timeout=5)
    reader.join(timeout=5)

    assert len(holder) == 1
    response = holder[0]
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == MERGED_ITEM_SCHEMA
    assert body["source_states"][0]["cache_state"] == "available"
    assert [claim["version"] for claim in body["dynamic_claims"]] in (
        ["0.15.0"],
        ["0.16.1"],
    )


def test_bounded_catalog_errors_preserve_route_conventions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingService:
        def get_item_projection(self, item_id: str, *, now: datetime):
            raise DiscoveryItemNotFoundError(
                f"Discovery item '{item_id}' was not found."
            )

    monkeypatch.setattr(
        route_module, "get_discovery_projection_service", MissingService
    )
    monkeypatch.setattr(route_module, "get_discovery_request_time", lambda: NOW)

    response = client.get("/api/v1/discovery/items/missing/evidence")

    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_response_model_validation_rejects_malformed_dependency_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MalformedService:
        def get_item_projection(self, item_id: str, *, now: datetime):
            return {
                "schema_version": MERGED_ITEM_SCHEMA,
                "catalog_item_id": item_id,
                "curated": {},
                "dynamic_claims": [{"contradictory": True}],
                "source_states": [],
                "conflict_state": "none",
            }

    monkeypatch.setattr(
        route_module, "get_discovery_projection_service", MalformedService
    )
    monkeypatch.setattr(route_module, "get_discovery_request_time", lambda: NOW)

    response = bounded_request()

    assert response.status_code == 500
    assert "contradictory" not in response.text
    assert response.json()["error"]["code"] == "internal_server_error"


def test_projection_failure_does_not_leak_internal_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = (
        "/opt/atlas/data/cache/discovery https://api.github.com/repos/x/y"
        ' Authorization: Bearer secret-token ?token=raw {"payload":true}'
    )

    class FailingService:
        def get_item_projection(self, item_id: str, *, now: datetime):
            raise RuntimeError(secret)

    monkeypatch.setattr(
        route_module, "get_discovery_projection_service", FailingService
    )
    monkeypatch.setattr(route_module, "get_discovery_request_time", lambda: NOW)

    response = bounded_request()

    assert response.status_code == 500
    assert secret not in response.text
    assert "secret-token" not in response.text
    assert response.json()["error"]["message"] == (
        "An unexpected internal error occurred."
    )
