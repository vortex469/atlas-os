from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.discovery.exceptions import RepositoryComposeObservationError
from app.discovery.image_grounding import ImageGroundingStatus
from app.discovery.loader import LoadedCatalog, YamlCatalogLoader
from app.discovery.models import (
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)
from app.services import home_assistant_image_grounding
from app.services import image_grounding_read_model as read_model

ITEM_ID = "home-assistant"
VERSION = "2026.8.3"
REFERENCE = "ghcr.io/home-assistant/home-assistant"
DIGEST = "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"
IMAGE = f"{REFERENCE}@{DIGEST}"


def _catalog_entry(item_id: str = ITEM_ID):
    return next(
        entry
        for entry in YamlCatalogLoader().load().entries
        if entry.item.id == item_id
    )


def _write_compose(root: Path, image: str = IMAGE) -> None:
    target = root / "compose/home-assistant.yaml"
    target.parent.mkdir()
    target.write_text(
        f"services:\n  home-assistant:\n    image: {image}\n",
        encoding="utf-8",
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


def _replace_catalog(monkeypatch, *entries) -> None:
    class Loader:
        def load(self):
            return LoadedCatalog(entries=tuple(entries))

    monkeypatch.setattr(read_model, "YamlCatalogLoader", Loader)


def _replace_evidence(monkeypatch, *rows: ImageReleaseEvidence) -> None:
    class Loader:
        def load(self):
            return SimpleNamespace(rows=tuple(rows))

    monkeypatch.setattr(read_model, "ImageReleaseEvidenceLoader", Loader)


def test_home_assistant_success_is_equivalent_to_existing_composition(
    tmp_path: Path,
) -> None:
    _write_compose(tmp_path)

    existing = home_assistant_image_grounding.HomeAssistantImageGroundingService(
        tmp_path
    ).ground()
    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding == existing
    assert result.grounding.status is ImageGroundingStatus.GROUNDED
    assert result.repository_observation is not None
    assert result.repository_observation.image == IMAGE
    assert len(result.image_release_evidence) == 1
    source = result.image_release_evidence[0]
    assert source.source_class is ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED
    assert source.source_id == "collector:home-assistant-ghcr-cosign"
    assert result.catalog_provenance.source == "atlas-curated-discovery-catalog"


def test_item_without_deployment_binding_fails_closed(tmp_path: Path) -> None:
    result = read_model.BindingDrivenImageGroundingService(tmp_path).get("frigate")

    assert result.grounding.status is ImageGroundingStatus.NO_DEPLOYMENT_BINDING
    assert result.repository_observation is None
    assert result.image_release_evidence == ()


def test_unknown_catalog_item_has_bounded_local_failure(tmp_path: Path) -> None:
    with pytest.raises(read_model.ImageGroundingReadError) as caught:
        read_model.BindingDrivenImageGroundingService(tmp_path).get("not-cataloged")

    assert (
        caught.value.failure
        is read_model.ImageGroundingReadFailure.CATALOG_ITEM_NOT_FOUND
    )
    assert caught.value.catalog_item_id == "not-cataloged"


def test_bound_item_with_missing_compose_artifact_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        RepositoryComposeObservationError, match="directory|Compose file"
    ):
        read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)


def test_missing_accepted_evidence_fails_closed(tmp_path: Path, monkeypatch) -> None:
    _write_compose(tmp_path)
    _replace_evidence(monkeypatch)

    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding.status is ImageGroundingStatus.NO_IMAGE_RELEASE_EVIDENCE


def test_conflicting_accepted_evidence_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    _write_compose(tmp_path)
    _replace_evidence(
        monkeypatch,
        _evidence(source_id="accepted-a"),
        _evidence(image_digest=f"sha256:{'0' * 64}", source_id="accepted-b"),
    )

    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding.status is ImageGroundingStatus.CONFLICTED
    assert {row.source_id for row in result.image_release_evidence} == {
        "accepted-a",
        "accepted-b",
    }


@pytest.mark.parametrize(
    ("image", "status"),
    [
        (
            f"ghcr.io/example/home-assistant@{DIGEST}",
            ImageGroundingStatus.REPOSITORY_IDENTITY_MISMATCH,
        ),
        (f"{REFERENCE}@sha256:{'0' * 64}", ImageGroundingStatus.DIGEST_MISMATCH),
    ],
)
def test_repository_and_digest_mismatches_fail_closed(
    tmp_path: Path, image: str, status: ImageGroundingStatus
) -> None:
    _write_compose(tmp_path, image)

    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding.status is status


def test_release_mismatch_fails_closed(tmp_path: Path, monkeypatch) -> None:
    _write_compose(tmp_path)
    entry = _catalog_entry()
    _replace_catalog(
        monkeypatch,
        entry.model_copy(
            update={
                "release_claim": entry.release_claim.model_copy(
                    update={"version": "2026.8.4"}
                )
            }
        ),
    )

    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding.status is ImageGroundingStatus.EVIDENCE_VERSION_MISMATCH


def test_untrusted_evidence_cannot_produce_positive_grounding(
    tmp_path: Path, monkeypatch
) -> None:
    _write_compose(tmp_path)
    _replace_evidence(
        monkeypatch,
        _evidence(source_class=ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED),
    )

    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding.status is ImageGroundingStatus.EVIDENCE_NOT_TRUSTED
    assert (
        result.image_release_evidence[0].source_class
        is ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED
    )


def test_sources_are_preserved_without_silent_precedence(
    tmp_path: Path, monkeypatch
) -> None:
    _write_compose(tmp_path)
    rows = (
        _evidence(
            source_class=ImageReleaseEvidenceSourceClass.CURATED,
            source_id="curated-proof",
        ),
        _evidence(source_id="registry-proof"),
    )
    _replace_evidence(monkeypatch, *reversed(rows))

    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(ITEM_ID)

    assert result.grounding.status is ImageGroundingStatus.GROUNDED
    assert [
        (row.source_class, row.source_id) for row in result.image_release_evidence
    ] == [
        (ImageReleaseEvidenceSourceClass.CURATED, "curated-proof"),
        (ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED, "registry-proof"),
    ]


def test_repeated_evaluation_is_deterministic(tmp_path: Path) -> None:
    _write_compose(tmp_path)
    service = read_model.BindingDrivenImageGroundingService(tmp_path)

    first = service.get(ITEM_ID)
    second = service.get(ITEM_ID)

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
