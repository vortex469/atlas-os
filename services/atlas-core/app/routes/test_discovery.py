from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.discovery.loader import YamlCatalogLoader
from app.main import app
from app.routes import discovery as route_module
from app.services.discovery import DiscoveryCatalogService
from app.testing import ASGITestClient

client = ASGITestClient(app)


def entry_yaml(
    *,
    item_id: str,
    name: str,
    item_type: str = "application",
    status: str = "active",
    tags: list[str] | None = None,
    capabilities: list[str] | None = None,
    relationships: str = "[]",
    description: str = "",
    entry_id: str | None = None,
) -> str:
    document = {
        "schema_version": 1,
        "item": {
            "id": item_id,
            "type": item_type,
            "status": status,
            "name": name,
            "description": description,
            "tags": tags or [],
            "capabilities": [{"id": capability} for capability in (capabilities or [])],
            "relationships": yaml.safe_load(relationships),
        },
        "provenance": {
            "source_type": "curated",
            "source": "Atlas test catalog",
            "trust_level": "curated",
        },
        "metadata": {"public_note": "safe"},
    }
    if entry_id is not None:
        document["provenance"]["entry_id"] = entry_id
    return yaml.safe_dump(document, sort_keys=False)


def write_entry(catalog_dir: Path, filename: str, content: str) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / filename).write_text(content, encoding="utf-8")


@pytest.fixture
def catalog_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "catalog"
    write_entry(
        path,
        "postgres.yaml",
        entry_yaml(
            item_id="postgresql",
            name="PostgreSQL",
            item_type="service",
            tags=["database", "storage"],
            capabilities=["relational-database"],
            description="Relational database service",
            entry_id="entry-postgresql",
        ),
    )
    write_entry(
        path,
        "immich.yaml",
        entry_yaml(
            item_id="immich",
            name="Immich",
            tags=["photos", "media"],
            capabilities=["photo-library"],
            relationships="""
    - type: depends_on
      target: postgresql
      required: true
      description: Stores photo metadata
    - type: integrates_with
      target: redis
      required: false
""".rstrip(),
            description="Self-hosted photo library",
            entry_id="entry-immich",
        ),
    )
    service = DiscoveryCatalogService(YamlCatalogLoader(path))
    monkeypatch.setattr(route_module, "get_discovery_service", lambda: service)
    return path


@pytest.fixture
def empty_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "missing-default-catalog"
    service = DiscoveryCatalogService(YamlCatalogLoader())
    service._loader = YamlCatalogLoader(path)
    service._loader._explicit_catalog_path = False
    monkeypatch.setattr(route_module, "get_discovery_service", lambda: service)
    return path


def test_metadata_reports_empty_absent_default_catalog(empty_catalog: Path) -> None:
    response = client.get("/api/v1/discovery")

    assert response.status_code == 200
    assert response.json() == {
        "catalog_loaded": True,
        "entry_count": 0,
        "schema_version": 1,
    }


def test_items_returns_empty_page_for_absent_default_catalog(empty_catalog: Path) -> None:
    response = client.get("/api/v1/discovery/items")

    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["total"] == 0
    assert body["has_more"] is False


def test_item_detail_missing_returns_404(empty_catalog: Path) -> None:
    response = client.get("/api/v1/discovery/items/immich")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Discovery item 'immich' was not found."


def test_items_returns_public_api_models_without_internal_domain_score(catalog_dir: Path) -> None:
    response = client.get("/api/v1/discovery/items")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [entry["item"]["id"] for entry in body["entries"]] == ["immich", "postgresql"]
    assert body["entries"][0]["item"]["capabilities"] == ["photo-library"]
    assert "score" not in response.text


def test_items_filters_then_paginates_in_deterministic_order(catalog_dir: Path) -> None:
    response = client.get(
        "/api/v1/discovery/items",
        params=[("tag", "media"), ("limit", "1"), ("offset", "0")],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [entry["item"]["id"] for entry in body["entries"]] == ["immich"]
    assert body["has_more"] is False


def test_items_support_type_status_capability_and_relationship_filters(catalog_dir: Path) -> None:
    response = client.get(
        "/api/v1/discovery/items",
        params={
            "type": "application",
            "status": "active",
            "capability": "photo-library",
            "relationship_type": "depends_on",
            "relationship_target": "postgresql",
        },
    )

    assert response.status_code == 200
    assert [entry["item"]["id"] for entry in response.json()["entries"]] == ["immich"]


def test_duplicate_filter_values_return_422(catalog_dir: Path) -> None:
    response = client.get(
        "/api/v1/discovery/items",
        params=[("tag", "media"), ("tag", "media")],
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Discovery query validation failed."


def test_item_detail_returns_public_entry(catalog_dir: Path) -> None:
    response = client.get("/api/v1/discovery/items/immich")

    assert response.status_code == 200
    body = response.json()
    assert body["item"]["id"] == "immich"
    assert body["provenance"]["entry_id"] == "entry-immich"
    assert body["metadata"] == {"public_note": "safe"}


def test_relationships_returns_incoming_and_outgoing_collections(catalog_dir: Path) -> None:
    response = client.get("/api/v1/discovery/items/postgresql/relationships")

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == "postgresql"
    assert [item["source_item_id"] for item in body["incoming"]] == ["immich"]
    assert body["incoming"][0]["resolved"] is True
    assert body["outgoing"] == []


def test_relationships_support_type_filter_and_unresolved_optional_relationships(
    catalog_dir: Path,
) -> None:
    response = client.get(
        "/api/v1/discovery/items/immich/relationships",
        params={"type": "integrates_with"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["incoming"] == []
    assert len(body["outgoing"]) == 1
    assert body["outgoing"][0]["target"] == "redis"
    assert body["outgoing"][0]["resolved"] is False


def test_search_requires_query(catalog_dir: Path) -> None:
    response = client.get("/api/v1/discovery/search")

    assert response.status_code == 422


def test_search_ranks_then_filters_then_paginates_without_raw_scores(catalog_dir: Path) -> None:
    response = client.get(
        "/api/v1/discovery/search",
        params={"q": "photo", "tag": "media", "limit": "1", "offset": "0"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [result["item"]["id"] for result in body["results"]] == ["immich"]
    assert body["results"][0]["evidence"]
    assert "score" not in response.text


def test_catalog_errors_are_sanitized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "catalog"
    write_entry(path, "broken.yaml", "not: [valid")
    service = DiscoveryCatalogService(YamlCatalogLoader(path))
    monkeypatch.setattr(route_module, "get_discovery_service", lambda: service)

    response = client.get("/api/v1/discovery/items")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Discovery catalog is unavailable."
    assert str(path) not in response.text
    assert "broken.yaml" not in response.text
    assert "ValidationError" not in response.text


def test_repository_initializes_once_for_multiple_requests(
    catalog_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = route_module.get_discovery_service()
    calls = 0
    original_load = service._loader.load

    def counted_load():
        nonlocal calls
        calls += 1
        return original_load()

    monkeypatch.setattr(service._loader, "load", counted_load)

    assert client.get("/api/v1/discovery/items").status_code == 200
    assert client.get("/api/v1/discovery/search", params={"q": "photo"}).status_code == 200
    assert calls == 1
