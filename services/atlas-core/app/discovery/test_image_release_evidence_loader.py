from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.discovery.exceptions import (
    DiscoveryCatalogError,
    ImageReleaseEvidenceConflictError,
    ImageReleaseEvidenceDocumentError,
    ImageReleaseEvidenceDuplicateError,
    ImageReleaseEvidenceLoaderError,
    ImageReleaseEvidencePathError,
    ImageReleaseEvidenceValidationError,
    ImageReleaseEvidenceYamlError,
)
from app.discovery.image_release_evidence_loader import (
    DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR,
    CuratedImageReleaseEvidenceDocument,
    ImageReleaseEvidenceLoader,
    LoadedImageReleaseEvidence,
)
from app.discovery.models import DiscoveryCenterModel

DIGEST = (
    "sha256:"
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
REFERENCE = "ghcr.example/atlas/my-service"


def evidence_yaml(
    *,
    catalog_item_id: str = "my-service",
    release_version: str = "1.2.3",
    image_reference: str = REFERENCE,
    image_digest: str = DIGEST,
    source_class: str = "curated",
    source_id: str = "source-a",
    attested_at: str = "2026-01-15T00:00:00Z",
) -> str:
    return (
        "schema_version: 1\n"
        "evidence:\n"
        f"  catalog_item_id: {catalog_item_id}\n"
        f'  release_version: "{release_version}"\n'
        f"  image_reference: {image_reference}\n"
        f"  image_digest: {image_digest}\n"
        f"  source_class: {source_class}\n"
        f"  source_id: {source_id}\n"
        f"  attested_at: \"{attested_at}\"\n"
    )


def write(
    tmp_path: Path,
    name: str,
    text: str,
    *,
    subdir: str | None = None,
) -> Path:
    directory = tmp_path / subdir if subdir is not None else tmp_path
    if subdir is not None:
        directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Envelope contract
# ---------------------------------------------------------------------------


def test_envelope_is_frozen_and_extra_forbid() -> None:
    document = CuratedImageReleaseEvidenceDocument.model_validate(
        {
            "schema_version": 1,
            "evidence": {
                "catalog_item_id": "my-service",
                "release_version": "1.2.3",
                "image_reference": REFERENCE,
                "image_digest": DIGEST,
                "source_class": "curated",
                "source_id": "source-a",
                "attested_at": datetime(2026, 1, 15, tzinfo=UTC),
            },
        }
    )
    with pytest.raises((ValueError, AttributeError)):
        document.schema_version = 2  # type: ignore[misc]
    with pytest.raises((ValueError, AttributeError)):
        document.evidence = document.evidence  # type: ignore[misc]
    assert DiscoveryCenterModel.model_config["frozen"] is True
    assert CuratedImageReleaseEvidenceDocument.model_config["extra"] == "forbid"

    with pytest.raises(ValueError):
        CuratedImageReleaseEvidenceDocument.model_validate(
            {
                "schema_version": 1,
                "evidence": {
                    "catalog_item_id": "my-service",
                    "release_version": "1.2.3",
                    "image_reference": REFERENCE,
                    "image_digest": DIGEST,
                    "source_class": "curated",
                    "source_id": "source-a",
                    "attested_at": datetime(2026, 1, 15, tzinfo=UTC),
                },
                "unexpected": "extra",
            }
        )


def test_loaded_result_is_frozen_and_extra_forbid() -> None:
    assert (
        LoadedImageReleaseEvidence.model_config["extra"] == "forbid"
    )
    result = LoadedImageReleaseEvidence()
    assert result.rows == ()
    assert result.source_paths == ()
    with pytest.raises((ValueError, AttributeError)):
        result.rows = ()  # type: ignore[misc]
    with pytest.raises(ValueError):
        LoadedImageReleaseEvidence(rows=(), extra=1)  # type: ignore[call-arg]


def test_schema_version_strictly_literal_one() -> None:
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            evidence_yaml().replace("schema_version: 1", "schema_version: 2"),
            source="schema-2",
        )
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            "schema_version: '1'\nevidence:\n",
            source="schema-string",
        )


