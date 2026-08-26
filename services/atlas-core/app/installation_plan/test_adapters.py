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
    _bounded_relative_regular_bytes,
    adapt_raw_evidence_record,
    adapt_released_evidence,
)
from app.installation_plan.assembly import (
    InstallationPlanSourceUnavailable,
    default_installation_plan_dependency,
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


def test_descriptor_relative_read_accepts_exact_bound_and_short_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "nested"
    directory.mkdir()
    (directory / "x").write_bytes(b"abcdef")
    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, size: real_read(fd, min(size, 2)))
    assert _bounded_relative_regular_bytes(tmp_path, "nested/x", 6) == b"abcdef"
    with pytest.raises(InstallationPlanAdapterError, match="content_size"):
        _bounded_relative_regular_bytes(tmp_path, "nested/x", 5)


@pytest.mark.parametrize(
    "shape", ["intermediate_symlink", "final_symlink", "non_directory", "directory"]
)
def test_descriptor_relative_traversal_rejects_unsafe_shapes(
    tmp_path: Path, shape: str
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x").write_bytes(b"abc")
    if shape == "intermediate_symlink":
        (tmp_path / "parent").symlink_to(outside, target_is_directory=True)
        relative = "parent/x"
    elif shape == "final_symlink":
        (tmp_path / "x").symlink_to(outside / "x")
        relative = "x"
    elif shape == "non_directory":
        (tmp_path / "parent").write_bytes(b"abc")
        relative = "parent/x"
    else:
        (tmp_path / "x").mkdir()
        relative = "x"
    with pytest.raises(InstallationPlanAdapterError, match="symlink|non_regular"):
        _bounded_relative_regular_bytes(tmp_path, relative, 3)


@pytest.mark.parametrize("mutation", ["truncate", "extend"])
def test_descriptor_relative_size_mutation_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    target = tmp_path / "x"
    target.write_bytes(b"abcdef")
    real_read = os.read
    changed = False

    def hostile_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, min(size, 2))
        if chunk and not changed:
            changed = True
            if mutation == "truncate":
                target.write_bytes(b"a")
            else:
                target.write_bytes(b"abcdefg")
        return chunk

    monkeypatch.setattr(os, "read", hostile_read)
    with pytest.raises(InstallationPlanAdapterError, match="changed"):
        _bounded_relative_regular_bytes(tmp_path, "x", 7)


def test_parent_detached_before_final_open_uses_opened_chain_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "x").write_bytes(b"OLD")
    real_open = os.open
    replaced = False

    def hostile_open(path: object, *args: object, **kwargs: object) -> int:
        nonlocal replaced
        if path == "x" and kwargs.get("dir_fd") is not None and not replaced:
            replaced = True
            parent.rename(tmp_path / "detached")
            parent.mkdir()
            (parent / "x").write_bytes(b"NEW")
            # The final open remains relative to the already-selected parent.
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", hostile_open)
    assert _bounded_relative_regular_bytes(tmp_path, "parent/x", 3) == b"OLD"
    assert (tmp_path / "parent" / "x").read_bytes() == b"NEW"


@pytest.mark.parametrize("replacement_bytes", [b"NEWNEW", b"OLDOLD"])
def test_namespace_replacement_after_linearization_returns_opened_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement_bytes: bytes
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "x").write_bytes(b"OLDOLD")
    real_read = os.read
    replaced = False

    def hostile_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        chunk = real_read(descriptor, min(size, 2))
        if chunk and not replaced:
            replaced = True
            parent.rename(tmp_path / "detached")
            parent.mkdir()
            (parent / "x").write_bytes(replacement_bytes)
        return chunk

    monkeypatch.setattr(os, "read", hostile_read)
    assert _bounded_relative_regular_bytes(tmp_path, "parent/x", 6) == b"OLDOLD"
    assert (tmp_path / "parent" / "x").read_bytes() == replacement_bytes


def test_final_file_replaced_before_linearization_selects_new_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "x"
    target.write_bytes(b"OLD")
    real_open = os.open
    replaced = False

    def hostile_open(path: object, *args: object, **kwargs: object) -> int:
        nonlocal replaced
        if path == "x" and kwargs.get("dir_fd") is not None and not replaced:
            replaced = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"NEW")
            replacement.replace(target)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", hostile_open)
    assert _bounded_relative_regular_bytes(tmp_path, "x", 3) == b"NEW"
    assert target.read_bytes() == b"NEW"


