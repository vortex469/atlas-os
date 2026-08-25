from __future__ import annotations

from typing import Any, get_args, get_origin, get_type_hints

import pytest
from pydantic import ValidationError

from app.installation_plan import contract


@pytest.mark.parametrize("value", ["0.0.0", "2.10.0", "2147483647.0.1"])
def test_version_and_numeric_components(value: str) -> None:
    assert contract.version_components(value) == tuple(map(int, value.split(".")))


@pytest.mark.parametrize("value", ["01.0.0", "1.0", "2147483648.0.0", "1.0.0 "])
def test_version_rejections(value: str) -> None:
    with pytest.raises(ValueError):
        contract.version_components(value)


@pytest.mark.parametrize(
    "valid", ["0001-01-01T00:00:00Z", "2000-02-29T23:59:59Z", "9999-12-31T23:59:59Z"]
)
def test_utc_second(valid: str) -> None:
    contract.FreshnessDecisionInputV1(
        evidence_identity="0" * 64,
        effective_time=valid,
        window_seconds=60,
        age_seconds=0,
        result="fresh",
    )


@pytest.mark.parametrize(
    "invalid",
    [
        "0000-01-01T00:00:00Z",
        "2024-02-30T00:00:00Z",
        "2024-01-01T00:00:00+00:00",
        "2024-01-01T00:00:00.1Z",
    ],
)
def test_utc_second_rejections(invalid: str) -> None:
    with pytest.raises(ValidationError):
        contract.FreshnessDecisionInputV1(
            evidence_identity="0" * 64,
            effective_time=invalid,
            window_seconds=60,
            age_seconds=0,
            result="fresh",
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ubuntu", "docker.io/library/ubuntu"),
        ("docker.io/ubuntu:latest", "docker.io/library/ubuntu"),
        ("GHCR.IO/org/image", "ghcr.io/org/image"),
        ("localhost:5000/a", "localhost:5000/a"),
    ],
)
def test_oci_normalization(raw: str, expected: str | None) -> None:
    if expected is None:
        with pytest.raises(ValueError):
            contract.normalize_oci_reference(raw)
    else:
        assert contract.normalize_oci_reference(raw)[0] == expected


def test_restricted_jcs_vectors() -> None:
    class CanonicalVector(contract.ContractModel):
        z: int
        a: str
        b: bool
        n: None

    class HashVector(contract.ContractModel):
        a: int

    assert (
        contract.canonical_json(CanonicalVector(z=0, a="é", b=True, n=None))
        == '{"a":"é","b":true,"n":null,"z":0}'.encode()
    )
    assert (
        contract.compound_hash("atlas:test:v1", HashVector(a=1))
        == "33f88a82fa847e43acf4c4236853217db02357c8bbf830aa91ad098c9e909fc7"
    )
    with pytest.raises(TypeError):
        contract.canonical_json({"bad": 1.0})  # type: ignore[arg-type]


def test_models_are_strict_closed_frozen() -> None:
    blocker = contract.Blocker(code="image_conflict", subject="app")
    with pytest.raises(ValidationError):
        contract.Blocker(code="image_conflict", subject="app", surprise=True)
    with pytest.raises(ValidationError):
        blocker.subject = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        contract.Relationship(
            kind="depends_on",
            item_id="app",
            required=1,
            minimum_version=None,
            maximum_version=None,
        )


def test_decision_models_have_no_any_or_arbitrary_maps() -> None:
    for name in (
        "ApplicationDecisionInputV1",
        "CatalogDecisionFingerprintInputV1",
        "BindingDecisionInputV1",
        "ArtifactDecisionInputV1",
        "ImageDecisionInputV1",
        "EvidenceDecisionInput",
        "ProvenanceDecisionInputV1",
        "CompatibilityDecisionInputV1",
        "PrerequisiteDecisionInputV1",
        "RelationshipDecisionInputV1",
        "AssumptionDecisionInputV1",
        "BlockerDecisionInputV1",
        "RiskDecisionInputV1",
        "MissingFactDecisionInputV1",
        "ConfirmationDecisionInputV1",
        "AbsenceFactInputV1",
        "ConflictFactInputV1",
        "SourceUnavailableFactInputV1",
        "FreshnessDecisionInputV1",
    ):
        hints = get_type_hints(getattr(contract, name), include_extras=True)
        for hint in hints.values():
            assert hint is not Any
            assert get_origin(hint) is not dict
            assert dict not in get_args(hint)


def test_artifact_relation_is_closed() -> None:
    with pytest.raises(ValidationError):
        contract.ArtifactDecisionInputV1(
            state="unsafe",
            repository_path="a.yaml",
            service="a",
            content_digest=None,
            reason_code="invalid_yaml",
            identity="0" * 64,
        )


