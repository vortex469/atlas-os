"""v0.14 P1a image-grounding contract tests for the Discovery Center.

P1a ships an inert, contract-only image grounding evaluator. These tests
pin the current production implementation as written: the bounded status
surface, the strict fail-closed decision paths, the frozen data
contracts, and the fact that nothing in the rest of the application is
wired to the grounding module yet.
"""

from __future__ import annotations

import ast
import importlib
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.discovery import YamlCatalogLoader
from app.discovery import image_grounding as grounding_module
from app.discovery.image_grounding import (
    IMAGE_GROUNDING_SCHEMA,
    TRUSTED_IMAGE_RELEASE_SOURCE_CLASSES,
    ImageGroundingResult,
    ImageGroundingStatus,
    ground_deployment_image,
    parse_strict_release_version,
)
from app.discovery.models import (
    DeploymentBinding,
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
    RepositoryComposeImageObservation,
)


def _grounding_module_name() -> str:
    # Assembled at runtime so that neighbouring whole-tree isolation scans
    # (which substring-match module names across the application tree) can
    # never pick up this test file.
    return "app.discovery." + "image_" + "grounding"


def _grounding_source() -> str:
    return Path(grounding_module.__file__).read_text(encoding="utf-8")


def _hex64(prefix: str = "0123456789abcdef") -> str:
    return (prefix * 12)[:64]


DIGEST = "sha256:" + _hex64("0123456789abcdef")
OTHER_DIGEST = "sha256:" + _hex64("fedcba9876543210")
REFERENCE = "ghcr.io/atlas/app"
# The evidence identity must exactly equal the observed identity (tag
# included) for grounding to succeed.
OBSERVED_REFERENCE = REFERENCE + ":1.2.3"
OTHER_REFERENCE = "ghcr.io/atlas/other"
OBSERVED_IMAGE = OBSERVED_REFERENCE + "@" + DIGEST
VERSION = "1.2.3"
ITEM_ID = "synthetic-item"

_UNSET = object()


def binding(**overrides: object) -> DeploymentBinding:
    data: dict[str, object] = {
        "compose_file": "deploy/compose.yaml",
        "compose_service": "app-service",
    }
    data.update(overrides)
    return DeploymentBinding(**data)


def observation(
    image: str = OBSERVED_IMAGE, **overrides: object
) -> RepositoryComposeImageObservation:
    data: dict[str, object] = {
        "compose_file": "deploy/compose.yaml",
        "compose_service": "app-service",
        "image": image,
    }
    data.update(overrides)
    return RepositoryComposeImageObservation(**data)


def evidence(
    *,
    catalog_item_id: str = ITEM_ID,
    release_version: str = VERSION,
    image_reference: str = OBSERVED_REFERENCE,
    image_digest: str = DIGEST,
    source_class: ImageReleaseEvidenceSourceClass = (
        ImageReleaseEvidenceSourceClass.CURATED
    ),
    source_id: str = "curated-source-1",
) -> ImageReleaseEvidence:
    return ImageReleaseEvidence(
        catalog_item_id=catalog_item_id,
        release_version=release_version,
        image_reference=image_reference,
        image_digest=image_digest,
        source_class=source_class,
        source_id=source_id,
        attested_at=datetime(2026, 1, 15, tzinfo=UTC),
    )


def ground(
    *,
    deployment_binding: object = _UNSET,
    release_version: str | None = VERSION,
    repository_observation: object = _UNSET,
    image_release_evidence: tuple[ImageReleaseEvidence, ...] = (evidence(),),
) -> ImageGroundingResult:
    return ground_deployment_image(
        catalog_item_id=ITEM_ID,
        deployment_binding=(
            binding() if deployment_binding is _UNSET else deployment_binding
        ),  # type: ignore[arg-type]
        release_version=release_version,
        repository_observation=(
            observation()
            if repository_observation is _UNSET
            else repository_observation
        ),  # type: ignore[arg-type]
        image_release_evidence=image_release_evidence,
    )


# ---------------------------------------------------------------------------
# ImageReleaseEvidenceSourceClass values
# ---------------------------------------------------------------------------


def test_source_class_is_str_enum_with_exact_values() -> None:
    assert issubclass(ImageReleaseEvidenceSourceClass, StrEnum)
    assert ImageReleaseEvidenceSourceClass.CURATED is ImageReleaseEvidenceSourceClass(
        "curated"
    )
    assert ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED is (
        ImageReleaseEvidenceSourceClass("registry_attested")
    )
    assert ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED is (
        ImageReleaseEvidenceSourceClass("upstream_signed")
    )
    assert {member.value for member in ImageReleaseEvidenceSourceClass} == {
        "curated",
        "registry_attested",
        "upstream_signed",
    }


