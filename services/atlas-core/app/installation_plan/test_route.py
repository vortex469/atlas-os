from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.installation_plan.assembly import (
    InstallationPlanClockUnavailable,
    InstallationPlanContractFailure,
    InstallationPlanItemNotFound,
    InstallationPlanReadDependency,
    InstallationPlanSourceUnavailable,
    default_installation_plan_dependency,
)
from app.main import app
from app.routes import installation_plan as route_module
from app.testing import ASGITestClient

PATH = "/api/v1/discovery/items/home-assistant/installation-plan"
GOLDEN = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"
client = ASGITestClient(app)


def fixed_clock() -> datetime:
    return datetime(2026, 8, 25, tzinfo=UTC)


@pytest.fixture
def production_reader(monkeypatch: pytest.MonkeyPatch) -> InstallationPlanReadDependency:
    dependency = default_installation_plan_dependency(
        repository_root=Path("/opt/atlas"),
        clock=fixed_clock,
    )
    monkeypatch.setattr(
        route_module,
        "get_installation_plan_read_dependency",
        lambda: dependency,
    )
    return dependency


def test_home_assistant_installation_plan_route(
    production_reader: InstallationPlanReadDependency,
) -> None:
    response = client.get(PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "installation-plan-v1"
    assert body["application"]["item_id"] == "home-assistant"
    assert body["application"]["release_version"] == "2026.8.3"
    assert body["deployment_artifact"] == {
        "state": "missing",
        "kind": "docker-compose",
        "repository_path": "compose/home-assistant.yaml",
        "service": "home-assistant",
        "content_digest": None,
    }
    assert body["image"] == {
        "state": "missing",
        "reference": None,
        "digest": None,
        "release_version": "2026.8.3",
    }
    assert body["compatibility"] == [
        {
            "environment": "item-scoped",
            "result": "unknown",
            "reason_code": "compatibility_fact_missing",
        }
    ]
    assert body["status"] == "missing_deployment_artifact"
    assert body["fingerprint"]["value"] == GOLDEN
    assert len(body["accepted_evidence"]) == 1
    assert body["accepted_evidence"][0]["claim"] == "immutable_image_release"
    assert body["accepted_evidence"][0]["trust"] == "accepted"
    assert body["deployment_artifact"]["state"] == "missing"


class FailingDependency:
    def __init__(self, failure: type[Exception], secret: str) -> None:
        self._failure = failure
        self._secret = secret

    def assemble(self, item_id: str) -> None:
        raise self._failure(self._secret)


@pytest.mark.parametrize(
    ("failure", "status", "message"),
    [
        (InstallationPlanItemNotFound, 404, "Installation plan item was not found."),
        (
            InstallationPlanSourceUnavailable,
            503,
            "Installation plan sources are unavailable.",
        ),
        (
            InstallationPlanClockUnavailable,
            503,
            "Installation plan clock is unavailable.",
        ),
        (
            InstallationPlanContractFailure,
            503,
            "Installation plan contract is unavailable.",
        ),
    ],
)
def test_typed_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    failure: type[Exception],
    status: int,
    message: str,
) -> None:
    secret = "/private/repository/parser detail: command --token evidence"
    dependency = FailingDependency(failure, secret)
    monkeypatch.setattr(
        route_module,
        "get_installation_plan_read_dependency",
        lambda: dependency,
    )

    response = client.get(PATH)

    assert response.status_code == status
    assert response.json()["error"]["message"] == message
    assert secret not in response.text
    assert "/private" not in response.text


def test_unknown_item_is_404(production_reader: InstallationPlanReadDependency) -> None:
    response = client.get(
        "/api/v1/discovery/items/not-in-the-catalog/installation-plan"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "installation_plan_item_not_found"
    assert response.json()["error"]["message"] == (
        "Installation plan item was not found."
    )


def test_required_source_failure_is_sanitized_at_route(
    production_reader: InstallationPlanReadDependency,
) -> None:
    secret = "/srv/private/catalog.yaml: parser exploded"

    class FailingCatalog:
        def read(self, item_id: str) -> None:
            raise RuntimeError(secret)

    production_reader._catalog = FailingCatalog()  # type: ignore[assignment]
    response = client.get(PATH)

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "Installation plan sources are unavailable."
    )
    assert secret not in response.text


@pytest.mark.parametrize(
    "clock",
    [
        lambda: "not-a-server-clock",
        lambda: (_ for _ in ()).throw(RuntimeError("clock backend secret")),
    ],
)
def test_invalid_or_failing_clock_is_sanitized_at_route(
    production_reader: InstallationPlanReadDependency,
    clock: object,
) -> None:
    production_reader._clock = clock  # type: ignore[assignment]
    response = client.get(PATH)

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "Installation plan clock is unavailable."
    )
    assert "backend secret" not in response.text


def test_contract_failure_is_sanitized_at_route(
    production_reader: InstallationPlanReadDependency,
) -> None:
    secret = "contract internals and evidence secret"

    class FailingAssembler:
        def assemble(self, **kwargs: object) -> None:
            raise ValueError(secret)

    production_reader._assembler = FailingAssembler()  # type: ignore[assignment]
    response = client.get(PATH)

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "Installation plan contract is unavailable."
    )
    assert secret not in response.text