def test_evidence_triple_and_unknown_enum_rejected() -> None:
    base = {
        "expected_source_id": "source",
        "source_class": "unknown",
        "subject": None,
        "release_version": None,
        "image_reference": None,
        "image_digest": None,
        "source_id": None,
        "immutable_identity": None,
        "evidence_id": None,
        "attested_at": None,
        "freshness_window_seconds": None,
    }
    with pytest.raises(ValidationError):
        contract.EvidenceDecisionInput(
            **base,
            disposition="accepted",
            eligibility="eligible",
            reason_code="record_missing",
        )
    with pytest.raises(ValidationError):
        contract.Blocker(code="implementation_only", subject="app")


@pytest.mark.parametrize(
    ("disposition", "eligibility", "reason"),
    [
        ("accepted", "eligible", "accepted_fresh"),
        ("accepted", "ineligible", "accepted_stale"),
        ("missing", "ineligible", "record_missing"),
        ("untrusted", "ineligible", "source_class_untrusted"),
        ("unsupported", "ineligible", "source_class_unsupported"),
        ("malformed", "ineligible", "record_malformed"),
        ("malformed", "ineligible", "timestamp_malformed"),
        ("malformed", "ineligible", "digest_or_identity_malformed"),
        ("conflicted", "ineligible", "accepted_claim_conflict"),
        ("conflicted", "ineligible", "immutable_identity_conflict"),
        ("mismatched", "ineligible", "release_identity_mismatch"),
        ("unavailable", "ineligible", "source_unavailable"),
    ],
)
def test_every_evidence_decision_triple(
    disposition: str, eligibility: str, reason: str
) -> None:
    contract.EvidenceDecisionInput(
        expected_source_id="expected",
        source_class="registry_attested",
        subject="app",
        release_version="2.10.0",
        image_reference="ghcr.io/acme/app",
        image_digest="sha256:" + "1" * 64,
        source_id="collector",
        immutable_identity="2" * 64,
        evidence_id="3" * 64,
        attested_at="2026-08-25T00:00:00Z",
        freshness_window_seconds=60,
        disposition=disposition,
        eligibility=eligibility,
        reason_code=reason,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"subject": None, "eligibility": "eligible"},
        {"immutable_identity": "2" * 64, "evidence_id": None},
        {"immutable_identity": None, "evidence_id": "3" * 64},
        {"source_class": "unknown", "immutable_identity": "2" * 64, "evidence_id": "3" * 64},
        {"attested_at": None, "freshness_window_seconds": 60},
    ],
)
def test_evidence_decision_null_identity_freshness_relations(change: dict[str, object]) -> None:
    values: dict[str, object] = {
        "expected_source_id": "expected", "source_class": "registry_attested",
        "subject": "app", "release_version": "2.10.0",
        "image_reference": "ghcr.io/acme/app", "image_digest": "sha256:" + "1" * 64,
        "source_id": "collector", "immutable_identity": None, "evidence_id": None,
        "attested_at": "2026-08-25T00:00:00Z", "freshness_window_seconds": None,
        "disposition": "accepted", "eligibility": "ineligible", "reason_code": "accepted_stale",
    }
    values.update(change)
    with pytest.raises(ValidationError):
        contract.EvidenceDecisionInput(**values)


@pytest.mark.parametrize(
    "change",
    [
        {"immutable_identity": None, "evidence_id": None},
        {"immutable_identity": "2" * 64, "evidence_id": None},
        {"freshness_window_seconds": None},
    ],
)
def test_accepted_evidence_requires_complete_derived_fields(
    change: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "expected_source_id": "expected", "source_class": "registry_attested",
        "subject": "app", "release_version": "2.10.0",
        "image_reference": "ghcr.io/acme/app",
        "image_digest": "sha256:" + "1" * 64, "source_id": "collector",
        "immutable_identity": "2" * 64, "evidence_id": "3" * 64,
        "attested_at": "2026-08-25T00:00:00Z", "freshness_window_seconds": 60,
        "disposition": "accepted", "eligibility": "eligible",
        "reason_code": "accepted_fresh",
    }
    values.update(change)
    with pytest.raises(ValidationError):
        contract.EvidenceDecisionInput(**values)


