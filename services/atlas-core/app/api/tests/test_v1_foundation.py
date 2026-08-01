from app.main import app

EXPECTED_DISCOVERY_PATHS = {
    "/api/v1/discovery",
    "/api/v1/discovery/items",
    "/api/v1/discovery/items/{item_id}",
    "/api/v1/discovery/items/{item_id}/relationships",
    "/api/v1/discovery/items/{item_id}/compatibility",
    "/api/v1/discovery/search",
}

INTERNAL_DISCOVERY_SCHEMA_NAMES = {
    "CapabilityReference",
    "CatalogEntry",
    "CatalogProvenance",
    "DiscoveryRelationship",
    "DiscoveryRequirements",
    "NetworkRequirements",
    "PlatformRequirements",
    "PortRequirement",
    "ResourceRequirements",
}


def schema_paths() -> set[str]:
    return set(app.openapi()["paths"])


def test_api_v1_foundation_routes_are_registered() -> None:
    paths = schema_paths()

    assert "/api/v1" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/dashboard" in paths
    assert "/api/v1/status/" in paths
    assert "/api/v1/providers/{provider_id}/resources" in paths
    assert "/api/v1/providers/{provider_id}/discovery/refresh" in paths
    assert (
        "/api/v1/providers/{provider_id}/resources/"
        "{resource_id}/expectation"
    ) in paths
    assert EXPECTED_DISCOVERY_PATHS.issubset(paths)


def test_discovery_endpoint_set_is_stable() -> None:
    discovery_paths = {
        path for path in schema_paths() if path.startswith("/api/v1/discovery")
    }

    assert discovery_paths == EXPECTED_DISCOVERY_PATHS


def test_discovery_routes_are_read_only() -> None:
    schema = app.openapi()

    discovery_paths = {
        path: methods
        for path, methods in schema["paths"].items()
        if path.startswith("/api/v1/discovery")
    }

    assert discovery_paths
    for methods in discovery_paths.values():
        assert set(methods) == {"get"}


def test_discovery_openapi_uses_public_response_dtos() -> None:
    schema_names = set(app.openapi()["components"]["schemas"])

    assert INTERNAL_DISCOVERY_SCHEMA_NAMES.isdisjoint(schema_names)


def test_discovery_openapi_contract_does_not_expose_score_fields() -> None:
    schemas = app.openapi()["components"]["schemas"]

    for schema_name, schema in schemas.items():
        if "Discovery" not in schema_name:
            continue
        properties = schema.get("properties", {})
        assert "score" not in properties


def test_legacy_dashboard_routes_remain_registered() -> None:
    paths = schema_paths()

    assert "/health" in paths
    assert "/dashboard" in paths


def test_versioned_and_legacy_dashboard_contracts_match() -> None:
    schema = app.openapi()

    legacy = schema["paths"]["/dashboard"]["get"]
    versioned = schema["paths"]["/api/v1/dashboard"]["get"]

    assert (
        legacy["responses"]["200"]["content"]["application/json"]["schema"]
        == versioned["responses"]["200"]["content"]["application/json"]["schema"]
    )