def test_delegates_row_validation_to_existing_image_release_evidence(
    tmp_path: Path,
) -> None:
    """Invalid rows must fail via the existing P1a validators."""

    # Non-strict release version.
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            evidence_yaml(release_version="1.2.3-rc1"),
            source="bad-version",
        )
    # Bad digest.
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            evidence_yaml(image_digest="sha256:zz" + "0" * 62),
            source="bad-digest",
        )
    # Missing required field.
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            "schema_version: 1\nevidence:\n  catalog_item_id: my-service\n",
            source="missing-fields",
        )
    # Unknown field on the row (extra-forbid).
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            evidence_yaml().replace(
                "  attested_at:",
                "  unexpected_row_field: 1\n  attested_at:",
            ),
            source="extra-row-field",
        )
    # Naive timestamp.
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            evidence_yaml(attested_at="2026-01-15T00:00:00"),
            source="naive-time",
        )
    # Invalid source class.
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader().load_text(
            evidence_yaml(source_class="guessed"),
            source="bad-source-class",
        )


def test_document_root_must_be_mapping() -> None:
    with pytest.raises(ImageReleaseEvidenceDocumentError, match="<memory>"):
        ImageReleaseEvidenceLoader().load_text("- one\n- two\n")
    with pytest.raises(ImageReleaseEvidenceDocumentError):
        ImageReleaseEvidenceLoader().load_text("just a string")
    with pytest.raises(ImageReleaseEvidenceDocumentError):
        ImageReleaseEvidenceLoader().load_text("")


def test_malformed_yaml_fails_with_yaml_error_and_chains() -> None:
    with pytest.raises(ImageReleaseEvidenceYamlError) as excinfo:
        ImageReleaseEvidenceLoader().load_text("a: [unclosed")
    assert isinstance(excinfo.value.__cause__, Exception)


def test_invalid_row_fails_entire_directory_load(tmp_path: Path) -> None:
    write(tmp_path, "good.yaml", evidence_yaml(source_id="good"))
    write(
        tmp_path,
        "bad.yaml",
        evidence_yaml(source_id="bad").replace("1.2.3", "1.2"),
    )
    with pytest.raises(ImageReleaseEvidenceValidationError):
        ImageReleaseEvidenceLoader(tmp_path).load()


def test_one_bad_file_no_partial_results(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", evidence_yaml(source_id="a"))
    write(tmp_path, "b.yaml", "not: [valid")
    with pytest.raises(ImageReleaseEvidenceYamlError):
        ImageReleaseEvidenceLoader(tmp_path).load()


# ---------------------------------------------------------------------------
# Path behavior
# ---------------------------------------------------------------------------


def test_implicit_missing_default_dir_returns_empty(tmp_path: Path) -> None:
    loader = ImageReleaseEvidenceLoader(tmp_path / "missing-default")
    loader._explicit_evidence_path = False

    result = loader.load()
    assert result == LoadedImageReleaseEvidence()


def test_explicit_missing_path_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ImageReleaseEvidencePathError, match=str(missing)):
        ImageReleaseEvidenceLoader(missing).load()


def test_explicit_non_directory_path_fails_closed(tmp_path: Path) -> None:
    file_path = write(tmp_path, "evidence.yaml", evidence_yaml())
    with pytest.raises(ImageReleaseEvidencePathError, match="not a directory"):
        ImageReleaseEvidenceLoader(file_path).load()


def test_explicit_empty_directory_returns_empty(tmp_path: Path) -> None:
    result = ImageReleaseEvidenceLoader(tmp_path).load()
    assert result == LoadedImageReleaseEvidence()