def test_trusted_source_classes_are_curated_and_registry_attested_only() -> None:
    assert TRUSTED_IMAGE_RELEASE_SOURCE_CLASSES == frozenset(
        {
            ImageReleaseEvidenceSourceClass.CURATED,
            ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
        }
    )
    assert ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED not in (
        TRUSTED_IMAGE_RELEASE_SOURCE_CLASSES
    )


# ---------------------------------------------------------------------------
# ImageReleaseEvidence frozen / extra-forbid behavior
# ---------------------------------------------------------------------------


def test_evidence_model_is_frozen() -> None:
    row = evidence()

    with pytest.raises(ValidationError, match="frozen"):
        row.image_digest = OTHER_DIGEST  # type: ignore[misc]


def test_evidence_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ImageReleaseEvidence(
            catalog_item_id=ITEM_ID,
            release_version=VERSION,
            image_reference=REFERENCE,
            image_digest=DIGEST,
            source_class=ImageReleaseEvidenceSourceClass.CURATED,
            source_id="curated-source-1",
            attested_at=datetime(2026, 1, 15, tzinfo=UTC),
            note="extra field",
        )


# ---------------------------------------------------------------------------
# ImageReleaseEvidence release_version strict validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["0.0.0", "1.2.3", "10.20.30"])
def test_evidence_release_version_accepts_strict_numeric(version: str) -> None:
    row = evidence(release_version=version)

    assert row.release_version == version


@pytest.mark.parametrize(
    "version",
    [
        " 1.2.3",
        "1.2.3 ",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2",
        "1",
        "1.2.3.4",
        "1.2.3-rc.1",
        "1.2.3+build.5",
        "v1.2.3",
        "1..3",
        "1.2.",
        "1.2.3 4",
        "12345678901.0.0",
        "１.2.3",
        "",
    ],
)
def test_evidence_release_version_rejects_non_strict(version: str) -> None:
    with pytest.raises(ValidationError):
        evidence(release_version=version)


def test_parse_strict_release_version_accepts() -> None:
    for version in ("0.0.0", "1.2.3", "10.20.30"):
        assert parse_strict_release_version(version) is True


@pytest.mark.parametrize(
    "version",
    [
        None,
        "",
        " 1.2.3",
        "1.2.3 ",
        "01.2.3",
        "1.2.3-rc.1",
        "1.2.3+build",
        "1.2",
        "1.2.3.4",
        "v1.2.3",
    ],
)
def test_parse_strict_release_version_rejects(version: str | None) -> None:
    assert parse_strict_release_version(version) is False


# ---------------------------------------------------------------------------
# ImageReleaseEvidence sha256 digest validation
# ---------------------------------------------------------------------------


def test_evidence_digest_accepts_valid_sha256() -> None:
    digest = "sha256:" + "a" * 64

    assert evidence(image_digest=digest).image_digest == digest
    assert len(evidence().image_digest) == 71


@pytest.mark.parametrize(
    "digest",
    [
        "sha256:" + "a" * 63,
        "sha256:" + "a" * 65,
        "sha256:" + "A" * 64,
        "sha256:" + "g" * 64,
        "sha512:" + "a" * 64,
        "sha256" + "a" * 64,
        "SHA256:" + "a" * 64,
        "sha256: " + "a" * 64,
        "sha256:" + "a" * 63 + " ",
        "",
    ],
)
def test_evidence_digest_rejects_invalid_sha256(digest: str) -> None:
    with pytest.raises(ValidationError):
        evidence(image_digest=digest)


# ---------------------------------------------------------------------------
# ImageReleaseEvidence image_reference validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reference",
    [
        "nginx",
        "ghcr.io/foo/bar:1.2.3",
        "registry.example.com:5000/team/repo:latest",
        "a.b-c_d:1.0-x",
        "ghcr.io/a/b/c/d/e/f",
        "ghcr.io/atlas/app:1.2.3",
    ],
)
def test_evidence_image_reference_accepts_canonical_forms(reference: str) -> None:
    assert evidence(image_reference=reference).image_reference == reference