@pytest.mark.parametrize(
    ("model", "valid", "invalid"),
    [
        (contract.DeploymentArtifact,
         {"state": "present", "repository_path": "compose/a.yaml", "service": "a", "content_digest": "sha256:" + "1" * 64},
         {"state": "present", "repository_path": "compose/a.yaml", "service": "a", "content_digest": None}),
        (contract.Image,
         {"state": "grounded", "reference": "ghcr.io/a/b", "digest": "sha256:" + "1" * 64, "release_version": "1.0.0"},
         {"state": "grounded", "reference": "ghcr.io/a/b", "digest": None, "release_version": "1.0.0"}),
        (contract.BindingDecisionInputV1,
         {"state": "absent", "repository_path": None, "service": None, "identity": "1" * 64},
         {"state": "absent", "repository_path": "a.yaml", "service": "a", "identity": "1" * 64}),
        (contract.ArtifactDecisionInputV1,
         {"state": "unsafe", "repository_path": "a.yaml", "service": "a", "content_digest": None, "reason_code": "symlink", "identity": "1" * 64},
         {"state": "unsafe", "repository_path": "a.yaml", "service": "a", "content_digest": None, "reason_code": "invalid_yaml", "identity": "1" * 64}),
        (contract.ConflictFactInputV1,
         {"kind": "image_claim", "subject": "app", "left_identity": "1" * 64, "right_identity": "2" * 64},
         {"kind": "image_claim", "subject": "app", "left_identity": "2" * 64, "right_identity": "1" * 64}),
        (contract.FreshnessDecisionInputV1,
         {"evidence_identity": "1" * 64, "effective_time": "2026-08-25T00:00:00Z", "window_seconds": 60, "age_seconds": 60, "result": "fresh"},
         {"evidence_identity": "1" * 64, "effective_time": "2026-08-25T00:00:00Z", "window_seconds": 60, "age_seconds": 61, "result": "fresh"}),
    ],
)
def test_complete_model_relations(model: object, valid: dict[str, object], invalid: dict[str, object]) -> None:
    model(**valid)  # type: ignore[operator]
    with pytest.raises(ValidationError):
        model(**invalid)  # type: ignore[operator]


@pytest.mark.parametrize("model", [contract.Relationship, contract.RelationshipDecisionInputV1])
def test_relationship_bounds_use_numeric_components(model: object) -> None:
    model(kind="depends_on", item_id="app", required=True,
          minimum_version="2.10.0", maximum_version="10.0.0")  # type: ignore[operator]
    with pytest.raises(ValidationError):
        model(kind="depends_on", item_id="app", required=True,
              minimum_version="10.0.0", maximum_version="2.10.0")  # type: ignore[operator]


def _compat_finding(
    identity: str = "finding", *, evidence_ids: tuple[str, ...] = (),
    severity: str = "info", status: str = "compatible",
) -> contract.CompatibilityFindingInputV1:
    return contract.CompatibilityFindingInputV1(
        id=identity, check_type="catalog", severity=severity, status=status,
        subject="app", evidence_ids=evidence_ids,
    )


def test_compatibility_nested_array_bounds_ordering_and_duplicates() -> None:
    _compat_finding(evidence_ids=())
    _compat_finding(evidence_ids=tuple(f"id-{i:02}" for i in range(32)))
    with pytest.raises(ValidationError):
        _compat_finding(evidence_ids=tuple(f"id-{i:02}" for i in range(33)))
    with pytest.raises(ValidationError):
        _compat_finding(evidence_ids=("b", "a"))
    with pytest.raises(ValidationError):
        _compat_finding(evidence_ids=("a", "a"))

    base = {
        "item_id": "app", "evaluator_identity": "1" * 64,
        "input_identity": "2" * 64, "source_target_type_present": False,
        "source_result": "compatible", "projected_result": "compatible",
        "projected_reason": "target_free_catalog_compatible",
        "findings": (_compat_finding("a"), _compat_finding("b")),
        "unknown_fact_codes": (), "warning_projection": False,
        "target_required_projection": False,
    }
    contract.CompatibilityDecisionInputV1(**base)
    for field, value in (
        ("findings", tuple(reversed(base["findings"]))),
        ("findings", (base["findings"][0], base["findings"][0])),
        ("unknown_fact_codes", ("b", "a")),
        ("unknown_fact_codes", ("a", "a")),
    ):
        invalid = dict(base)
        invalid[field] = value
        with pytest.raises(ValidationError):
            contract.CompatibilityDecisionInputV1(**invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_result", "incompatible"),
        ("source_target_type_present", True),
        ("projected_result", "unknown"),
        ("projected_reason", "compatibility_fact_missing"),
        ("warning_projection", True),
        ("target_required_projection", True),
        ("unknown_fact_codes", ("missing",)),
    ],
)
def test_compatibility_projection_contradictions(field: str, value: object) -> None:
    values: dict[str, object] = {
        "item_id": "app", "evaluator_identity": "1" * 64,
        "input_identity": "2" * 64, "source_target_type_present": False,
        "source_result": "compatible", "projected_result": "compatible",
        "projected_reason": "target_free_catalog_compatible", "findings": (),
        "unknown_fact_codes": (), "warning_projection": False,
        "target_required_projection": False,
    }
    values[field] = value
    with pytest.raises(ValidationError):
        contract.CompatibilityDecisionInputV1(**values)