def test_default_directory_ships_zero_yaml_files() -> None:
    assert DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR.is_dir()
    yaml_files = [
        path
        for path in DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR.rglob("*")
        if path.suffix.lower() in {".yaml", ".yml"}
    ]
    assert yaml_files == []


def test_default_directory_loads_to_empty_result() -> None:
    result = ImageReleaseEvidenceLoader().load()
    assert result.rows == ()
    assert result.source_paths == ()


def test_load_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = write(tmp_path, "evidence.txt", evidence_yaml())
    with pytest.raises(ImageReleaseEvidencePathError, match="extension"):
        ImageReleaseEvidenceLoader().load_file(path)


def test_load_file_missing_path_fails(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ImageReleaseEvidencePathError, match="does not exist"):
        ImageReleaseEvidenceLoader().load_file(missing)


def test_load_file_directory_path_fails(tmp_path: Path) -> None:
    (tmp_path / "sub.yaml").mkdir()
    with pytest.raises(ImageReleaseEvidencePathError, match="not a file"):
        ImageReleaseEvidenceLoader().load_file(tmp_path / "sub.yaml")


# ---------------------------------------------------------------------------
# Discovery determinism
# ---------------------------------------------------------------------------


def test_recursive_discovery_is_posix_sorted(tmp_path: Path) -> None:
    write(tmp_path, "zeta.yml", evidence_yaml(source_id="zeta"), subdir="deep")
    write(tmp_path, "alpha.yml", evidence_yaml(source_id="alpha"))
    write(tmp_path, "mid.yaml", evidence_yaml(source_id="mid"), subdir="a")

    result = ImageReleaseEvidenceLoader(tmp_path).load()
    assert [Path(path).name for path in result.source_paths] == [
        "mid.yaml",
        "alpha.yml",
        "zeta.yml",
    ]
    assert [row.source_id for row in result.rows] == [
        "mid",
        "alpha",
        "zeta",
    ]


def test_non_recursive_loading_only_reads_top_level(tmp_path: Path) -> None:
    write(tmp_path, "top.yaml", evidence_yaml(source_id="top"))
    write(tmp_path, "nested.yaml", evidence_yaml(source_id="nested"), subdir="n")

    result = ImageReleaseEvidenceLoader(tmp_path, recursive=False).load()
    assert [Path(path).name for path in result.source_paths] == ["top.yaml"]
    assert [row.source_id for row in result.rows] == ["top"]


def test_load_is_deterministic_and_repeatable(tmp_path: Path) -> None:
    write(tmp_path, "b.yaml", evidence_yaml(source_id="b"))
    write(tmp_path, "a.yml", evidence_yaml(source_id="a", release_version="2.0.0"))

    first = ImageReleaseEvidenceLoader(tmp_path).load()
    second = ImageReleaseEvidenceLoader(tmp_path).load()
    assert first == second
    assert first.rows == second.rows
    assert first.source_paths == second.source_paths


# ---------------------------------------------------------------------------
# Duplicate and conflict semantics
# ---------------------------------------------------------------------------


def test_duplicate_source_id_across_files_fails(tmp_path: Path) -> None:
    write(
        tmp_path,
        "a.yaml",
        evidence_yaml(source_id="same", release_version="1.2.3"),
    )
    write(
        tmp_path,
        "b.yaml",
        evidence_yaml(source_id="same", release_version="9.9.9"),
    )
    with pytest.raises(ImageReleaseEvidenceDuplicateError, match="same"):
        ImageReleaseEvidenceLoader(tmp_path).load()