def test_openapi_exposes_one_get_only_without_request_controls() -> None:
    schema = app.openapi()
    route = schema["paths"][
        "/api/v1/discovery/items/{item_id}/installation-plan"
    ]

    assert set(route) == {"get"}
    operation = route["get"]
    assert "requestBody" not in operation
    assert operation["parameters"] == [
        {
            "name": "item_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string", "title": "Item Id"},
        }
    ]
    assert operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/InstallationPlan"}

    item_route = schema["paths"]["/api/v1/discovery/items/{item_id}"]["get"]
    assert item_route["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/DiscoveryCatalogEntryResponse"}


def test_installation_plan_path_does_not_collide_with_item_detail(
    production_reader: InstallationPlanReadDependency,
) -> None:
    response = client.get(PATH)

    assert response.status_code == 200
    assert response.json()["schema_version"] == "installation-plan-v1"


class CountingDependency:
    def __init__(self) -> None:
        self.calls = 0

    def assemble(self, item_id: str) -> None:
        self.calls += 1
        raise AssertionError("assembly must not run")


@pytest.mark.parametrize(
    ("path", "content"),
    [
        (PATH + "?evaluation_instant=evil", None),
        (PATH, b"not-empty"),
        ("/api/v1/discovery/items/BAD!/installation-plan", None),
        (PATH + "/", None),
    ],
)
def test_closed_inputs_are_422_without_assembly(
    monkeypatch: pytest.MonkeyPatch, path: str, content: bytes | None
) -> None:
    dependency = CountingDependency()
    monkeypatch.setattr(
        route_module, "get_installation_plan_read_dependency", lambda: dependency
    )
    response = client.request("GET", path, content=content)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert dependency.calls == 0


@pytest.mark.parametrize(
    ("item_id", "status"),
    [
        ("a", 404),
        ("a" * 64, 404),
        ("a" * 65, 422),
        ("A", 422),
        ("caf%C3%A9", 422),
        ("a%20b", 422),
        ("a.b", 422),
        ("a_b", 422),
        ("a:b", 422),
        ("a-", 422),
        ("-a", 422),
        ("a--b", 422),
        ("valid-unknown-item", 404),
    ],
)
def test_item_id_route_grammar_precedes_assembly(
    monkeypatch: pytest.MonkeyPatch, item_id: str, status: int
) -> None:
    if status == 422:
        dependency: object = CountingDependency()
    else:
        dependency = FailingDependency(InstallationPlanItemNotFound, "not found")
    monkeypatch.setattr(
        route_module, "get_installation_plan_read_dependency", lambda: dependency
    )
    response = client.get(
        f"/api/v1/discovery/items/{item_id}/installation-plan",
        follow_redirects=False,
    )
    assert response.status_code == status
    if status == 422:
        assert isinstance(dependency, CountingDependency)
        assert dependency.calls == 0


@pytest.mark.parametrize(
    ("headers", "content"),
    [
        ({"content-length": "1"}, None),
        ({"content-length": "invalid"}, None),
        ({"content-length": "-1"}, None),
        ({"transfer-encoding": "chunked"}, None),
        (None, b" "),
        (None, b'{}'),
        ({"content-type": "application/x-www-form-urlencoded"}, b"a=b"),
    ],
)
def test_body_and_body_framing_are_rejected_before_assembly(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str] | None,
    content: bytes | None,
) -> None:
    dependency = CountingDependency()
    monkeypatch.setattr(
        route_module, "get_installation_plan_read_dependency", lambda: dependency
    )
    response = client.request("GET", PATH, headers=headers, content=content)
    assert response.status_code == 422
    assert dependency.calls == 0


def test_conflicting_content_lengths_are_rejected_before_assembly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = CountingDependency()
    monkeypatch.setattr(
        route_module, "get_installation_plan_read_dependency", lambda: dependency
    )
    response = client.request(
        "GET", PATH, headers=[("content-length", "0"), ("content-length", "1")]
    )
    assert response.status_code == 422
    assert dependency.calls == 0


@pytest.mark.parametrize("suffix", ["/", "//", "/%2F"])
def test_trailing_separator_forms_do_not_redirect_or_assemble(
    monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    dependency = CountingDependency()
    monkeypatch.setattr(
        route_module, "get_installation_plan_read_dependency", lambda: dependency
    )
    response = client.get(PATH + suffix, follow_redirects=False)
    assert response.status_code == 422
    assert not response.is_redirect
    assert dependency.calls == 0


@pytest.mark.parametrize(
    "item_id",
    [
        "home%2Fassistant",
        "home%2fassistant",
        "home%252Fassistant",
        "home%5Cassistant",
        "home%5cassistant",
        "a%2Fb",
        "a//b",
    ],
)
def test_path_shaping_item_ids_are_sanitized_422_without_assembly(
    monkeypatch: pytest.MonkeyPatch, item_id: str
) -> None:
    dependency = CountingDependency()
    monkeypatch.setattr(
        route_module, "get_installation_plan_read_dependency", lambda: dependency
    )
    response = client.get(
        f"/api/v1/discovery/items/{item_id}/installation-plan",
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == (
        "Installation plan request is invalid."
    )
    assert not response.is_redirect
    assert dependency.calls == 0


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutation_methods_are_405(method: str) -> None:
    assert client.request(method, PATH).status_code == 405


def test_unrelated_suffix_is_404() -> None:
    assert client.get(PATH + "/extra").status_code == 404


def test_unexpected_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "unexpected backend secret"

    class UnexpectedDependency:
        def assemble(self, item_id: str) -> None:
            raise RuntimeError(secret)

    monkeypatch.setattr(
        route_module,
        "get_installation_plan_read_dependency",
        lambda: UnexpectedDependency(),
    )
    response = client.get(PATH)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert secret not in response.text