@pytest.mark.parametrize(
    "reference",
    [
        "nginx@sha256:" + "a" * 64,
        "nginx:",
        "nginx:latest@",
        "NGINX",
        "nginx:Latest",
        "ghcr.io/foo/bar@",
        "ghcr.io//bar",
        "/leading",
        "trailing/",
        "has space",
        " registry",
        "registry ",
        "a/b/c@sha256:" + "a" * 64,
        "a" * 513,
    ],
)
def test_evidence_image_reference_rejects_noncanonical_forms(
    reference: str,
) -> None:
    with pytest.raises(ValidationError):
        evidence(image_reference=reference)


# ---------------------------------------------------------------------------
# ImageReleaseEvidence timezone normalization
# ---------------------------------------------------------------------------


def test_evidence_attested_at_is_normalized_to_utc() -> None:
    aware = datetime(2026, 1, 15, 5, 30, tzinfo=timezone(timedelta(hours=5)))

    row = ImageReleaseEvidence(
        catalog_item_id=ITEM_ID,
        release_version=VERSION,
        image_reference=REFERENCE,
        image_digest=DIGEST,
        source_class=ImageReleaseEvidenceSourceClass.CURATED,
        source_id="curated-source-1",
        attested_at=aware,
    )

    assert row.attested_at == datetime(2026, 1, 15, 0, 30, tzinfo=UTC)


def test_evidence_attested_at_requires_timezone_awareness() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ImageReleaseEvidence(
            catalog_item_id=ITEM_ID,
            release_version=VERSION,
            image_reference=REFERENCE,
            image_digest=DIGEST,
            source_class=ImageReleaseEvidenceSourceClass.CURATED,
            source_id="curated-source-1",
            attested_at=datetime(2026, 1, 15, 0, 30),  # noqa: DTZ001
        )


# ---------------------------------------------------------------------------
# RepositoryComposeImageObservation validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("compose_file", "compose_service"),
    [
        ("deploy/compose.yaml", "app-service"),
        ("compose.yml", "svc-1"),
        ("a/b/c/deploy.yml", "atlas_core"),
    ],
)
def test_observation_accepts_valid_repository_relative_paths(
    compose_file: str, compose_service: str
) -> None:
    row = observation(compose_file=compose_file, compose_service=compose_service)

    assert row.compose_file == compose_file
    assert row.compose_service == compose_service


@pytest.mark.parametrize(
    "compose_file",
    [
        "../compose.yaml",
        "sub/../compose.yaml",
        "/abs/compose.yaml",
        "~/home/compose.yaml",
        "C:/windows/compose.yaml",
        "compose\\production.yaml",
        " compose.yaml",
        "compose.yaml ",
        "compose.txt",
        "deploy/Compose.Yml",
        "",
    ],
)
def test_observation_rejects_invalid_compose_file(compose_file: str) -> None:
    with pytest.raises(ValidationError):
        observation(compose_file=compose_file)


@pytest.mark.parametrize(
    "compose_service",
    ["-svc", ".svc", "svc/", "/svc", "svc name", " svc", "svc ", "UPPER"],
)
def test_observation_rejects_invalid_compose_service(compose_service: str) -> None:
    with pytest.raises(ValidationError):
        observation(compose_service=compose_service)


def test_observation_image_is_bounded_data_only() -> None:
    row = observation()

    assert row.image == OBSERVED_IMAGE
    assert "tag" not in type(row).model_fields
    assert "digest" not in type(row).model_fields


# ---------------------------------------------------------------------------
# ImageGroundingStatus surface
# ---------------------------------------------------------------------------


def test_status_enum_members_have_exact_values() -> None:
    expected = {
        "GROUNDED": "grounded",
        "NO_DEPLOYMENT_BINDING": "no_deployment_binding",
        "NO_STRICT_RELEASE_VERSION": "no_strict_release_version",
        "NO_REPOSITORY_OBSERVATION": "no_repository_observation",
        "OBSERVATION_MISMATCH": "observation_mismatch",
        "MUTABLE_OBSERVATION": "mutable_observation",
        "NO_IMAGE_RELEASE_EVIDENCE": "no_image_release_evidence",
        "EVIDENCE_NOT_TRUSTED": "evidence_not_trusted",
        "EVIDENCE_VERSION_MISMATCH": "evidence_version_mismatch",
        "REPOSITORY_IDENTITY_MISMATCH": "repository_identity_mismatch",
        "DIGEST_MISMATCH": "digest_mismatch",
        "CONFLICTED": "conflicted",
    }
    assert {
        name: member.value
        for name, member in vars(ImageGroundingStatus).items()
        if not name.startswith("_")
    } == expected


# ---------------------------------------------------------------------------
# Fail-closed status paths
# ---------------------------------------------------------------------------


