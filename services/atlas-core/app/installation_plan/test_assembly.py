from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.installation_plan.adapters import (
    CatalogAdapter,
    InstallationPlanAdapterError,
    RepositoryArtifactAdapter,
)
from app.installation_plan.assembly import (
    BoundedReleasedEvidenceSource,
    InstallationPlanClockUnavailable,
    InstallationPlanItemNotFound,
    InstallationPlanReadDependency,
    InstallationPlanSourceUnavailable,
    ReleasedEvidenceRecordSource,
    default_installation_plan_dependency,
)

FIXED = datetime(2026, 8, 25, tzinfo=UTC)
EVIDENCE = (
    b"catalog_item_id: home-assistant\n"
    b"release_version: 2026.8.3\n"
    b"image_reference: ghcr.io/home-assistant/home-assistant\n"
    b"image_digest: sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe\n"
    b"source_class: registry_attested\n"
    b"source_id: collector:home-assistant-ghcr-cosign\n"
    b"attested_at: 2026-08-21T20:54:36Z\n"
)


def _source(
    root: Path, *, maximum: int = 1024 * 1024, required: bool = False
) -> BoundedReleasedEvidenceSource:
    return BoundedReleasedEvidenceSource(
        root,
        (
            ReleasedEvidenceRecordSource(
                "home-assistant", "record.yaml", "expected", required
            ),
        ),
        max_bytes=maximum,
    )


def _dependency(
    tmp_path: Path, clock=lambda: FIXED
) -> InstallationPlanReadDependency:
    return InstallationPlanReadDependency(
        catalog=CatalogAdapter(),
        repository=RepositoryArtifactAdapter(tmp_path),
        evidence=BoundedReleasedEvidenceSource(tmp_path, ()),
        clock=clock,
    )


def test_home_assistant_fixed_clock_complete_p3a_behavior(tmp_path: Path) -> None:
    plan = default_installation_plan_dependency(
        repository_root=tmp_path, clock=lambda: FIXED
    ).assemble("home-assistant")
    assert plan.fingerprint.value == (
        "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"
    )
    assert plan.status == "missing_deployment_artifact"
    assert plan.deployment_artifact.repository_path == "compose/home-assistant.yaml"
    assert plan.deployment_artifact.state == "missing"
    assert plan.image.model_dump() == {
        "state": "missing",
        "reference": None,
        "digest": None,
        "release_version": "2026.8.3",
    }
    assert len(plan.accepted_evidence) == 1
    assert len(plan.compatibility) == 1
    assert plan.compatibility[0].model_dump() == {
        "environment": "item-scoped",
        "result": "unknown",
        "reason_code": "compatibility_fact_missing",
    }


def test_complete_catalog_and_unknown_item_are_preserved(tmp_path: Path) -> None:
    dep = _dependency(tmp_path)
    with pytest.raises(InstallationPlanItemNotFound) as caught:
        dep.assemble("does-not-exist")
    assert str(caught.value) == "installation plan item not found"


def test_evidence_exact_bound_and_bound_plus_one(tmp_path: Path) -> None:
    target = tmp_path / "record.yaml"
    target.write_bytes(EVIDENCE)
    assert _source(tmp_path, maximum=len(EVIDENCE)).observe("home-assistant")[0].observation_kind == "present"
    target.write_bytes(EVIDENCE + b"x")
    with pytest.raises(InstallationPlanAdapterError):
        _source(tmp_path, maximum=len(EVIDENCE)).observe("home-assistant")


def test_evidence_short_reads_are_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "record.yaml").write_bytes(EVIDENCE)
    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, size: real_read(fd, min(size, 3)))
    assert _source(tmp_path).observe("home-assistant")[0].observation_kind == "present"


def test_evidence_early_eof_is_uncertain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "record.yaml").write_bytes(EVIDENCE)
    monkeypatch.setattr(os, "read", lambda _fd, _size: b"")
    with pytest.raises(InstallationPlanAdapterError):
        _source(tmp_path).observe("home-assistant")


def test_evidence_change_during_read_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "record.yaml"
    target.write_bytes(EVIDENCE)
    real_read = os.read
    changed = False

    def read_then_change(fd: int, size: int):
        nonlocal changed
        result = real_read(fd, size)
        if result and not changed:
            changed = True
            info = target.stat()
            os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
        return result

    monkeypatch.setattr(os, "read", read_then_change)
    with pytest.raises(InstallationPlanAdapterError):
        _source(tmp_path).observe("home-assistant")