def test_duplicate_source_id_identical_rows_still_fails(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", evidence_yaml(source_id="same"))
    write(tmp_path, "b.yaml", evidence_yaml(source_id="same"))
    with pytest.raises(ImageReleaseEvidenceDuplicateError):
        ImageReleaseEvidenceLoader(tmp_path).load()


def test_agreement_with_different_source_ids_is_retained(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", evidence_yaml(source_id="source-a"))
    write(
        tmp_path,
        "b.yml",
        evidence_yaml(
            source_id="source-b",
            source_class="registry_attested",
            attested_at="2026-02-01T00:00:00Z",
        ),
    )
    result = ImageReleaseEvidenceLoader(tmp_path).load()
    assert [row.source_id for row in result.rows] == ["source-a", "source-b"]
    assert {
        (row.image_reference, row.image_digest) for row in result.rows
    } == {(REFERENCE, DIGEST)}


def test_conflicting_reference_or_digest_fails(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", evidence_yaml(source_id="source-a"))
    write(
        tmp_path,
        "b.yaml",
        evidence_yaml(
            source_id="source-b",
            image_digest="sha256:" + "ab" * 32,
        ),
    )
    with pytest.raises(ImageReleaseEvidenceConflictError, match="my-service"):
        ImageReleaseEvidenceLoader(tmp_path).load()


def test_conflicting_reference_fails(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", evidence_yaml(source_id="source-a"))
    write(
        tmp_path,
        "b.yaml",
        evidence_yaml(
            source_id="source-b",
            image_reference="ghcr.example/atlas/other",
        ),
    )
    with pytest.raises(ImageReleaseEvidenceConflictError):
        ImageReleaseEvidenceLoader(tmp_path).load()


def test_different_item_and_version_pairs_do_not_conflict(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", evidence_yaml(source_id="source-a"))
    write(
        tmp_path,
        "b.yaml",
        evidence_yaml(
            source_id="source-b",
            release_version="2.0.0",
            image_digest="sha256:" + "ab" * 32,
        ),
    )
    write(
        tmp_path,
        "c.yaml",
        evidence_yaml(
            source_id="source-c",
            catalog_item_id="other-service",
            image_reference="ghcr.example/atlas/other",
        ),
    )
    result = ImageReleaseEvidenceLoader(tmp_path).load()
    assert len(result.rows) == 3


def test_conflict_detection_is_order_independent(tmp_path: Path) -> None:
    first_text = evidence_yaml(source_id="source-a")
    second_text = evidence_yaml(
        source_id="source-b",
        image_digest="sha256:" + "cd" * 32,
    )

    # Write in both orders; both must raise the same conflict error.
    for directory_name, (x_text, y_text) in (
        ("order-one", (first_text, second_text)),
        ("order-two", (second_text, first_text)),
    ):
        order_path = tmp_path / directory_name
        order_path.mkdir()
        (order_path / "x.yaml").write_text(x_text, encoding="utf-8")
        (order_path / "y.yaml").write_text(y_text, encoding="utf-8")
        with pytest.raises(ImageReleaseEvidenceConflictError):
            ImageReleaseEvidenceLoader(order_path).load()


def test_agreement_is_order_independent(tmp_path: Path) -> None:
    first_text = evidence_yaml(source_id="source-a")
    second_text = evidence_yaml(source_id="source-b")

    for directory_name, (x_text, y_text) in (
        ("agreement-one", (first_text, second_text)),
        ("agreement-two", (second_text, first_text)),
    ):
        order_path = tmp_path / directory_name
        order_path.mkdir()
        (order_path / "x.yaml").write_text(x_text, encoding="utf-8")
        (order_path / "y.yaml").write_text(y_text, encoding="utf-8")
        result = ImageReleaseEvidenceLoader(order_path).load()
        assert len(result.rows) == 2


def test_all_loader_exceptions_root_at_discovery_catalog_error() -> None:
    for exc_type in (
        ImageReleaseEvidenceLoaderError,
        ImageReleaseEvidencePathError,
        ImageReleaseEvidenceYamlError,
        ImageReleaseEvidenceDocumentError,
        ImageReleaseEvidenceValidationError,
        ImageReleaseEvidenceDuplicateError,
        ImageReleaseEvidenceConflictError,
    ):
        assert issubclass(exc_type, DiscoveryCatalogError)
        assert issubclass(exc_type, ImageReleaseEvidenceLoaderError)