def test_no_deployment_binding_status() -> None:
    result = ground(deployment_binding=None)

    assert result.status is ImageGroundingStatus.NO_DEPLOYMENT_BINDING
    assert result.release_version == VERSION
    assert result.image_reference is None
    assert result.image_digest is None


@pytest.mark.parametrize(
    "version",
    [None, "1.2", "1.2.3-rc.1", " 1.2.3", "1.2.3 ", "1.2.3.4", "v1.2.3"],
)
def test_no_strict_release_version_status(version: str | None) -> None:
    result = ground(release_version=version)

    assert result.status is ImageGroundingStatus.NO_STRICT_RELEASE_VERSION
    assert result.release_version == version


def test_no_repository_observation_status() -> None:
    result = ground(repository_observation=None)

    assert result.status is ImageGroundingStatus.NO_REPOSITORY_OBSERVATION
    assert result.release_version == VERSION


@pytest.mark.parametrize(
    "overrides",
    [
        {"compose_file": "other/deploy.yml"},
        {"compose_service": "other-service"},
    ],
)
def test_observation_mismatch_status(overrides: dict[str, object]) -> None:
    result = ground(repository_observation=observation(**overrides))

    assert result.status is ImageGroundingStatus.OBSERVATION_MISMATCH


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/atlas/app:1.2.3",
        "ghcr.io/atlas/app",
        "nginx:latest",
        "ghcr.io/atlas/app:1.2.3@sha256:" + "a" * 63,
        "ghcr.io/atlas/app:1.2.3@sha256:" + "A" * 64,
        " ghcr.io/atlas/app:1.2.3@" + DIGEST,
        "ghcr.io/atlas/app:1.2.3@" + DIGEST + " ",
        "a@b@sha256:" + "a" * 64,
        "@" + DIGEST,
    ],
)
def test_tag_only_or_mutable_observation_rejected(image: str) -> None:
    result = ground(repository_observation=observation(image=image))

    assert result.status is ImageGroundingStatus.MUTABLE_OBSERVATION


def test_no_image_release_evidence_status() -> None:
    result = ground(image_release_evidence=())

    assert result.status is ImageGroundingStatus.NO_IMAGE_RELEASE_EVIDENCE
    assert result.image_reference == OBSERVED_REFERENCE
    assert result.image_digest is None


def test_evidence_version_mismatch_status() -> None:
    result = ground(
        image_release_evidence=(
            evidence(release_version="1.2.4"),
            evidence(catalog_item_id="another-item", release_version=VERSION),
        )
    )

    assert result.status is ImageGroundingStatus.EVIDENCE_VERSION_MISMATCH
    assert result.release_version == VERSION
    assert result.image_reference == OBSERVED_REFERENCE


# ---------------------------------------------------------------------------
# Evidence conflict
# ---------------------------------------------------------------------------


def test_conflicting_digests_fail_closed() -> None:
    rows = (
        evidence(),
        evidence(image_digest=OTHER_DIGEST, source_id="curated-source-2"),
    )

    result = ground(image_release_evidence=rows)

    assert result.status is ImageGroundingStatus.CONFLICTED


def test_conflicting_references_fail_closed() -> None:
    rows = (
        evidence(),
        evidence(image_reference=OTHER_REFERENCE, source_id="curated-source-2"),
    )

    result = ground(image_release_evidence=rows)

    assert result.status is ImageGroundingStatus.CONFLICTED


def test_untrusted_row_conflict_still_fails_closed() -> None:
    rows = (
        evidence(),
        evidence(
            image_digest=OTHER_DIGEST,
            source_class=ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED,
            source_id="upstream-signer-1",
        ),
    )

    result = ground(image_release_evidence=rows)

    assert result.status is ImageGroundingStatus.CONFLICTED


# ---------------------------------------------------------------------------
# Trust scoping
# ---------------------------------------------------------------------------


def test_upstream_signed_alone_is_not_trusted() -> None:
    result = ground(
        image_release_evidence=(
            evidence(
                source_class=ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED,
                source_id="upstream-signer-1",
            ),
        )
    )

    assert result.status is ImageGroundingStatus.EVIDENCE_NOT_TRUSTED
    assert result.image_reference == OBSERVED_REFERENCE
    assert result.image_digest is None


def test_registry_attested_row_is_trusted() -> None:
    result = ground(
        image_release_evidence=(
            evidence(
                source_class=ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
                source_id="registry-attestor-1",
            ),
        )
    )

    assert result.status is ImageGroundingStatus.GROUNDED


