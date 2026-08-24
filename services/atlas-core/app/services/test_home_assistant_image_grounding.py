from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.discovery.exceptions import (
    ImageReleaseEvidenceConflictError,
    ImageReleaseEvidenceYamlError,
    RepositoryComposeObservationError,
)
from app.discovery.image_grounding import ImageGroundingResult, ImageGroundingStatus
from app.discovery.loader import LoadedCatalog, YamlCatalogLoader
from app.discovery.models import (
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)
from app.services import home_assistant_image_grounding as composition

ITEM_ID = "home-assistant"
VERSION = "2026.8.3"
REFERENCE = "ghcr.io/home-assistant/home-assistant"
DIGEST = "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"
IMAGE = f"{REFERENCE}@{DIGEST}"


def _catalog_entry():
    return next(
        entry
        for entry in YamlCatalogLoader().load().entries
        if entry.item.id == ITEM_ID
    )


def _write_compose(
    root: Path, image: str = IMAGE, *, service: str = "home-assistant"
) -> None:
    target = root / "compose/home-assistant.yaml"
    target.parent.mkdir()
    target.write_text(
        f"services:\n  {service}:\n    image: {image}\n", encoding="utf-8"
    )


def _evidence(
    *,
    release_version: str = VERSION,
    image_reference: str = REFERENCE,
    image_digest: str = DIGEST,
    source_class: ImageReleaseEvidenceSourceClass = ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
    source_id: str = "test-source",
) -> ImageReleaseEvidence:
    return ImageReleaseEvidence(
        catalog_item_id=ITEM_ID,
        release_version=release_version,
        image_reference=image_reference,
        image_digest=image_digest,
        source_class=source_class,
        source_id=source_id,
        attested_at=datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC),
    )


def _replace_catalog(monkeypatch, entry) -> None:
    class Loader:
        def load(self):
            return LoadedCatalog(entries=(() if entry is None else (entry,)))

    monkeypatch.setattr(composition, "YamlCatalogLoader", Loader)


def _replace_evidence(monkeypatch, *rows: ImageReleaseEvidence) -> None:
    class Loader:
        def load(self):
            return SimpleNamespace(rows=tuple(rows))

    monkeypatch.setattr(composition, "ImageReleaseEvidenceLoader", Loader)


def test_exact_reviewed_inputs_return_existing_grounded_result(tmp_path: Path) -> None:
    _write_compose(tmp_path)

    result = composition.HomeAssistantImageGroundingService(tmp_path).ground()

    assert type(result) is ImageGroundingResult
    assert result.status is ImageGroundingStatus.GROUNDED
    assert result.catalog_item_id == ITEM_ID
    assert result.release_version == VERSION
    assert result.image_reference == REFERENCE
    assert result.image_digest == DIGEST


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        (
            f"ghcr.io/example/home-assistant@{DIGEST}",
            ImageGroundingStatus.REPOSITORY_IDENTITY_MISMATCH,
        ),
        (f"{REFERENCE}@sha256:{'0' * 64}", ImageGroundingStatus.DIGEST_MISMATCH),
    ],
)
def test_observed_identity_and_digest_mismatches_return_existing_status(
    tmp_path: Path, image: str, expected: ImageGroundingStatus
) -> None:
    _write_compose(tmp_path, image)
    assert (
        composition.HomeAssistantImageGroundingService(tmp_path).ground().status
        is expected
    )


def test_release_mismatch_returns_existing_status(tmp_path: Path, monkeypatch) -> None:
    _write_compose(tmp_path)
    entry = _catalog_entry().model_copy(
        update={
            "release_claim": _catalog_entry().release_claim.model_copy(
                update={"version": "2026.8.4"}
            )
        }
    )
    _replace_catalog(monkeypatch, entry)
    assert (
        composition.HomeAssistantImageGroundingService(tmp_path).ground().status
        is ImageGroundingStatus.EVIDENCE_VERSION_MISMATCH
    )


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ((), ImageGroundingStatus.NO_IMAGE_RELEASE_EVIDENCE),
        (
            (_evidence(source_class=ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED),),
            ImageGroundingStatus.EVIDENCE_NOT_TRUSTED,
        ),
    ],
)
def test_unavailable_or_untrusted_evidence_cannot_ground(
    tmp_path: Path, monkeypatch, rows, expected: ImageGroundingStatus
) -> None:
    _write_compose(tmp_path)
    _replace_evidence(monkeypatch, *rows)
    assert (
        composition.HomeAssistantImageGroundingService(tmp_path).ground().status
        is expected
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("release_claim", ImageGroundingStatus.NO_STRICT_RELEASE_VERSION),
        ("deployment_binding", ImageGroundingStatus.NO_DEPLOYMENT_BINDING),
    ],
)
def test_missing_catalog_grounding_contract_returns_existing_status(
    tmp_path: Path, monkeypatch, field: str, expected: ImageGroundingStatus
) -> None:
    _replace_catalog(monkeypatch, _catalog_entry().model_copy(update={field: None}))
    assert (
        composition.HomeAssistantImageGroundingService(tmp_path).ground().status
        is expected
    )


def test_missing_catalog_item_fails_closed(tmp_path: Path, monkeypatch) -> None:
    _replace_catalog(monkeypatch, None)
    with pytest.raises(composition.HomeAssistantCatalogEntryNotFoundError):
        composition.HomeAssistantImageGroundingService(tmp_path).ground()


def test_complete_loader_corruption_and_conflict_propagate_before_observation(
    tmp_path: Path, monkeypatch
) -> None:
    class BrokenLoader:
        error: Exception

        def load(self):
            raise self.error

    monkeypatch.setattr(composition, "ImageReleaseEvidenceLoader", BrokenLoader)
    for error in (
        ImageReleaseEvidenceYamlError("corrupt"),
        ImageReleaseEvidenceConflictError("conflict"),
    ):
        BrokenLoader.error = error
        with pytest.raises(type(error)):
            composition.HomeAssistantImageGroundingService(tmp_path).ground()


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("services:\n  home-assistant:\n    image: ${HA_IMAGE}\n", "interpolation"),
        (
            f"services:\n  wrong-service:\n    image: {IMAGE}\n",
            "missing 'home-assistant'",
        ),
        ("services:\n  home-assistant:\n    command: noop\n", "image"),
    ],
)
def test_observation_failures_propagate(
    tmp_path: Path, content: str, match: str
) -> None:
    target = tmp_path / "compose/home-assistant.yaml"
    target.parent.mkdir()
    target.write_text(content, encoding="utf-8")
    with pytest.raises(RepositoryComposeObservationError, match=match):
        composition.HomeAssistantImageGroundingService(tmp_path).ground()


def test_invalid_or_missing_repository_root_fails_through_p1c(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="Repository root"):
        composition.HomeAssistantImageGroundingService(Path("relative")).ground()
    with pytest.raises(Exception, match="Repository root"):
        composition.HomeAssistantImageGroundingService(tmp_path / "missing").ground()