@pytest.mark.parametrize("mutation", ["metadata", "truncate", "extend"])
def test_opened_file_mutation_during_short_read_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    target = parent / "x"
    target.write_bytes(b"OLDOLD")
    real_read = os.read
    reads = 0
    changed = False

    def hostile_read(descriptor: int, size: int) -> bytes:
        nonlocal reads, changed
        chunk = real_read(descriptor, min(size, 2))
        reads += 1
        if reads == 1 and chunk and not changed:
            changed = True
            if mutation == "metadata":
                info = target.stat()
                os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns + 1))
            elif mutation == "truncate":
                target.write_bytes(b"O")
            else:
                target.write_bytes(b"OLDOLDX")
        return chunk

    monkeypatch.setattr(os, "read", hostile_read)
    with pytest.raises(InstallationPlanAdapterError, match="changed|content_size"):
        _bounded_relative_regular_bytes(tmp_path, "parent/x", 6)
    assert changed


@pytest.mark.parametrize("succeeds", [True, False])
def test_relative_read_closes_every_opened_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, succeeds: bool
) -> None:
    target = tmp_path / "x"
    target.write_bytes(b"abc" if succeeds else b"abcd")
    real_open = os.open
    real_close = os.close
    opened: set[int] = set()

    def tracking_open(*args: object, **kwargs: object) -> int:
        descriptor = real_open(*args, **kwargs)
        opened.add(descriptor)
        return descriptor

    def tracking_close(descriptor: int) -> None:
        real_close(descriptor)
        opened.discard(descriptor)

    monkeypatch.setattr(os, "open", tracking_open)
    monkeypatch.setattr(os, "close", tracking_close)
    if succeeds:
        assert _bounded_relative_regular_bytes(tmp_path, "x", 3) == b"abc"
    else:
        with pytest.raises(InstallationPlanAdapterError, match="content_size"):
            _bounded_relative_regular_bytes(tmp_path, "x", 3)
    assert opened == set()


@pytest.mark.parametrize("mutation", ["replace", "metadata"])
def test_catalog_read_fails_closed_on_opened_file_uncertainty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    source = (
        Path(__file__).parents[1]
        / "discovery"
        / "catalog"
        / "applications"
        / "home-assistant.yaml"
    )
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()
    target = catalog_root / "d5.yaml"
    target.write_bytes(source.read_bytes())
    real_read = os.read
    changed = False

    def hostile_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, min(size, 32))
        if chunk and not changed:
            changed = True
            if mutation == "replace":
                replacement = catalog_root / "replacement.yaml"
                replacement.write_bytes(target.read_bytes())
                replacement.replace(target)
                opened = os.fstat(descriptor)
                os.utime(
                    descriptor,
                    ns=(opened.st_atime_ns, opened.st_mtime_ns + 1),
                )
            else:
                os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 1))
        return chunk

    monkeypatch.setattr(os, "read", hostile_read)
    dependency = default_installation_plan_dependency(
        repository_root=tmp_path,
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
    )
    dependency._catalog = CatalogAdapter(catalog_root)  # type: ignore[assignment]
    with pytest.raises(InstallationPlanSourceUnavailable) as caught:
        dependency.assemble("home-assistant")
    assert str(caught.value) == "installation plan required source unavailable"


def test_catalog_parent_replacement_after_open_keeps_linearized_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        Path(__file__).parents[1]
        / "discovery"
        / "catalog"
        / "applications"
        / "home-assistant.yaml"
    )
    catalog_root = tmp_path / "catalog"
    applications = catalog_root / "applications"
    applications.mkdir(parents=True)
    target = applications / "home-assistant.yaml"
    target.write_bytes(source.read_bytes())
    real_read = os.read
    replaced = False

    def hostile_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        chunk = real_read(descriptor, min(size, 32))
        if chunk and not replaced:
            replaced = True
            applications.rename(catalog_root / "detached")
            applications.mkdir()
            (applications / "home-assistant.yaml").write_bytes(source.read_bytes())
        return chunk

    monkeypatch.setattr(os, "read", hostile_read)
    assert CatalogAdapter(catalog_root).read("home-assistant").selected.entry.item.id == (
        "home-assistant"
    )


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
