from app.main import app


def schema_paths() -> set[str]:
    return set(app.openapi()["paths"])


def test_api_v1_foundation_routes_are_registered() -> None:
    paths = schema_paths()

    assert "/api/v1" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/dashboard" in paths
    assert "/api/v1/status/" in paths


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
