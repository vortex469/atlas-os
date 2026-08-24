from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from app.discovery import home_assistant_registry_attested as integration
from app.discovery import home_assistant_sigstore_verifier as verifier
from app.discovery.image_release_evidence_loader import ImageReleaseEvidenceLoader
from app.discovery.models import ImageReleaseEvidenceSourceClass

_DISCOVERY_DIR = Path(__file__).parent
_FIXTURE = _DISCOVERY_DIR / "testdata/home_assistant_sigstore/ha-2026.8.3-bundle.json"
_TRUST_ROOT = _DISCOVERY_DIR / "trust/sigstore-production-trusted-root.json"
_FIXTURE_SHA256 = "733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520"
_TRUST_ROOT_SHA256 = "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66"
_SOURCE_ID = "collector:home-assistant-ghcr-cosign"


def test_reviewed_sigstore_proof_reproduces_promoted_evidence_row() -> None:
    fixture_bytes = _FIXTURE.read_bytes()
    trust_root_bytes = _TRUST_ROOT.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == _FIXTURE_SHA256
    assert hashlib.sha256(trust_root_bytes).hexdigest() == _TRUST_ROOT_SHA256

    verified = verifier.verify_home_assistant_2026_8_3_bundle(
        bundle_bytes=fixture_bytes
    )
    loaded = ImageReleaseEvidenceLoader().load()
    matching_rows = [row for row in loaded.rows if row.source_id == _SOURCE_ID]
    assert len(matching_rows) == 1
    row = matching_rows[0]

    assert row.catalog_item_id == integration._CATALOG_ITEM_ID == "home-assistant"
    assert row.release_version == verified.release_version == "2026.8.3"
    assert (
        row.image_reference
        == integration._IMAGE_REFERENCE
        == "ghcr.io/home-assistant/home-assistant"
    )
    assert row.image_digest == verified.image_digest == integration._EXPECTED_DIGEST
    assert row.source_class is ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED
    assert row.source_id == integration._SOURCE_ID == _SOURCE_ID
    assert (
        row.attested_at
        == verified.integrated_at
        == datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC)
    )

    assert verified.authenticated_ref == verifier._REF == "refs/tags/2026.8.3"
    assert verified.authenticated_repository == "home-assistant/core"
    assert verified.authenticated_workflow_identity == verifier._IDENTITY
    assert verified.authenticated_workflow_name == "Build images"
    assert verified.source_commit_sha == "759e4658f40b3ccb671d418b8a0ed95224bf4561"
