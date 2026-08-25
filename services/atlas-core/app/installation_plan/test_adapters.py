from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.discovery.models import ImageReleaseEvidence
from app.installation_plan.adapters import (
    CatalogAdapter,
    InstallationPlanAdapterError,
    RepositoryArtifactAdapter,
    _bounded_regular_bytes,
    adapt_raw_evidence_record,
    adapt_released_evidence,
)


def test_catalog_exact_home_assistant_digest_and_uniqueness() -> None:
    snapshot = CatalogAdapter().read("home-assistant")
    assert snapshot.selected.entry.provenance.entry_id == "d5-home-assistant"
    assert snapshot.selected.reviewed_content_digest.startswith("sha256:")
    assert (
        len([r for r in snapshot.records if r.entry.item.id == "home-assistant"]) == 1
    )


def test_bounded_read_short_reads_and_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "x"
    path.write_bytes(b"abcdef")
    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, size: real_read(fd, min(size, 2)))
    assert _bounded_regular_bytes(path, 6) == b"abcdef"
    with pytest.raises(InstallationPlanAdapterError, match="content_size"):
        _bounded_regular_bytes(path, 5)


@pytest.mark.parametrize(
    ("content", "state", "reason"),
    [
        (b"\xff", "invalid", "non_utf8"),
        (b"[", "invalid", "invalid_yaml"),
        (b"services: {}", "invalid", "ambiguous_service"),
    ],
)
def test_artifact_rejections(
    tmp_path: Path, content: bytes, state: str, reason: str
) -> None:
    snapshot = CatalogAdapter().read("home-assistant")
    target = tmp_path / "compose" / "home-assistant.yaml"
    target.parent.mkdir()
    target.write_bytes(content)
    observation = RepositoryArtifactAdapter(tmp_path).observe(snapshot.selected.entry)
    assert (observation.state, observation.reason_code) == (state, reason)


def test_artifact_missing_and_component_symlink(tmp_path: Path) -> None:
    entry = CatalogAdapter().read("home-assistant").selected.entry
    assert RepositoryArtifactAdapter(tmp_path).observe(entry).state == "missing"
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "compose").symlink_to(outside, target_is_directory=True)
    result = RepositoryArtifactAdapter(tmp_path).observe(entry)
    assert (result.state, result.reason_code) == ("unsafe", "symlink")


@pytest.mark.parametrize(
    ("payload", "kind"),
    [
        (None, "absent"),
        (b"[", "parse_failure"),
        (b"[]", "schema_failure"),
        (b"source_class: future\nsource_id: ok", "unsupported_source_class"),
        (b"source_class: curated", "missing_required_field"),
    ],
)
def test_raw_evidence_classification(payload: bytes | None, kind: str) -> None:
    assert (
        adapt_raw_evidence_record(
            payload, expected_source_id="expected"
        ).observation_kind
        == kind
    )


def test_optional_unavailable() -> None:
    assert (
        adapt_raw_evidence_record(
            None, expected_source_id="expected", source_unavailable=True
        ).observation_kind
        == "source_unavailable"
    )


def test_missing_source_class_is_missing_required_field() -> None:
    payload = b'catalog_item_id: home-assistant\nrelease_version: 2026.8.3\nimage_reference: ghcr.io/home-assistant/home-assistant\nimage_digest: sha256:1111111111111111111111111111111111111111111111111111111111111111\nsource_id: ghcr\nattested_at: "2026-08-25T00:00:00Z"\n'
    assert (
        adapt_raw_evidence_record(payload, expected_source_id="expected").observation_kind
        == "missing_required_field"
    )


@pytest.mark.parametrize(
    ("yaml_value", "kind"),
    [
        ("7", "unsupported_source_class"),
        ("[registry_attested]", "schema_failure"),
        ("{kind: registry_attested}", "schema_failure"),
        ("true", "unsupported_source_class"),
        ("null", "unsupported_source_class"),
        ("future_attestation", "unsupported_source_class"),
    ],
)
def test_malformed_source_class_totality(yaml_value: str, kind: str) -> None:
    payload = (
        "catalog_item_id: home-assistant\nrelease_version: 2026.8.3\n"
        "image_reference: ghcr.io/home-assistant/home-assistant\n"
        f"image_digest: sha256:{'1' * 64}\nsource_class: {yaml_value}\n"
        "source_id: collector\nattested_at: 2026-08-21T20:54:36Z\n"
    ).encode()
    result = adapt_raw_evidence_record(payload, expected_source_id="expected")
    assert result.observation_kind == kind


@pytest.mark.parametrize(
    ("replacement", "kind"),
    [
        (b"", "present"),
        (b"attested_at: yesterday\n", "malformed_timestamp"),
        (b"source_id: INVALID VALUE\n", "malformed_identity"),
        (b"image_digest: sha256:nope\n", "malformed_digest"),
        (b"source_class: [7]\n", "schema_failure"),
        (b"unexpected: value\n", "schema_failure"),
    ],
)
def test_raw_evidence_total_cross_field_table(replacement: bytes, kind: str) -> None:
    fields = {
        b"catalog_item_id": b"home-assistant",
        b"release_version": b"2026.8.3",
        b"image_reference": b"ghcr.io/home-assistant/home-assistant",
        b"image_digest": b"sha256:" + b"1" * 64,
        b"source_class": b"registry_attested",
        b"source_id": b"collector:home-assistant-ghcr-cosign",
        b"attested_at": b"2026-08-21T20:54:36Z",
    }
    if replacement:
        key, value = replacement.rstrip(b"\n").split(b": ", 1)
        if key == b"unexpected":
            fields[key] = value
        else:
            fields[key] = value
    payload = b"".join(key + b": " + value + b"\n" for key, value in fields.items())
    result = adapt_raw_evidence_record(payload, expected_source_id="expected")
    assert result.observation_kind == kind


def test_released_evidence_always_serializes_utc() -> None:
    row = ImageReleaseEvidence(
        catalog_item_id="home-assistant",
        release_version="2026.8.3",
        image_reference="ghcr.io/home-assistant/home-assistant",
        image_digest="sha256:" + "1" * 64,
        source_class="registry_attested",
        source_id="ghcr",
        attested_at=datetime(2026, 8, 25, 2, tzinfo=timezone(timedelta(hours=2))),
    )
    assert adapt_released_evidence(row).attested_at == "2026-08-25T00:00:00Z"
