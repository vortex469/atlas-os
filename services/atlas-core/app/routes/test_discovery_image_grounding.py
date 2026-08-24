from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from starlette.requests import Request

from app.core.exceptions import unhandled_exception_handler
from app.discovery.exceptions import (
    DiscoveryCatalogValidationError,
    ImageReleaseEvidenceValidationError,
)
from app.discovery.image_grounding import ImageGroundingResult, ImageGroundingStatus
from app.discovery.image_grounding_projection import (
    DISCOVERY_IMAGE_GROUNDING_PROJECTION_SCHEMA,
    project_image_grounding,
)
from app.discovery.models import (
    CatalogProvenance,
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
    RepositoryComposeImageObservation,
)
from app.main import app
from app.routes import discovery as route_module
from app.services import discovery_image_grounding as dependency_module
from app.services.discovery_image_grounding import (
    ImageGroundingReadError,
    ImageGroundingReadFailure,
    ImageGroundingReadModel,
)
from app.testing import ASGITestClient

PATH = "/api/v1/discovery/items/home-assistant/image-grounding"
REFERENCE = "ghcr.io/home-assistant/home-assistant"
DIGEST = "sha256:" + "1" * 64
VERSION = "2026.8.3"
client = ASGITestClient(app)

UNAVAILABLE = "Image grounding is unavailable."
INTERNAL_MARKERS = ("SECRET", "token=hidden", "/private/repository")


def test_real_home_assistant_composition_matches_existing_consumer(
    monkeypatch,
    tmp_path,
) -> None:
    compose = tmp_path / "compose/home-assistant.yaml"
    compose.parent.mkdir()
    compose.write_text(
        "services:\n"
        "  home-assistant:\n"
        "    image: "
        "ghcr.io/home-assistant/home-assistant@"
        "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dependency_module, "ATLAS_ROOT", tmp_path)

    response = client.get(PATH)
    existing_module = importlib.import_module(
        "app.services.home_assistant_" + "image_grounding"
    )
    existing = existing_module.HomeAssistantImageGroundingService(tmp_path).ground()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "grounded"
    assert body["release_version"] == "2026.8.3"
    assert body["observed_image"] == {
        "image_reference": "ghcr.io/home-assistant/home-assistant",
        "image_digest": (
            "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"
        ),
    }
    assert body["status"] == existing.status.value
    assert body["release_version"] == existing.release_version
    assert body["observed_image"]["image_reference"] == existing.image_reference
    assert body["observed_image"]["image_digest"] == existing.image_digest


def evidence(
    source_class: ImageReleaseEvidenceSourceClass = (
        ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED
    ),
    source_id: str = "accepted:test",
    digest: str = DIGEST,
) -> ImageReleaseEvidence:
    return ImageReleaseEvidence(
        catalog_item_id="home-assistant",
        release_version=VERSION,
        image_reference=REFERENCE,
        image_digest=digest,
        source_class=source_class,
        source_id=source_id,
        attested_at=datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC),
    )


def read_model(
    status: ImageGroundingStatus = ImageGroundingStatus.GROUNDED,
    *,
    rows: tuple[ImageReleaseEvidence, ...] | None = None,
    image: str | None = f"{REFERENCE}@{DIGEST}",
    release_version: str | None = VERSION,
    reason: str | None = "internal reason /secret/path token=hidden",
) -> ImageGroundingReadModel:
    observation = None
    if image is not None:
        observation = RepositoryComposeImageObservation(
            compose_file="compose/home-assistant.yaml",
            compose_service="home-assistant",
            image=image,
        )
    return ImageGroundingReadModel(
        grounding=ImageGroundingResult(
            status=status,
            catalog_item_id="home-assistant",
            release_version=release_version,
            image_reference=REFERENCE if observation is not None else None,
            image_digest=DIGEST if status is ImageGroundingStatus.GROUNDED else None,
            reason=reason,
        ),
        catalog_provenance=CatalogProvenance(source="/secret/catalog/path"),
        repository_observation=observation,
        image_release_evidence=rows if rows is not None else (evidence(),),
    )


def install(monkeypatch: pytest.MonkeyPatch, value) -> SimpleNamespace:
    service = SimpleNamespace(get=lambda item_id: value)
    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        lambda: service,
    )
    return service


def bounded_get(path: str = PATH) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as async_client:
            return await async_client.get(path)

    return asyncio.run(send())


def assert_sanitized_unavailable(response: httpx.Response) -> None:
    assert response.status_code == 503
    assert response.json()["error"]["message"] == UNAVAILABLE
    exposed = response.text + repr(response) + repr(response.json())
    assert not any(marker in exposed for marker in INTERNAL_MARKERS)