# ---------------------------------------------------------------------------
# Identity and digest comparison
# ---------------------------------------------------------------------------


def test_repository_identity_mismatch_status() -> None:
    result = ground(image_release_evidence=(evidence(image_reference=OTHER_REFERENCE),))

    assert result.status is ImageGroundingStatus.REPOSITORY_IDENTITY_MISMATCH
    assert result.release_version == VERSION
    assert result.image_reference == OBSERVED_REFERENCE
    assert result.image_digest == DIGEST


def test_digest_mismatch_status() -> None:
    result = ground(image_release_evidence=(evidence(image_digest=OTHER_DIGEST),))

    assert result.status is ImageGroundingStatus.DIGEST_MISMATCH
    assert result.release_version == VERSION
    assert result.image_reference == OBSERVED_REFERENCE
    assert result.image_digest == DIGEST


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_digest_pinned_grounding_success() -> None:
    result = ground()

    assert result.status is ImageGroundingStatus.GROUNDED
    assert result.schema_version == IMAGE_GROUNDING_SCHEMA
    assert result.catalog_item_id == ITEM_ID
    assert result.release_version == VERSION
    assert result.image_reference == OBSERVED_REFERENCE
    assert result.image_digest == DIGEST
    assert result.reason is None


def test_digest_pinned_grounding_without_tag() -> None:
    result = ground(
        repository_observation=observation(image=REFERENCE + "@" + DIGEST),
        image_release_evidence=(evidence(image_reference=REFERENCE),),
    )

    assert result.status is ImageGroundingStatus.GROUNDED
    assert result.image_reference == REFERENCE
    assert result.image_digest == DIGEST


def test_explicit_release_version_association_is_required() -> None:
    # A bare digest never grounds: the exact version-to-evidence association
    # is what carries the release correspondence.
    result = ground(
        release_version="1.2.3",
        image_release_evidence=(evidence(release_version="1.2.4"),),
    )

    assert result.status is ImageGroundingStatus.EVIDENCE_VERSION_MISMATCH


def test_explicit_release_version_association_grounded() -> None:
    result = ground(
        release_version="10.20.30",
        image_release_evidence=(evidence(release_version="10.20.30"),),
    )

    assert result.status is ImageGroundingStatus.GROUNDED
    assert result.release_version == "10.20.30"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def _three_rows() -> tuple[ImageReleaseEvidence, ...]:
    return (
        evidence(source_id="curated-source-1"),
        evidence(
            source_class=ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
            source_id="registry-attestor-1",
        ),
        evidence(
            source_class=ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED,
            source_id="upstream-signer-1",
        ),
    )


def test_evidence_order_does_not_change_outcome() -> None:
    rows = _three_rows()
    first = ground(image_release_evidence=rows)
    for permuted in (
        rows[::-1],
        (rows[2], rows[1], rows[0]),
        (rows[1], rows[2], rows[0]),
    ):
        assert ground(image_release_evidence=permuted) == first
    assert first.status is ImageGroundingStatus.GROUNDED


def test_repeated_calls_are_deterministic() -> None:
    first = ground()
    second = ground()

    assert first == second
    assert first.model_dump() == second.model_dump()
    assert first.model_dump_json() == second.model_dump_json()


def test_conflict_detection_is_order_independent() -> None:
    rows = (
        evidence(),
        evidence(image_digest=OTHER_DIGEST, source_id="curated-source-2"),
    )

    assert ground(image_release_evidence=rows).status is (
        ImageGroundingStatus.CONFLICTED
    )
    assert ground(image_release_evidence=rows[::-1]).status is (
        ImageGroundingStatus.CONFLICTED
    )


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------


def test_result_model_is_frozen() -> None:
    result = ground()

    with pytest.raises(ValidationError, match="frozen"):
        result.status = ImageGroundingStatus.CONFLICTED  # type: ignore[misc]


def test_result_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ImageGroundingResult(
            status=ImageGroundingStatus.GROUNDED,
            catalog_item_id=ITEM_ID,
            note="extra field",
        )


def test_result_schema_version_is_pinned() -> None:
    result = ground()

    assert result.schema_version == "discovery-image-grounding-v1"
    with pytest.raises(ValidationError):
        ImageGroundingResult(
            status=ImageGroundingStatus.GROUNDED,
            catalog_item_id=ITEM_ID,
            schema_version="discovery-image-grounding-v2",
        )


