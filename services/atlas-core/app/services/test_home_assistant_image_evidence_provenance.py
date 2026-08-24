from __future__ import annotations

import traceback
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.discovery import home_assistant_sigstore_verifier as verifier
from app.discovery.image_release_evidence_loader import LoadedImageReleaseEvidence
from app.discovery.models import (
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)
from app.services import home_assistant_image_evidence_provenance as provenance


def _row(**changes: object) -> ImageReleaseEvidence:
    values = {
        "catalog_item_id": "home-assistant",
        "release_version": "2026.8.3",
        "image_reference": "ghcr.io/home-assistant/home-assistant",
        "image_digest": "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe",
        "source_class": ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
        "source_id": "collector:home-assistant-ghcr-cosign",
        "attested_at": datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC),
    }
    values.update(changes)
    return ImageReleaseEvidence.model_validate(values)


def _replace_rows(monkeypatch: pytest.MonkeyPatch, *rows: ImageReleaseEvidence) -> None:
    monkeypatch.setattr(
        provenance.ImageReleaseEvidenceLoader,
        "load",
        lambda self: LoadedImageReleaseEvidence(rows=rows),
    )


def test_exact_successful_projection_and_deterministic_serialization() -> None:
    first = provenance.HomeAssistantImageEvidenceProvenanceService().get()
    second = provenance.HomeAssistantImageEvidenceProvenanceService().get()

    assert first == second
    assert first.model_dump(mode="json") == {
        "catalog_item_id": "home-assistant",
        "release_version": "2026.8.3",
        "image_reference": "ghcr.io/home-assistant/home-assistant",
        "image_digest": "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe",
        "source_class": "registry_attested",
        "source_id": "collector:home-assistant-ghcr-cosign",
        "attested_at": "2026-08-21T20:54:36Z",
        "verification_mechanism": "sigstore_bundle_v0_3",
        "verification_profile_id": "home-assistant-ghcr-cosign-2026.8.3-v1",
        "bundle_sha256": "733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520",
        "trust_root_sha256": "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66",
        "issuer": "https://token.actions.githubusercontent.com",
        "repository": "home-assistant/core",
        "workflow_identity": "https://github.com/home-assistant/core/.github/workflows/builder.yml@refs/tags/2026.8.3",
        "workflow_name": "Build images",
        "ref": "refs/tags/2026.8.3",
        "source_commit_sha": "759e4658f40b3ccb671d418b8a0ed95224bf4561",
        "reverification_state": "verified_current_profile",
    }
    assert first.source_class is ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED
    assert first.attested_at == datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC)


def test_profile_constants_match_offline_verifier_and_reviewed_hashes() -> None:
    assert (
        provenance._BUNDLE_SHA256
        == "733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520"
    )
    assert provenance._TRUST_ROOT_SHA256 == verifier._TRUSTED_ROOT_SHA256
    assert provenance._ISSUER == verifier._ISSUER
    assert provenance._REPOSITORY == verifier._REPOSITORY
    assert provenance._WORKFLOW_IDENTITY == verifier._IDENTITY
    assert provenance._WORKFLOW_NAME == verifier._WORKFLOW_NAME
    assert provenance._REF == verifier._REF
    assert provenance._SOURCE_COMMIT_SHA == verifier._WORKFLOW_SHA


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("catalog_item_id", "other"),
        ("release_version", "2026.8.4"),
        ("image_reference", "ghcr.io/example/home-assistant"),
        ("image_digest", "sha256:" + "0" * 64),
        ("source_class", ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED),
        ("source_id", "collector:other"),
        ("attested_at", datetime(2026, 8, 21, 20, 54, 37, tzinfo=UTC)),
    ],
)
def test_wrong_accepted_evidence_fails_closed(monkeypatch, field, value) -> None:
    _replace_rows(monkeypatch, _row(**{field: value}))
    with pytest.raises(provenance.HomeAssistantImageEvidenceProvenanceError):
        provenance.HomeAssistantImageEvidenceProvenanceService().get()


def test_missing_evidence_fails_closed(monkeypatch) -> None:
    _replace_rows(monkeypatch)
    with pytest.raises(provenance.HomeAssistantImageEvidenceProvenanceError):
        provenance.HomeAssistantImageEvidenceProvenanceService().get()


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("loader-secret-marker: /local/evidence.json is malformed"),
        RuntimeError("loader-secret-marker: conflicting private evidence"),
    ],
)
def test_corrupted_or_conflicting_loader_fails_with_stable_error(
    monkeypatch, failure
) -> None:
    def fail(self):
        raise failure

    monkeypatch.setattr(provenance.ImageReleaseEvidenceLoader, "load", fail)
    with pytest.raises(
        provenance.HomeAssistantImageEvidenceProvenanceError,
        match="accepted image evidence set could not be loaded",
    ) as caught:
        provenance.HomeAssistantImageEvidenceProvenanceService().get()
    assert str(caught.value) == "The accepted image evidence set could not be loaded."
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    rendered = "\n".join(
        (
            str(caught.value),
            repr(caught.value),
            "".join(
                traceback.format_exception(
                    type(caught.value), caught.value, caught.value.__traceback__
                )
            ),
        )
    )
    assert "loader-secret-marker" not in rendered


def test_profile_constant_drift_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(provenance, "_ISSUER", "https://issuer.invalid")
    with pytest.raises(provenance.HomeAssistantImageEvidenceProvenanceError):
        provenance.HomeAssistantImageEvidenceProvenanceService().get()


def test_projection_is_immutable() -> None:
    projected = provenance.HomeAssistantImageEvidenceProvenanceService().get()

    with pytest.raises(ValidationError):
        projected.source_id = "collector:other"
