from app.main import app

EXPECTED_DISCOVERY_PATHS = {
    "/api/v1/discovery",
    "/api/v1/discovery/items",
    "/api/v1/discovery/items/{item_id}",
    "/api/v1/discovery/items/{item_id}/evidence",
    "/api/v1/discovery/items/{item_id}/image-grounding",
    "/api/v1/discovery/items/{item_id}/relationships",
    "/api/v1/discovery/items/{item_id}/compatibility",
    "/api/v1/discovery/proposals",
    "/api/v1/discovery/proposals/{proposal_id}",
    "/api/v1/discovery/search",
}

EXPECTED_EXECUTION_CANDIDATE_PATHS = {
    "/api/v1/execution-candidates",
    "/api/v1/execution-candidates/{candidate_id}",
    "/api/v1/execution-candidates/{candidate_id}/planning-intake",
    "/api/v1/execution-candidates/operator-intents",
    "/api/v1/execution-candidates/operator-intents/capabilities",
    "/api/v1/execution-candidates/operator-intents/capabilities/{selector_id}/resources",
    "/api/v1/execution-candidates/operator-intents/resources",
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
        "/api/v1/providers/{provider_id}/resources/{resource_id}/expectation"
    ) in paths
    assert EXPECTED_DISCOVERY_PATHS.issubset(paths)
    assert EXPECTED_EXECUTION_CANDIDATE_PATHS.issubset(paths)


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


def test_execution_candidate_endpoint_set_is_stable() -> None:
    candidate_paths = {
        path
        for path in schema_paths()
        if path.startswith("/api/v1/execution-candidates")
    }

    assert candidate_paths == EXPECTED_EXECUTION_CANDIDATE_PATHS


def test_execution_candidate_routes_expose_expected_methods() -> None:
    schema = app.openapi()

    assert set(schema["paths"]["/api/v1/execution-candidates"]) == {"get"}
    assert set(schema["paths"]["/api/v1/execution-candidates/{candidate_id}"]) == {
        "get"
    }
    assert set(
        schema["paths"]["/api/v1/execution-candidates/{candidate_id}/planning-intake"]
    ) == {"post"}
    assert set(schema["paths"]["/api/v1/execution-candidates/operator-intents"]) == {
        "post"
    }
    assert set(
        schema["paths"]["/api/v1/execution-candidates/operator-intents/capabilities"]
    ) == {"get"}
    assert set(
        schema["paths"][
            "/api/v1/execution-candidates/operator-intents/capabilities/"
            "{selector_id}/resources"
        ]
    ) == {"get"}
    assert set(
        schema["paths"]["/api/v1/execution-candidates/operator-intents/resources"]
    ) == {"get"}


def test_execution_candidate_openapi_uses_public_response_dtos() -> None:
    schema_names = set(app.openapi()["components"]["schemas"])

    assert "ExecutionCandidate" not in schema_names
    assert "ProjectionResult" not in schema_names
    assert "ExecutionEligibilityResult" not in schema_names
    assert "CandidatePlanningIntakeResult" in schema_names
    assert "CandidatePlanningIntakeRequest" in schema_names
    assert "ExecutionCandidateResponse" in schema_names
    assert "ExecutionCandidatePageResponse" in schema_names


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