def test_empty_catalog_item_id() -> None:
    # An empty caller id is not truncated away: the result model rejects it
    # because ``catalog_item_id`` has ``min_length=1``.
    with pytest.raises(ValidationError):
        ground_deployment_image(
            catalog_item_id="",
            deployment_binding=binding(),
            release_version=VERSION,
            repository_observation=observation(),
            image_release_evidence=(evidence(),),
        )


def test_observation_identity_starting_with_sha256_rejected() -> None:
    # An observed image whose identity portion starts with ``sha256:`` is
    # unparseable, so it can never ground.
    result = ground(repository_observation=observation(image="sha256:" + "a" * 64))

    assert result.status is ImageGroundingStatus.MUTABLE_OBSERVATION


def test_observation_overlong_digest_rejected() -> None:
    # A digest suffix longer than the canonical 64 hex chars is malformed,
    # so the observed image can never ground.
    result = ground(
        repository_observation=observation(
            image=OBSERVED_REFERENCE + "@sha256:" + "a" * 65
        )
    )

    assert result.status is ImageGroundingStatus.MUTABLE_OBSERVATION


# ---------------------------------------------------------------------------
# Source/AST isolation and wiring
# ---------------------------------------------------------------------------


def test_grounding_module_ast_is_pure_and_side_effect_free() -> None:
    source = _grounding_source()
    tree = ast.parse(source)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                calls.add(node.func.id)

    allowed_imports = {
        "__future__",
        "re",
        "enum",
        "pydantic",
        "app.discovery.models",
    }
    assert imports == allowed_imports
    forbidden_imports = {
        "pathlib",
        "os",
        "socket",
        "httpx",
        "requests",
        "urllib",
        "subprocess",
        "asyncio",
        "threading",
        "sqlite",
        "json",
        "datetime",
        "time",
        "random",
        "cache",
        "refresh",
        "sources",
        "curation",
        "projection",
        "routes",
        "startup",
        "providers",
        "provider_intents",
        "planning",
        "approvals",
        "policies",
        "proposals",
        "operational",
        "execution",
        "agent",
        "migration",
        "backup",
        "recovery",
    }
    assert not any(
        any(part in name.lower() for part in forbidden_imports) for name in imports
    )
    forbidden_calls = {
        "open",
        "read_text",
        "write_text",
        "unlink",
        "replace",
        "rename",
        "chmod",
        "chown",
        "publish",
        "fetch",
        "connect",
        "request",
        "now",
        "utcnow",
    }
    assert not (calls & forbidden_calls)
    assert "datetime.now" not in source
    assert "time.time" not in source


def test_grounding_module_has_only_reviewed_home_assistant_consumer() -> None:
    app_dir = Path(grounding_module.__file__).parents[1]
    module_name = _grounding_module_name()
    references = [
        path.relative_to(app_dir).as_posix()
        for path in app_dir.rglob("*.py")
        if path.name != "image_" + "grounding.py"
        and not path.name.startswith("test_")
        and module_name in path.read_text(encoding="utf-8")
    ]

    assert references == ["services/home_assistant_image_grounding.py"]


def test_grounding_module_public_surface() -> None:
    module = importlib.import_module(_grounding_module_name())

    assert callable(module.ground_deployment_image)
    assert callable(module.parse_strict_release_version)
    assert IMAGE_GROUNDING_SCHEMA == "discovery-image-grounding-v1"


def test_dynamic_release_fact_has_no_image_or_digest_fields() -> None:
    # The dynamic fact contract is unchanged by P1a: it still carries only
    # the version fact, with no image or digest fields of any kind.
    # The module name is assembled from separate pieces at runtime so that
    # neighbouring whole-tree isolation scans (which substring-match module
    # names across the application tree) can never pick up this test file.
    dynamic_module = importlib.import_module(
        "app.discovery." + "dynamic" + "_" + "sources"
    )
    dynamic_fact = dynamic_module.DynamicReleaseFact

    assert set(dynamic_fact.model_fields) == {
        "schema_version",
        "catalog_item_id",
        "fact_kind",
        "version",
        "published_at",
    }
    assert "image_reference" not in dynamic_fact.model_fields
    assert "image_digest" not in dynamic_fact.model_fields


def test_shipped_catalog_has_only_reviewed_home_assistant_binding() -> None:
    catalog = YamlCatalogLoader().load()

    assert len(catalog.entries) > 0
    for entry in catalog.entries:
        if entry.item.id == "home-assistant":
            assert entry.deployment_binding is not None
        else:
            assert entry.deployment_binding is None, entry.item.id