def install_real_service(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(dependency_module, "ATLAS_ROOT", root)
    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        dependency_module.get_discovery_image_grounding_service,
    )


@pytest.mark.parametrize(
    "case",
    ("missing", "malformed", "anchor", "invalid_utf8", "oversized", "symlink"),
)
def test_compose_input_failures_through_real_get_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    compose = tmp_path / "compose/home-assistant.yaml"
    if case != "missing":
        compose.parent.mkdir()
    if case == "malformed":
        compose.write_text("services: [SECRET /private/repository", encoding="utf-8")
    elif case == "anchor":
        compose.write_text(
            "services:\n"
            "  home-assistant: &unsafe\n"
            f"    image: {REFERENCE}@{DIGEST}\n"
            "  copied: *unsafe\n",
            encoding="utf-8",
        )
    elif case == "invalid_utf8":
        compose.write_bytes(b"services:\n  home-assistant:\n    image: \xffSECRET")
    elif case == "oversized":
        compose.write_bytes(b"# SECRET /private/repository\n" + b"x" * (256 * 1024))
    elif case == "symlink":
        target = tmp_path / "private-compose.yaml"
        target.write_text("token=hidden", encoding="utf-8")
        compose.symlink_to(target)

    install_real_service(monkeypatch, tmp_path)

    assert_sanitized_unavailable(client.get(PATH))


@pytest.mark.parametrize(
    ("loader", "error"),
    (
        (
            "catalog",
            DiscoveryCatalogValidationError(
                "SECRET catalog failure at /private/repository token=hidden"
            ),
        ),
        (
            "evidence",
            ImageReleaseEvidenceValidationError(
                "SECRET evidence failure at /private/repository token=hidden"
            ),
        ),
    ),
)
def test_typed_loader_failures_through_real_get_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    loader: str,
    error: Exception,
) -> None:
    compose = tmp_path / "compose/home-assistant.yaml"
    compose.parent.mkdir()
    compose.write_text(
        f"services:\n  home-assistant:\n    image: {REFERENCE}@{DIGEST}\n",
        encoding="utf-8",
    )
    install_real_service(monkeypatch, tmp_path)
    service_globals = (
        dependency_module.BindingDrivenImageGroundingService.get.__globals__
    )
    target = service_globals[
        "YamlCatalogLoader" if loader == "catalog" else "ImageReleaseEvidenceLoader"
    ]

    def fail_load(self):
        raise error

    monkeypatch.setattr(target, "load", fail_load)
    assert_sanitized_unavailable(client.get(PATH))


def test_grounded_request_returns_exact_redacted_projection(monkeypatch) -> None:
    model = read_model()
    install(monkeypatch, model)

    response = client.get(PATH)

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": DISCOVERY_IMAGE_GROUNDING_PROJECTION_SCHEMA,
        "catalog_item_id": "home-assistant",
        "status": "grounded",
        "release_version": VERSION,
        "deployment_binding": {
            "compose_file": "compose/home-assistant.yaml",
            "compose_service": "home-assistant",
            "mutable_property": "image",
            "deployment_method": "docker-compose",
        },
        "observed_image": {
            "image_reference": REFERENCE,
            "image_digest": DIGEST,
        },
        "accepted_evidence": [
            {
                "release_version": VERSION,
                "image_reference": REFERENCE,
                "image_digest": DIGEST,
                "source_class": "registry_attested",
                "source_id": "accepted:test",
                "attested_at": "2026-08-21T20:54:36Z",
            }
        ],
    }
    serialized = response.text
    for forbidden in ("internal reason", "/secret/catalog/path", "token=hidden"):
        assert forbidden not in serialized


@pytest.mark.parametrize("status", tuple(ImageGroundingStatus))
def test_every_p1_status_is_informational_200(monkeypatch, status) -> None:
    model = read_model(
        status,
        image=None
        if status is ImageGroundingStatus.NO_REPOSITORY_OBSERVATION
        else f"{REFERENCE}@{DIGEST}",
    )
    install(monkeypatch, model)

    response = client.get(PATH)

    assert response.status_code == 200
    assert response.json()["status"] == status.value


def test_non_strict_release_is_redacted_for_200_negative_status(monkeypatch) -> None:
    install(
        monkeypatch,
        read_model(
            ImageGroundingStatus.NO_STRICT_RELEASE_VERSION,
            release_version="latest SECRET",
            image=None,
        ),
    )
    response = client.get(PATH)
    assert response.status_code == 200
    assert response.json()["release_version"] is None
    assert "SECRET" not in response.text