def test_evidence_path_replacement_after_open_keeps_linearized_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "record.yaml"
    replacement = tmp_path / "replacement.yaml"
    target.write_bytes(EVIDENCE)
    replacement.write_bytes(EVIDENCE)
    real_read = os.read
    replaced = False

    def read_then_replace(fd: int, size: int):
        nonlocal replaced
        result = real_read(fd, size)
        if result and not replaced:
            replaced = True
            replacement.replace(target)
        return result

    monkeypatch.setattr(os, "read", read_then_replace)
    observations = _source(tmp_path).observe("home-assistant")
    assert len(observations) == 1
    assert observations[0].observation_kind == "present"


def test_evidence_symlink_nonregular_and_containment_fail_closed(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_bytes(EVIDENCE)
    (tmp_path / "record.yaml").symlink_to(outside)
    with pytest.raises(InstallationPlanAdapterError):
        _source(tmp_path).observe("home-assistant")
    (tmp_path / "record.yaml").unlink()
    (tmp_path / "record.yaml").mkdir()
    with pytest.raises(InstallationPlanAdapterError):
        _source(tmp_path).observe("home-assistant")
    with pytest.raises(ValueError, match="invalid evidence source configuration"):
        BoundedReleasedEvidenceSource(
            tmp_path,
            (ReleasedEvidenceRecordSource("home-assistant", "../outside.yaml", "x"),),
        )


def test_optional_missing_unavailable_and_malformed_are_classified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _source(tmp_path).observe("home-assistant")[0].observation_kind == "absent"
    target = tmp_path / "record.yaml"
    target.write_bytes(b"[")
    assert _source(tmp_path).observe("home-assistant")[0].observation_kind == "parse_failure"
    real_open = os.open

    def unavailable(path: object, flags: int, *args: object, **kwargs: object):
        if path == "record.yaml":
            raise OSError(5, "hidden")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", unavailable)
    assert _source(tmp_path).observe("home-assistant")[0].observation_kind == "source_unavailable"
    with pytest.raises(InstallationPlanAdapterError):
        _source(tmp_path, required=True).observe("home-assistant")


def test_evidence_cardinality_maximum_and_overflow(tmp_path: Path) -> None:
    records = tuple(
        ReleasedEvidenceRecordSource("home-assistant", f"{i}.yaml", f"source:{i}")
        for i in range(128)
    )
    assert len(BoundedReleasedEvidenceSource(tmp_path, records).observe("home-assistant")) == 128
    with pytest.raises(InstallationPlanAdapterError, match="cardinality"):
        BoundedReleasedEvidenceSource(
            tmp_path,
            records + (ReleasedEvidenceRecordSource("home-assistant", "x.yaml", "x"),),
        ).observe("home-assistant")


def test_clock_once_utc_determinism_and_cannot_be_overridden(tmp_path: Path) -> None:
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return FIXED

    dep = _dependency(tmp_path, clock)
    first = dep.assemble("home-assistant")
    assert calls == 1
    second = dep.assemble("home-assistant")
    assert calls == 2
    assert first == second
    with pytest.raises(TypeError):
        dep.assemble("home-assistant", evaluation_instant=FIXED)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "clock",
    [
        lambda: (_ for _ in ()).throw(RuntimeError("secret")),
        lambda: datetime(2026, 8, 25),  # noqa: DTZ001 - hostile naive clock
        lambda: FIXED.replace(microsecond=1),
        lambda: FIXED.astimezone(timezone(timedelta(hours=1))),
        lambda: "2026-08-25T00:00:00Z",
    ],
)
def test_invalid_or_unavailable_clock_is_sanitized(tmp_path: Path, clock) -> None:
    with pytest.raises(InstallationPlanClockUnavailable) as caught:
        _dependency(tmp_path, clock).assemble("home-assistant")
    assert str(caught.value) == "installation plan clock unavailable"


def test_required_source_failure_is_sanitized(tmp_path: Path) -> None:
    dep = InstallationPlanReadDependency(
        catalog=CatalogAdapter(),
        repository=RepositoryArtifactAdapter(tmp_path),
        evidence=_source(tmp_path, required=True),
        clock=lambda: FIXED,
    )
    with pytest.raises(InstallationPlanSourceUnavailable) as caught:
        dep.assemble("home-assistant")
    assert str(caught.value) == "installation plan required source unavailable"
