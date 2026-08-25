from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_plan import contract, evaluator
from app.installation_plan.adapters import CatalogAdapter, RepositoryArtifactAdapter
from app.installation_plan.evaluator import InstallationPlanAssembler


@pytest.fixture
def base_fingerprint_input(monkeypatch: pytest.MonkeyPatch) -> contract.FingerprintInputV1:
    captured: list[contract.FingerprintInputV1] = []
    monkeypatch.setattr(
        evaluator,
        "fingerprint",
        lambda value: (captured.append(value), contract.fingerprint(value))[1],
    )
    catalog = CatalogAdapter().read("home-assistant")
    artifact = RepositoryArtifactAdapter(Path("/opt/atlas")).observe(
        catalog.selected.entry
    )
    InstallationPlanAssembler().assemble(
        catalog=catalog,
        artifact_observation=artifact,
        evidence_observations=(),
        evaluation_instant="2026-08-25T00:00:00Z",
    )
    return captured[0]


def _pairs() -> dict[str, tuple[object, object]]:
    evidence = lambda source: contract.EvidenceDecisionInput(
        expected_source_id=source, source_class="unknown", subject=None,
        release_version=None, image_reference=None, image_digest=None,
        source_id=None, immutable_identity=None, evidence_id=None, attested_at=None,
        freshness_window_seconds=None, disposition="missing", eligibility="ineligible",
        reason_code="record_missing",
    )
    provenance = lambda claim: contract.ProvenanceDecisionInputV1(
        claim=claim, source_class="curated_catalog", source_id="source",
        immutable_identity="1" * 64, observed_at=None, attested_at=None,
    )
    descriptor = lambda key: contract.PrerequisiteDescriptorInputV1(
        kind="platform", requirement_key=key, relationship=None
    )
    prerequisite = lambda key: contract.PrerequisiteDecisionInputV1(
        prerequisite_id=key, kind="platform", state="unknown",
        descriptor=descriptor(key),
    )
    relationship = lambda item: contract.RelationshipDecisionInputV1(
        kind="depends_on", item_id=item, required=False,
        minimum_version=None, maximum_version=None,
    )
    assumption = lambda key: contract.AssumptionDecisionInputV1(
        assumption_id=key, kind="environment",
        source_fact_kind="prerequisite_unknown", subject=key,
    )
    blocker = lambda subject: contract.BlockerDecisionInputV1(
        code="image_conflict", subject=subject
    )
    risk = lambda subject: contract.RiskDecisionInputV1(
        code="compatibility_warning", severity="medium", subject=subject
    )
    missing = lambda subject: contract.MissingFactDecisionInputV1(
        code="source_fact", subject=subject
    )
    confirmation = lambda subject: contract.ConfirmationDecisionInputV1(
        code="accept_assumption", subject=subject,
        prompt_template_id="atlas:prompt:accept-assumption:v1",
    )
    absence = lambda subject: contract.AbsenceFactInputV1(
        kind="evidence_record", subject=subject, source_id="source",
        identity=("1" if subject == "a" else "2") * 64,
    )
    conflict = lambda subject: contract.ConflictFactInputV1(
        kind="image_claim", subject=subject,
        left_identity="1" * 64, right_identity="2" * 64,
    )
    unavailable = lambda subject: contract.SourceUnavailableFactInputV1(
        subject=subject, expected_source_id="source",
        identity=("1" if subject == "a" else "2") * 64,
    )
    freshness = lambda identity: contract.FreshnessDecisionInputV1(
        evidence_identity=identity, effective_time="2026-08-25T00:00:00Z",
        window_seconds=60, age_seconds=0, result="fresh",
    )
    return {
        "evidence_decisions": (evidence("a"), evidence("b")),
        "provenance_decisions": (provenance("a"), provenance("b")),
        "prerequisites": (prerequisite("a"), prerequisite("b")),
        "relationships": (relationship("a"), relationship("b")),
        "assumptions": (assumption("a"), assumption("b")),
        "blockers": (blocker("a"), blocker("b")),
        "risks": (risk("a"), risk("b")),
        "missing_facts": (missing("a"), missing("b")),
        "confirmations": (confirmation("a"), confirmation("b")),
        "absence_facts": (absence("a"), absence("b")),
        "conflict_facts": (conflict("a"), conflict("b")),
        "source_unavailable_facts": (unavailable("a"), unavailable("b")),
        "freshness_decisions": (freshness("1" * 64), freshness("2" * 64)),
    }


@pytest.mark.parametrize("field", tuple(_pairs()))
def test_every_fingerprint_array_accepts_sorted_and_rejects_swap_and_duplicate(
    base_fingerprint_input: contract.FingerprintInputV1, field: str
) -> None:
    left, right = _pairs()[field]
    values = base_fingerprint_input.model_dump(mode="python")
    values[field] = (left, right)
    contract.FingerprintInputV1(**values)
    values[field] = (right, left)
    with pytest.raises(ValidationError):
        contract.FingerprintInputV1(**values)
    values[field] = (left, left)
    with pytest.raises(ValidationError):
        contract.FingerprintInputV1(**values)


def test_fingerprint_compatibility_array_exact_cardinality_and_relation(
    base_fingerprint_input: contract.FingerprintInputV1,
) -> None:
    assert len(base_fingerprint_input.compatibility_decisions) == 1
    values = base_fingerprint_input.model_dump(mode="python")
    values["compatibility_decisions"] = ()
    with pytest.raises(ValidationError):
        contract.FingerprintInputV1(**values)
    values["compatibility_decisions"] = (
        base_fingerprint_input.compatibility_decisions[0],
    ) * 2
    with pytest.raises(ValidationError):
        contract.FingerprintInputV1(**values)


def test_fingerprint_prerequisite_cardinality_64_then_65(
    base_fingerprint_input: contract.FingerprintInputV1,
) -> None:
    rows = tuple(
        contract.PrerequisiteDecisionInputV1(
            prerequisite_id=f"prerequisite-{index:02}", kind="platform",
            state="unknown",
            descriptor=contract.PrerequisiteDescriptorInputV1(
                kind="platform", requirement_key=f"capability:{index:02}",
                relationship=None,
            ),
        )
        for index in range(65)
    )
    values = base_fingerprint_input.model_dump(mode="python")
    values["prerequisites"] = rows[:64]
    contract.FingerprintInputV1(**values)
    values["prerequisites"] = rows
    with pytest.raises(ValidationError):
        contract.FingerprintInputV1(**values)