def test_unknown_item_is_sanitized_404(monkeypatch) -> None:
    class Service:
        def get(self, item_id):
            raise ImageGroundingReadError(
                ImageGroundingReadFailure.CATALOG_ITEM_NOT_FOUND,
                item_id,
            )

    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        Service,
    )
    response = client.get(PATH.replace("home-assistant", "missing"))
    assert response.status_code == 404
    assert response.json()["error"]["message"] == (
        "Discovery item 'missing' was not found."
    )


@pytest.mark.parametrize("error", [ValueError("secret"), UnicodeError("secret")])
def test_local_or_projection_failure_is_sanitized_503(monkeypatch, error) -> None:
    class Service:
        def get(self, item_id):
            raise error

    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        Service,
    )
    response = client.get(PATH)
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Image grounding is unavailable."
    assert "secret" not in response.text


def test_unexpected_failure_uses_standard_sanitized_500(monkeypatch) -> None:
    class Unexpected(RuntimeError):
        pass

    class Service:
        def get(self, item_id):
            raise Unexpected("secret internal marker")

    monkeypatch.setattr(
        route_module,
        "get_discovery_image_grounding_service",
        Service,
    )
    with pytest.raises(Unexpected) as caught:
        route_module.get_discovery_item_image_grounding("home-assistant")
    monkeypatch.setattr(
        "app.core.exceptions.logger.exception", lambda *args, **kwargs: None
    )
    response = asyncio.run(
        unhandled_exception_handler(Request({"type": "http"}), caught.value)
    )
    assert response.status_code == 500
    body = response.body.decode("utf-8")
    assert "An unexpected internal error occurred." in body
    assert "secret internal marker" not in body


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutation_methods_remain_unsupported(method) -> None:
    response = client.request(method, PATH)
    assert response.status_code == 405


def test_openapi_exposes_get_only_and_bounded_contract() -> None:
    operation = app.openapi()["paths"][
        "/api/v1/discovery/items/{item_id}/image-grounding"
    ]
    assert set(operation) == {"get"}
    get = operation["get"]
    assert "requestBody" not in get
    assert [(p["in"], p["name"]) for p in get["parameters"]] == [("path", "item_id")]
    assert set(get["responses"]) >= {"200", "404", "503"}
    schemas = app.openapi()["components"]["schemas"]
    projection = schemas["DiscoveryImageGroundingProjection"]
    assert projection["properties"]["accepted_evidence"]["maxItems"] == 100
    assert projection["properties"]["catalog_item_id"]["maxLength"] == 64
    assert (
        schemas["PublicObservedImageIdentity"]["properties"]["image_digest"][
            "minLength"
        ]
        == 71
    )


def test_evidence_provenance_and_conflicts_are_retained_in_canonical_order(
    monkeypatch,
) -> None:
    rows = (
        evidence(ImageReleaseEvidenceSourceClass.CURATED, "b"),
        evidence(ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED, "a"),
        evidence(ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED, "untrusted"),
        evidence(
            ImageReleaseEvidenceSourceClass.CURATED, "conflict", "sha256:" + "2" * 64
        ),
    )
    model = read_model(ImageGroundingStatus.CONFLICTED, rows=rows)
    install(monkeypatch, model)
    public = client.get(PATH).json()["accepted_evidence"]
    assert [row["source_class"] for row in public] == [
        row.source_class.value for row in rows
    ]
    assert [row["source_id"] for row in public] == [row.source_id for row in rows]


def test_more_than_100_evidence_rows_fails_closed(monkeypatch) -> None:
    rows = tuple(evidence(source_id=f"source-{index}") for index in range(101))
    install(monkeypatch, read_model(rows=rows))
    response = client.get(PATH)
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Image grounding is unavailable."


def test_overlong_public_string_fails_closed_without_truncation_or_leak(
    monkeypatch,
) -> None:
    overbound_reference = "a" * 500 + ".example/image"
    assert len(overbound_reference) > 512
    model = read_model(image=f"{overbound_reference}@{DIGEST}")
    assert model.repository_observation is not None
    assert model.repository_observation.image.startswith(overbound_reference)
    install(monkeypatch, model)

    response = client.get(PATH)

    assert_sanitized_unavailable(response)
    assert overbound_reference not in response.text


def test_route_equals_pure_projection_and_repeats_byte_identically(monkeypatch) -> None:
    model = read_model()
    install(monkeypatch, model)
    expected = project_image_grounding(model).model_dump(mode="json")
    first = client.get(PATH)
    second = client.get(PATH)
    assert first.json() == expected
    assert first.content == second.content
