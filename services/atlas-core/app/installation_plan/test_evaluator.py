from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_plan import contract, evaluator
from app.installation_plan.adapters import (
    ArtifactObservation,
    CatalogAdapter,
    CatalogRecord,
    CatalogSnapshot,
    CompatibilityAdapterInput,
    RepositoryArtifactAdapter,
    adapt_raw_evidence_record,
)
from app.installation_plan.evaluator import (
    InstallationPlanAssembler,
    _catalog,
    _plan_status,
    _prerequisites,
)

INSTANT = "2026-08-25T00:00:00Z"


def _home(*observations):
    catalog = CatalogAdapter().read("home-assistant")
    artifact = RepositoryArtifactAdapter(Path("/opt/atlas")).observe(
        catalog.selected.entry
    )
    return InstallationPlanAssembler().assemble(
        catalog=catalog,
        artifact_observation=artifact,
        evidence_observations=observations,
        evaluation_instant=INSTANT,
    )


def _home_compat(compatibility: CompatibilityAdapterInput):
    catalog = CatalogAdapter().read("home-assistant")
    artifact = RepositoryArtifactAdapter(Path("/opt/atlas")).observe(
        catalog.selected.entry
    )
    return InstallationPlanAssembler().assemble(
        catalog=catalog, artifact_observation=artifact, evidence_observations=(),
        compatibility_observation=compatibility, evaluation_instant=INSTANT,
    )


def _home_artifact(artifact: ArtifactObservation, *observations):
    return InstallationPlanAssembler().assemble(
        catalog=CatalogAdapter().read("home-assistant"),
        artifact_observation=artifact, evidence_observations=observations,
        evaluation_instant=INSTANT,
    )


def test_home_assistant_complete_plan_golden() -> None:
    plan = _home()
    assert plan.application.model_dump() == {
        "item_id": "home-assistant",
        "catalog_entry_id": "d5-home-assistant",
        "display_name": "Home Assistant",
        "release_version": "2026.8.3",
    }
    assert plan.deployment_artifact.model_dump() == {
        "state": "missing",
        "kind": "docker-compose",
        "repository_path": "compose/home-assistant.yaml",
        "service": "home-assistant",
        "content_digest": None,
    }
    assert plan.status == "missing_deployment_artifact"
    assert (
        plan.fingerprint.value
        == "886899818be44d5e1c1499c948b5a6760e2a4e1349d4fb57c3ad13ccce83be68"
    )
    assert ("missing_deployment_artifact", "home-assistant") in {
        (b.code, b.subject) for b in plan.blockers
    }
    assert plan.image.state == "missing"


def test_home_assistant_real_evidence_fixed_instant_golden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []
    monkeypatch.setattr(
        evaluator, "fingerprint",
        lambda value: (captured.append(value), contract.fingerprint(value))[1],
    )
    observation = adapt_raw_evidence_record(
        b'''catalog_item_id: home-assistant
release_version: 2026.8.3
image_reference: ghcr.io/home-assistant/home-assistant
image_digest: sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe
source_class: registry_attested
source_id: collector:home-assistant-ghcr-cosign
attested_at: 2026-08-21T20:54:36Z
''',
        expected_source_id="collector:home-assistant-ghcr-cosign",
    )
    plan = _home(observation)
    evidence = plan.accepted_evidence[0]
    assert evidence.immutable_identity == "4d60b08f34e168cb5ac825671682cfb9855175fa09fc08450e8bcdc84692d7c3"
    assert evidence.evidence_id == "930204abdb4caf6f4cb5da28ffc00c315370933211b5097a7e653e0953af5e11"
    assert evidence.attested_at == "2026-08-21T20:54:36Z"
    assert any(p.source_class == "policy_evaluation" for p in plan.provenance)
    assert plan.deployment_artifact.state == "missing"
    assert plan.image.model_dump() == {
        "state": "missing", "reference": None, "digest": None,
        "release_version": "2026.8.3",
    }
    assert plan.compatibility[0].model_dump() == {
        "environment": "item-scoped", "result": "unknown",
        "reason_code": "compatibility_fact_missing",
    }
    assert {(r.kind, r.item_id, r.required) for r in plan.relationships} == {
        ("integrates_with", "mqtt", False),
        ("integrates_with", "postgresql", False),
    }
    assert {p.description for p in plan.prerequisites} == {
        "Requires capability container-orchestration.",
        "Requires port 8123/tcp in the inbound direction (required: false).",
    }
    assert {b.code for b in plan.blockers} == {
        "missing_deployment_artifact", "missing_immutable_image_identity",
        "unknown_compatibility", "missing_prerequisite_fact",
        "required_operator_confirmation",
    }
    assert {m.code for m in plan.missing_facts} == {
        "deployment_artifact", "immutable_image_identity", "prerequisite_fact",
        "compatibility_fact",
    }
    assert len(plan.assumptions) == 2
    assert len(plan.required_operator_confirmations) == 4
    for prerequisite in plan.prerequisites:
        assumptions = [
            a for a in plan.assumptions
            if prerequisite.prerequisite_id in a.statement
        ]
        assert len(assumptions) == 1
        assumption = assumptions[0]
        assert assumption.kind == "environment"
        assert assumption.statement == (
            "Target environment must be checked for prerequisite "
            f"{prerequisite.prerequisite_id}."
        )
        assert [(c.code, c.subject, c.prompt) for c in plan.required_operator_confirmations
                if c.subject == prerequisite.prerequisite_id] == [
            ("confirm_prerequisite", prerequisite.prerequisite_id,
             f"Review the informational prerequisite {prerequisite.prerequisite_id}; "
             + "this does not approve or authorize any action.")
        ]
        assert len([c for c in plan.required_operator_confirmations
                    if c.code == "accept_assumption"
                    and c.subject == assumption.assumption_id]) == 1
        required_subjects = {
            b.subject for b in plan.blockers
            if b.code == "required_operator_confirmation"
        }
        assert {prerequisite.prerequisite_id, assumption.assumption_id} <= required_subjects
    assert not plan.risks
    fp_input = captured[0]
    assert [(x.result, x.age_seconds, x.window_seconds) for x in fp_input.freshness_decisions] == [
        ("fresh", 270324, 2592000)
    ]
    assert {(x.kind, x.subject) for x in fp_input.absence_facts} == {
        ("deployment_artifact", "home-assistant"),
        ("compatibility_fact", "home-assistant"),
        *(('prerequisite_fact', p.prerequisite_id) for p in plan.prerequisites),
    }
    provenance = {(p.claim, p.source_class): p for p in plan.provenance}
    assert provenance[("catalog_entry", "curated_catalog")].immutable_identity == (
        fp_input.catalog.catalog_source_identity
    )
    assert provenance[("deployment_binding", "deployment_binding")].immutable_identity == (
        fp_input.binding.identity
    )
    assert provenance[("deployment_artifact", "repository_observation")].immutable_identity == (
        fp_input.artifact.identity
    )
    assert provenance[("immutable_image_release", "image_release_evidence")].immutable_identity == (
        evidence.immutable_identity
    )
    assert provenance[("compatibility", "compatibility_evaluation")].immutable_identity == (
        contract.compound_hash(
            "atlas:compatibility-decision:v1", fp_input.compatibility_decisions[0]
        )
    )
    assert provenance[("compatibility", "compatibility_evaluation")].immutable_identity == (
        "ed4cd909345d8fb4e1575b048e5948c76a8b2ac557a5a3347a38d7b415d396f3"
    )
    freshness = fp_input.freshness_decisions[0]
    assert provenance[("freshness", "policy_evaluation")].immutable_identity == (
        contract.compound_hash(
            "atlas:freshness:v1",
            contract.FreshnessIdentityInputV1(
                policy_identity=fp_input.freshness_policy_identity,
                evaluation_instant=fp_input.evaluation_instant,
                evidence_identity=freshness.evidence_identity,
                effective_time=freshness.effective_time,
                window_seconds=freshness.window_seconds,
                age_seconds=freshness.age_seconds,
                result=freshness.result,
            ),
        )
    )
    assert plan.status == "missing_deployment_artifact"
    assert plan.fingerprint.value == "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"


@pytest.mark.parametrize(
    ("raw_kind", "blocker", "missing"),
    [
        ("absent", "missing_accepted_evidence", "accepted_evidence"),
        ("source_unavailable", "missing_accepted_evidence", "source_fact"),
        ("parse_failure", "malformed_evidence", "source_fact"),
    ],
)
def test_nonpresent_evidence_consequences(
    raw_kind: str, blocker: str, missing: str
) -> None:
    observation = adapt_raw_evidence_record(
        None if raw_kind != "parse_failure" else b"[",
        expected_source_id="expected",
        source_unavailable=raw_kind == "source_unavailable",
    )
    plan = _home(observation)
    assert blocker in {b.code for b in plan.blockers}
    assert missing in {m.code for m in plan.missing_facts}
    assert any(p.source_class == "image_release_evidence" for p in plan.provenance)


def test_permutation_invariance_and_mandatory_absence_facts_change_golden() -> None:
    a = adapt_raw_evidence_record(None, expected_source_id="a")
    b = adapt_raw_evidence_record(None, expected_source_id="b")
    assert _home(a, b).fingerprint == _home(b, a).fingerprint


def test_status_precedence_retains_lower_blockers() -> None:
    plan = _home(adapt_raw_evidence_record(b"[", expected_source_id="bad"))
    assert plan.status == "missing_deployment_artifact"
    assert {
        "missing_deployment_artifact",
        "malformed_evidence",
        "unknown_compatibility",
    } <= {b.code for b in plan.blockers}


def _evidence(
    *, source_class: str = "registry_attested", source_id: str = "collector",
    item: str = "home-assistant", release: str = "2026.8.3",
    reference: str = "ghcr.io/home-assistant/home-assistant",
    digest: str = "sha256:" + "1" * 64,
    attested_at: str = "2026-08-25T00:00:00Z",
):
    return adapt_raw_evidence_record(
        (f"catalog_item_id: {item}\nrelease_version: {release}\n"
         f"image_reference: {reference}\nimage_digest: {digest}\n"
         f"source_class: {source_class}\nsource_id: {source_id}\n"
         f"attested_at: {attested_at}\n").encode(),
        expected_source_id=source_id,
    )


@pytest.mark.parametrize(
    ("seconds", "reason", "age"),
    [
        (-300, "accepted_fresh", 0),
        (-301, "timestamp_malformed", None),
        (2592000, "accepted_fresh", 2592000),
        (2592001, "accepted_stale", 2592001),
    ],
)
def test_evidence_time_boundaries(seconds: int, reason: str, age: int | None) -> None:
    from datetime import datetime, timedelta, timezone

    instant = datetime(2026, 8, 25, tzinfo=timezone.utc)
    observed = instant - timedelta(seconds=seconds)
    plan = _home(_evidence(attested_at=observed.strftime("%Y-%m-%dT%H:%M:%SZ")))
    provenance = [p for p in plan.provenance if p.source_class == "image_release_evidence"]
    assert len(provenance) == 1
    assert ({"malformed_evidence", "stale_evidence"} & {b.code for b in plan.blockers}) == (
        {"malformed_evidence"} if reason == "timestamp_malformed"
        else {"stale_evidence"} if reason == "accepted_stale" else set()
    )
    freshness = [p for p in plan.provenance if p.claim == "freshness"]
    assert len(freshness) == (0 if age is None else 1)


def test_evidence_precedence_untrusted_over_mismatch_and_stale() -> None:
    plan = _home(_evidence(
        source_class="upstream_signed", item="other", release="1.0.0",
        attested_at="2026-01-01T00:00:00Z",
    ))
    codes = {b.code for b in plan.blockers}
    assert "untrusted_evidence" in codes
    assert "image_mismatch" not in codes
    assert "stale_evidence" not in codes


def test_evidence_precedence_mismatch_over_claim_conflict_and_stale() -> None:
    rows = (
        _evidence(item="other", digest="sha256:" + "1" * 64,
                  attested_at="2026-01-01T00:00:00Z", source_id="a"),
        _evidence(item="other", digest="sha256:" + "2" * 64,
                  attested_at="2026-01-01T00:00:00Z", source_id="b"),
    )
    plan = _home(*rows)
    codes = {b.code for b in plan.blockers}
    assert "image_mismatch" in codes
    assert "image_conflict" not in codes
    assert "stale_evidence" not in codes


def test_evidence_precedence_claim_conflict_over_stale() -> None:
    plan = _home(
        _evidence(digest="sha256:" + "1" * 64,
                  attested_at="2026-01-01T00:00:00Z", source_id="a"),
        _evidence(digest="sha256:" + "2" * 64,
                  attested_at="2026-01-01T00:00:00Z", source_id="b"),
    )
    codes = {b.code for b in plan.blockers}
    assert "image_conflict" in codes
    assert "stale_evidence" not in codes


def test_evidence_precedence_identity_collision_over_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evaluator, "_evidence_immutable_identity", lambda _value: "a" * 64)
    plan = _home(
        _evidence(item="other-a", source_id="a", digest="sha256:" + "1" * 64),
        _evidence(item="other-b", source_id="b", digest="sha256:" + "2" * 64),
    )
    codes = {b.code for b in plan.blockers}
    assert "provenance_conflict" in codes
    assert "image_mismatch" not in codes


def test_exact_duplicate_observation_collapses_once() -> None:
    row = _evidence()
    plan = _home(row, row)
    assert len(plan.accepted_evidence) == 1
    assert len([p for p in plan.provenance if p.source_class == "image_release_evidence"]) == 1


def test_immutable_identity_collision_is_total_and_permutation_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []
    monkeypatch.setattr(
        evaluator,
        "fingerprint",
        lambda value: (captured.append(value), contract.fingerprint(value))[1],
    )
    monkeypatch.setattr(evaluator, "_evidence_immutable_identity", lambda _value: "a" * 64)
    left = _evidence(source_id="a", digest="sha256:" + "1" * 64)
    right = _evidence(source_id="b", digest="sha256:" + "2" * 64)
    left_input = contract.EvidenceImmutableIdentityInputV1(
        catalog_item_id=left.subject, release_version=left.release_version,
        image_reference=left.image_reference, image_digest=left.image_digest,
        source_class=left.source_class, source_id=left.released_source_id,
        attested_at=left.attested_at,
    )
    right_input = contract.EvidenceImmutableIdentityInputV1(
        catalog_item_id=right.subject, release_version=right.release_version,
        image_reference=right.image_reference, image_digest=right.image_digest,
        source_class=right.source_class, source_id=right.released_source_id,
        attested_at=right.attested_at,
    )
    assert left_input != right_input
    assert evaluator._evidence_immutable_identity(left_input) == "a" * 64
    assert evaluator._evidence_immutable_identity(right_input) == "a" * 64
    first, second = _home(left, right), _home(right, left)
    assert first.fingerprint == second.fingerprint
    assert not first.accepted_evidence
    assert first.image.state == "missing"
    assert first.status == "conflicted"
    assert "provenance_conflict" in {b.code for b in first.blockers}
    assert "source_fact" in {m.code for m in first.missing_facts}
    collision_provenance = [
        p for p in first.provenance
        if p.source_class == "image_release_evidence"
    ]
    assert len(collision_provenance) == 2
    # Collision is at the evidence-row identity layer. Ineligible provenance
    # deliberately uses each full decision hash, which must remain distinct.
    assert len({p.immutable_identity for p in collision_provenance}) == 2
    for fp_input in captured:
        facts = [f for f in fp_input.conflict_facts if f.kind == "immutable_identity"]
        assert len(facts) == 1
        assert facts[0].left_identity < facts[0].right_identity
        decisions = [
            d for d in fp_input.evidence_decisions
            if d.reason_code == "immutable_identity_conflict"
        ]
        assert len(decisions) == 2
        assert {(d.disposition, d.eligibility) for d in decisions} == {
            ("conflicted", "ineligible")
        }


def test_provenance_identity_conflict_does_not_select_conflicted_image() -> None:
    fresh = _evidence(source_id="same", attested_at="2026-08-24T00:00:00Z")
    stale = _evidence(source_id="same", attested_at="2026-01-01T00:00:00Z")
    plan = _home(fresh, stale)
    assert plan.status == "conflicted"
    assert plan.image.state == "missing"
    assert "provenance_conflict" in {blocker.code for blocker in plan.blockers}


def test_image_claim_conflict_selects_conflicted_image() -> None:
    plan = _home(
        _evidence(source_id="a", digest="sha256:" + "1" * 64),
        _evidence(source_id="b", digest="sha256:" + "2" * 64),
    )
    assert plan.image.state == "conflicted"
    assert plan.status == "conflicted"
    assert "image_conflict" in {blocker.code for blocker in plan.blockers}


def test_installation_plan_rejects_status_inconsistent_with_blockers() -> None:
    plan = _home()
    values = plan.model_dump(mode="python")
    values["status"] = "plan_ready_for_review"
    with pytest.raises(ValidationError):
        contract.InstallationPlan(**values)


def _finding(severity: str, status: str):
    return contract.CompatibilityFindingInputV1(
        id=f"finding-{severity}", check_type="catalog", severity=severity,
        status=status, subject="home-assistant", evidence_ids=(),
    )


@pytest.mark.parametrize(
    ("target", "status", "findings", "unknown", "result", "reason"),
    [
        (True, "compatible", (), (), "unknown", "target_required"),
        (True, "compatible_with_warnings", (_finding("warning", "compatible_with_warnings"),), (), "unknown", "target_required"),
        (True, "insufficient_information", (), ("missing-target-fact",), "unknown", "target_required"),
        (True, "incompatible", (_finding("blocker", "incompatible"),), (), "unknown", "target_required"),
        (False, "compatible", (), (), "compatible", "target_free_catalog_compatible"),
        (False, "compatible_with_warnings", (_finding("warning", "compatible_with_warnings"),), (), "compatible_with_warnings", "target_free_catalog_warning"),
        (False, "incompatible", (_finding("blocker", "incompatible"),), (), "incompatible", "target_free_catalog_incompatible"),
        (False, "incompatible", (
            _finding("blocker", "compatible"),
            _finding("warning", "compatible"),
        ), (), "incompatible", "target_free_catalog_incompatible"),
        (False, "incompatible", (
            _finding("blocker", "compatible"),
            _finding("info", "compatible"),
            _finding("warning", "compatible"),
        ), (), "incompatible", "target_free_catalog_incompatible"),
        (False, "insufficient_information", (), ("missing-fact",), "unknown", "compatibility_fact_missing"),
    ],
)
def test_compatibility_projection_matrix(
    target: bool, status: str, findings: tuple[object, ...], unknown: tuple[str, ...],
    result: str, reason: str,
) -> None:
    observation = CompatibilityAdapterInput(
        source_kind="released", item_id="home-assistant",
        target_type_present=target, status=status, findings=findings,
        unknown_fact_codes=unknown,
    )
    projected = _home_compat(observation).compatibility[0]
    assert (projected.result, projected.reason_code) == (result, reason)


@pytest.mark.parametrize(
    ("source_kind", "status", "unknown", "reason"),
    [
        ("absent", "not_available", (), "compatibility_fact_missing"),
        ("malformed_optional", "insufficient_information",
         ("malformed_optional_compatibility_fact",), "compatibility_fact_malformed"),
    ],
)
def test_optional_compatibility_source_states(
    source_kind: str, status: str, unknown: tuple[str, ...], reason: str
) -> None:
    observation = CompatibilityAdapterInput(
        source_kind=source_kind, item_id="home-assistant",
        target_type_present=False, status=status, findings=(),
        unknown_fact_codes=unknown,
    )
    assert _home_compat(observation).compatibility[0].reason_code == reason


@pytest.mark.parametrize(
    ("source_kind", "status", "findings", "unknown"),
    [
        ("absent", "not_available", (_finding("info", "compatible"),), ()),
        ("absent", "not_available", (), ("forbidden",)),
        ("malformed_optional", "insufficient_information",
         (_finding("unknown", "insufficient_information"),),
         ("malformed_optional_compatibility_fact",)),
        ("malformed_optional", "insufficient_information", (), ("wrong",)),
    ],
)
def test_optional_compatibility_sources_reject_retained_payload(
    source_kind: str, status: str, findings: tuple[object, ...],
    unknown: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        CompatibilityAdapterInput(
            source_kind=source_kind, item_id="home-assistant",
            target_type_present=False, status=status, findings=findings,
            unknown_fact_codes=unknown,
        )


def test_compatibility_warning_consequences_exactly_once() -> None:
    plan = _home_compat(CompatibilityAdapterInput(
        source_kind="released", item_id="home-assistant",
        target_type_present=False, status="compatible_with_warnings",
        findings=(_finding("warning", "compatible_with_warnings"),),
        unknown_fact_codes=(),
    ))
    assert [(r.code, r.severity, r.subject) for r in plan.risks].count(
        ("compatibility_warning", "medium", "home-assistant")
    ) == 1
    catalog_assumptions = [a for a in plan.assumptions if a.kind == "catalog"]
    assert len(catalog_assumptions) == 1
    assert len([c for c in plan.required_operator_confirmations if c.code == "confirm_risk"]) == 1
    assert len([
        c for c in plan.required_operator_confirmations
        if c.code == "accept_assumption"
        and c.subject == catalog_assumptions[0].assumption_id
    ]) == 1


def _artifact(
    *, state: str = "present", reference: str | None = None,
    digest: str | None = None, mutable: bool = False,
    reason: str | None = None,
) -> ArtifactObservation:
    return ArtifactObservation(
        state=state, repository_path="compose/home-assistant.yaml",
        service="home-assistant",
        content_digest="sha256:" + "f" * 64 if state == "present" else None,
        reason_code=reason, image_reference=reference, image_digest=digest,
        image_mutable=mutable,
    )


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("conflicted", "conflicted"),
        ("mismatched", "mismatched"),
        ("mutable", "mutable"),
        ("missing", "missing"),
        ("untrusted", "untrusted"),
        ("unknown", "unknown"),
        ("grounded", "grounded"),
    ],
)
def test_image_state_matrix_and_first_match_precedence(case: str, expected: str) -> None:
    ref = "ghcr.io/home-assistant/home-assistant"
    digest = "sha256:" + "1" * 64
    if case == "conflicted":
        plan = _home_artifact(
            _artifact(),
            _evidence(source_id="a", digest="sha256:" + "1" * 64),
            _evidence(source_id="b", digest="sha256:" + "2" * 64),
        )
    elif case == "mismatched":
        plan = _home_artifact(_artifact(reference=ref, digest=digest),
                              _evidence(digest="sha256:" + "2" * 64))
    elif case == "mutable":
        plan = _home_artifact(_artifact(reference=ref, mutable=True), _evidence())
    elif case == "missing":
        plan = _home_artifact(_artifact(state="missing"), _evidence())
    elif case == "untrusted":
        plan = _home_artifact(_artifact(reference=ref, digest=digest),
                              _evidence(source_class="upstream_signed"))
    elif case == "unknown":
        plan = _home_artifact(_artifact(reference=ref, digest=digest))
    else:
        plan = _home_artifact(_artifact(reference=ref, digest=digest), _evidence())
    assert plan.image.state == expected


def test_missing_artifact_never_synthesizes_image_from_evidence() -> None:
    plan = _home_artifact(_artifact(state="missing"), _evidence())
    assert plan.image.model_dump() == {
        "state": "missing", "reference": None, "digest": None,
        "release_version": "2026.8.3",
    }
    assert plan.status == "missing_deployment_artifact"


@pytest.mark.parametrize(
    ("age", "present"),
    [(2332800, True), (2332799, False)],
)
def test_evidence_approaching_expiry_final_ten_percent_boundary(
    age: int, present: bool,
) -> None:
    from datetime import datetime, timedelta, timezone

    instant = datetime(2026, 8, 25, tzinfo=timezone.utc)
    attested = (instant - timedelta(seconds=age)).strftime("%Y-%m-%dT%H:%M:%SZ")
    plan = _home_artifact(
        _artifact(
            reference="ghcr.io/home-assistant/home-assistant",
            digest="sha256:" + "1" * 64,
        ),
        _evidence(attested_at=attested),
    )
    matching = [r for r in plan.risks if r.code == "evidence_approaching_expiry"]
    assert bool(matching) is present
    if matching:
        assert [(r.severity, r.subject) for r in matching] == [
            ("low", "home-assistant")
        ]
    assert not [c for c in plan.required_operator_confirmations if c.code == "confirm_risk"]
    assert not {"artifact_content_change", "environment_variance"} & {
        r.code for r in plan.risks
    }


def test_status_precedence_matrix_retains_lower_ranked_blockers() -> None:
    warning = CompatibilityAdapterInput(
        source_kind="released", item_id="home-assistant", target_type_present=False,
        status="incompatible",
        findings=(_finding("blocker", "incompatible"),), unknown_fact_codes=(),
    )
    catalog = CatalogAdapter().read("home-assistant")
    missing = _artifact(state="missing")
    plan = InstallationPlanAssembler().assemble(
        catalog=catalog, artifact_observation=missing, evidence_observations=(),
        compatibility_observation=warning, evaluation_instant=INSTANT,
    )
    assert plan.status == "missing_deployment_artifact"
    assert "incompatible_application_environment" in {b.code for b in plan.blockers}

    stale = _evidence(attested_at="2026-01-01T00:00:00Z")
    present = _artifact(
        reference="ghcr.io/home-assistant/home-assistant",
        digest="sha256:" + "1" * 64,
    )
    plan = InstallationPlanAssembler().assemble(
        catalog=catalog, artifact_observation=present,
        evidence_observations=(stale,), compatibility_observation=warning,
        evaluation_instant=INSTANT,
    )
    assert plan.status == "incompatible"
    assert "stale_evidence" in {b.code for b in plan.blockers}

    plan = _home_artifact(present, stale)
    assert plan.status == "stale_evidence"
    assert "unknown_compatibility" in {b.code for b in plan.blockers}


@pytest.mark.parametrize(
    ("codes", "status"),
    [
        ({"image_conflict", "missing_deployment_artifact"}, "conflicted"),
        ({"missing_deployment_artifact", "incompatible_application_environment"},
         "missing_deployment_artifact"),
        ({"incompatible_application_environment", "stale_evidence"}, "incompatible"),
        ({"stale_evidence", "unknown_compatibility"}, "stale_evidence"),
        ({"unknown_compatibility"}, "insufficient_information"),
        (set(), "plan_ready_for_review"),
    ],
)
def test_complete_status_matrix(codes: set[str], status: str) -> None:
    assert _plan_status(codes) == status


def _reject_public_plan(plan: contract.InstallationPlan, **changes: object) -> None:
    values = plan.model_dump(mode="python")
    values.update(changes)
    with pytest.raises(ValidationError):
        contract.InstallationPlan(**values)


def _with_blockers(
    plan: contract.InstallationPlan,
    *, add: tuple[contract.Blocker, ...] = (), remove: frozenset[str] = frozenset(),
) -> tuple[tuple[contract.Blocker, ...], str]:
    rows = tuple(blocker for blocker in plan.blockers if blocker.code not in remove) + add
    rows = tuple(sorted(rows, key=lambda row: (contract._BLOCKER_RANK[row.code], row.subject)))
    return rows, _plan_status({row.code for row in rows})


@pytest.mark.parametrize(
    ("base", "extra_code"),
    [
        ("missing", "image_conflict"),
        ("grounded", "image_conflict"),
        ("mismatched", "image_conflict"),
        ("mutable", "image_mismatch"),
        ("grounded", "unknown_image_state"),
        ("grounded", "missing_immutable_image_identity"),
    ],
)
def test_public_plan_rejects_contradictory_image_blocker(
    base: str, extra_code: str,
) -> None:
    ref = "ghcr.io/home-assistant/home-assistant"
    digest = "sha256:" + "1" * 64
    plans = {
        "missing": lambda: _home(),
        "grounded": lambda: _home_artifact(
            _artifact(reference=ref, digest=digest), _evidence()
        ),
        "mismatched": lambda: _home_artifact(
            _artifact(reference=ref, digest=digest),
            _evidence(digest="sha256:" + "2" * 64),
        ),
        "mutable": lambda: _home_artifact(
            _artifact(reference=ref, mutable=True), _evidence()
        ),
    }
    plan = plans[base]()
    blockers, status = _with_blockers(
        plan, add=(contract.Blocker(code=extra_code, subject="home-assistant"),)
    )
    _reject_public_plan(plan, blockers=blockers, status=status)


def test_public_plan_rejects_missing_or_wrong_subject_image_conflict() -> None:
    plan = _home_artifact(
        _artifact(),
        _evidence(source_id="a", digest="sha256:" + "1" * 64),
        _evidence(source_id="b", digest="sha256:" + "2" * 64),
    )
    blockers, status = _with_blockers(plan, remove=frozenset({"image_conflict"}))
    _reject_public_plan(plan, blockers=blockers, status=status)
    blockers, status = _with_blockers(
        plan,
        add=(contract.Blocker(code="image_conflict", subject="other"),),
        remove=frozenset({"image_conflict"}),
    )
    _reject_public_plan(plan, blockers=blockers, status=status)


def test_public_plan_rejects_mismatch_replaced_by_image_conflict() -> None:
    plan = _home_artifact(
        _artifact(
            reference="ghcr.io/home-assistant/home-assistant",
            digest="sha256:" + "1" * 64,
        ),
        _evidence(digest="sha256:" + "2" * 64),
    )
    blockers, status = _with_blockers(
        plan,
        add=(contract.Blocker(code="image_conflict", subject="home-assistant"),),
        remove=frozenset({"image_mismatch"}),
    )
    _reject_public_plan(plan, blockers=blockers, status=status)


@pytest.mark.parametrize(
    ("state", "wrong_code"),
    [
        ("present", "missing_deployment_artifact"),
        ("missing", "invalid_deployment_artifact"),
        ("invalid", "unsafe_deployment_artifact"),
        ("unsafe", "unknown_deployment_artifact"),
    ],
)
def test_public_plan_rejects_contradictory_artifact_blocker(
    state: str, wrong_code: str,
) -> None:
    reasons = {"invalid": "invalid_yaml", "unsafe": "symlink"}
    plan = _home_artifact(_artifact(state=state, reason=reasons.get(state)))
    blockers, status = _with_blockers(
        plan, add=(contract.Blocker(code=wrong_code, subject="home-assistant"),)
    )
    _reject_public_plan(plan, blockers=blockers, status=status)


def test_public_plan_rejects_artifact_blocker_wrong_subject() -> None:
    plan = _home()
    blockers, status = _with_blockers(
        plan,
        add=(contract.Blocker(code="missing_deployment_artifact", subject="other"),),
        remove=frozenset({"missing_deployment_artifact"}),
    )
    _reject_public_plan(plan, blockers=blockers, status=status)


def test_public_plan_unbound_unknown_artifact_has_no_catalog_subject_fallback() -> None:
    plan = _home()
    blockers, status = _with_blockers(
        plan,
        add=(contract.Blocker(
            code="unknown_deployment_artifact", subject="unbound-artifact",
        ),),
        remove=frozenset({"missing_deployment_artifact"}),
    )
    missing_facts = tuple(sorted(
        (
            fact for fact in plan.missing_facts
            if not (
                fact.code == "deployment_artifact"
                and fact.subject == "home-assistant"
            )
        ),
        key=lambda fact: (contract._MISSING_RANK[fact.code], fact.subject),
    )) + (contract.MissingFact(
        code="deployment_artifact", subject="unbound-artifact",
    ),)
    missing_facts = tuple(sorted(
        missing_facts,
        key=lambda fact: (contract._MISSING_RANK[fact.code], fact.subject),
    ))
    values = plan.model_dump(mode="python")
    values.update(
        deployment_artifact={
            "state": "unknown", "kind": "docker-compose",
            "repository_path": None, "service": None, "content_digest": None,
        },
        blockers=blockers, missing_facts=missing_facts, status=status,
    )
    contract.InstallationPlan(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim", "different_claim"),
        ("source_id", "different-source"),
        ("immutable_identity", "0" * 64),
        ("attested_at", "2026-08-20T00:00:00Z"),
        ("source_class", "policy_evaluation"),
    ],
)
def test_public_plan_rejects_inexact_accepted_evidence_provenance(
    field: str, value: str,
) -> None:
    plan = _home(_evidence())
    evidence = plan.accepted_evidence[0]
    rows = list(plan.provenance)
    index = next(
        index for index, row in enumerate(rows)
        if row.source_class == "image_release_evidence"
        and row.immutable_identity == evidence.immutable_identity
    )
    rows[index] = rows[index].model_copy(update={field: value})
    rows.sort(key=lambda row: (
        row.claim, contract._PROVENANCE_RANK[row.source_class], row.source_id,
        row.immutable_identity, row.observed_at or "", row.attested_at or "",
    ))
    _reject_public_plan(plan, provenance=tuple(rows))


def test_public_plan_accepts_exact_accepted_evidence_provenance() -> None:
    plan = _home(_evidence())
    evidence = plan.accepted_evidence[0]
    assert any(
        row.source_class == "image_release_evidence"
        and row.claim == evidence.claim
        and row.source_id == evidence.source_id
        and row.immutable_identity == evidence.immutable_identity
        and row.attested_at == evidence.attested_at
        for row in plan.provenance
    )
    contract.InstallationPlan(**plan.model_dump(mode="python"))


def test_public_plan_rejects_cross_satisfied_evidence_provenance() -> None:
    plan = _home(
        _evidence(source_id="shared", attested_at="2026-08-24T00:00:00Z"),
        _evidence(source_id="shared", attested_at="2026-08-23T00:00:00Z"),
    )
    evidence = plan.accepted_evidence
    rows = list(plan.provenance)
    indexes = [
        index for index, row in enumerate(rows)
        if row.source_class == "image_release_evidence"
    ]
    rows[indexes[0]] = rows[indexes[0]].model_copy(
        update={"immutable_identity": evidence[1].immutable_identity}
    )
    rows[indexes[1]] = rows[indexes[1]].model_copy(
        update={"immutable_identity": evidence[0].immutable_identity}
    )
    rows.sort(key=lambda row: (
        row.claim, contract._PROVENANCE_RANK[row.source_class], row.source_id,
        row.immutable_identity, row.observed_at or "", row.attested_at or "",
    ))
    _reject_public_plan(plan, provenance=tuple(rows))


def test_public_plan_rejects_compatibility_contradictions() -> None:
    compatible = _home_compat(CompatibilityAdapterInput(
        source_kind="released", item_id="home-assistant",
        target_type_present=False, status="compatible", findings=(),
        unknown_fact_codes=(),
    ))
    blockers, status = _with_blockers(
        compatible,
        add=(contract.Blocker(
            code="incompatible_application_environment", subject="home-assistant"
        ),),
    )
    _reject_public_plan(compatible, blockers=blockers, status=status)

    incompatible = _home_compat(CompatibilityAdapterInput(
        source_kind="released", item_id="home-assistant",
        target_type_present=False, status="incompatible",
        findings=(_finding("blocker", "incompatible"),), unknown_fact_codes=(),
    ))
    blockers, status = _with_blockers(
        incompatible, remove=frozenset({"incompatible_application_environment"})
    )
    _reject_public_plan(incompatible, blockers=blockers, status=status)

    target_required = _home_compat(CompatibilityAdapterInput(
        source_kind="released", item_id="home-assistant",
        target_type_present=True, status="compatible", findings=(),
        unknown_fact_codes=(),
    ))
    blockers, status = _with_blockers(
        target_required,
        add=(contract.Blocker(
            code="incompatible_application_environment", subject="home-assistant"
        ),),
    )
    _reject_public_plan(target_required, blockers=blockers, status=status)


def test_complete_prerequisite_producer_matrix_and_exact_descriptions() -> None:
    snapshot = CatalogAdapter().read("home-assistant")
    catalog, identity, _ = _catalog(snapshot)
    requirements = contract.RequirementDecisionInputV1(
        capability_ids=("container",), cpu_cores_min="2", memory_mb_min=4096,
        storage_gb_min="10.5", gpu_required=True, gpu_memory_gb_min="8",
        architectures=("amd64",), operating_systems=("linux",),
        runtimes=("docker",), devices=("usb",),
        ports=(
            contract.RequirementPortDecisionInputV1(
                port=80, protocol="tcp", direction="inbound", required=False
            ),
            contract.RequirementPortDecisionInputV1(
                port=443, protocol="tcp", direction="outbound", required=True
            ),
        ),
        requires_internet=True, requires_lan=True,
    )
    catalog = catalog.model_copy(update={"requirements": requirements})
    prerequisites, decisions, provenance = _prerequisites(catalog, snapshot, identity)
    assert len(prerequisites) == len(decisions) == len(provenance) == 14
    assert {p.description for p in prerequisites} == {
        "Requires at least 2 CPU cores.",
        "Requires at least 4096 MB memory.",
        "Requires at least 10.5 GB storage.",
        "Requires a GPU.",
        "Requires at least 8 GB GPU memory.",
        "Requires capability container.",
        "Requires architecture amd64.",
        "Requires operating system linux.",
        "Requires runtime docker.",
        "Requires device usb.",
        "Requires port 80/tcp in the inbound direction (required: false).",
        "Requires port 443/tcp in the outbound direction (required: true).",
        "Requires internet access.",
        "Requires LAN access.",
    }
    # Both required=false and required=true ports are environmental facts; neither
    # silently disappears merely because the catalog marks exposure optional.
    assert len(prerequisites) == 14


@pytest.mark.parametrize(
    ("target_status", "target_version", "minimum", "maximum", "state"),
    [
        ("active", "2.10.0", None, None, "satisfied"),
        ("active", "2.10.0", "2.10.0", None, "satisfied"),
        ("active", "2.10.0", None, "2.10.0", "satisfied"),
        ("active", "2.10.0", "2.10.1", None, "missing"),
        ("active", "2.10.0", None, "2.9.9", "missing"),
        ("active", None, "1.0.0", None, "unknown"),
        ("deprecated", "2.10.0", None, None, "missing"),
    ],
)
def test_application_prerequisite_version_and_activity_matrix(
    target_status: str, target_version: str | None, minimum: str | None,
    maximum: str | None, state: str,
) -> None:
    snapshot = CatalogAdapter().read("home-assistant")
    catalog, identity, _ = _catalog(snapshot)
    source_target = next(r for r in snapshot.records if r.entry.item.id == "mqtt")
    item_values = source_target.entry.item.model_dump(mode="python")
    item_values.update(status=target_status, version=target_version)
    target_item = type(source_target.entry.item).model_validate(item_values)
    target_entry = source_target.entry.model_copy(
        update={"item": target_item, "release_claim": None}
    )
    target = CatalogRecord(
        entry=target_entry, reviewed_content_digest=source_target.reviewed_content_digest
    )
    augmented = CatalogSnapshot(
        selected=snapshot.selected,
        records=tuple(r for r in snapshot.records if r.entry.item.id != "mqtt")
        + (target,),
    )
    relationship = contract.RelationshipDecisionInputV1(
        kind="depends_on", item_id="mqtt", required=True,
        minimum_version=minimum, maximum_version=maximum,
    )
    catalog = catalog.model_copy(update={"relationships": (relationship,)})
    prerequisites, _, _ = _prerequisites(catalog, augmented, identity)
    assert len(prerequisites) == 3
    projected = next(p for p in prerequisites if p.kind == "application")
    assert projected.state == state
    assert projected.description == (
        "Requires application relationship depends_on with item mqtt; "
        f"minimum version {minimum or 'none'}; maximum version {maximum or 'none'}."
    )


def test_relationship_kind_emission_and_optional_prerequisite_rule() -> None:
    snapshot = CatalogAdapter().read("home-assistant")
    catalog, identity, _ = _catalog(snapshot)
    kinds = (
        "depends_on", "provides", "consumes", "requires", "integrates_with",
        "conflicts_with", "runs_on", "deployed_by", "compatible_with",
        "incompatible_with",
    )
    relationships = tuple(
        contract.RelationshipDecisionInputV1(
            kind=kind, item_id=f"target-{index:02}", required=False,
            minimum_version=None, maximum_version=None,
        )
        for index, kind in enumerate(kinds)
    )
    catalog = catalog.model_copy(update={"relationships": relationships})
    assert tuple(r.kind for r in catalog.relationships) == kinds
    prerequisites, _, _ = _prerequisites(catalog, snapshot, identity)
    assert not [p for p in prerequisites if p.kind == "application"]


@pytest.mark.parametrize(("count", "accepted"), [(64, True), (65, False)])
def test_actual_assembler_prerequisite_cardinality_boundary(
    count: int, accepted: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = CatalogAdapter().read("home-assistant")
    catalog_model, catalog_identity, catalog_source_identity = _catalog(snapshot)
    environmental_count = 16
    requirements = catalog_model.requirements.model_copy(
        update={
            "capability_ids": tuple(
                f"capability-{index:02}" for index in range(environmental_count)
            ),
            "cpu_cores_min": None, "memory_mb_min": None,
            "storage_gb_min": None, "gpu_required": False,
            "gpu_memory_gb_min": None, "architectures": (),
            "operating_systems": (), "runtimes": (), "devices": (),
            "ports": (), "requires_internet": False, "requires_lan": False,
        }
    )
    relationships = tuple(
        contract.RelationshipDecisionInputV1(
            kind="depends_on", item_id=f"target-{index:02}", required=True,
            minimum_version=None, maximum_version=None,
        )
        for index in range(count - environmental_count)
    )
    catalog_model = catalog_model.model_copy(
        update={"requirements": requirements, "relationships": relationships}
    )
    target_source = next(row for row in snapshot.records if row.entry.item.id == "mqtt")
    targets = []
    for index in range(count - environmental_count):
        target_item = target_source.entry.item.model_copy(
            update={"id": f"target-{index:02}", "version": "1.0.0"}
        )
        targets.append(CatalogRecord(
            entry=target_source.entry.model_copy(
                update={"item": target_item, "release_claim": None}
            ),
            reviewed_content_digest=target_source.reviewed_content_digest,
        ))
    augmented = CatalogSnapshot(
        selected=snapshot.selected, records=(snapshot.selected, *targets),
    )
    monkeypatch.setattr(
        evaluator, "_catalog",
        lambda _snapshot: (catalog_model, catalog_identity, catalog_source_identity),
    )
    artifact = ArtifactObservation(
        state="missing", repository_path="compose/home-assistant.yaml",
        service="home-assistant", content_digest=None, reason_code=None,
        image_reference=None, image_digest=None, image_mutable=False,
    )
    if not accepted:
        with pytest.raises(ValueError):
            InstallationPlanAssembler().assemble(
                catalog=augmented, artifact_observation=artifact,
                evidence_observations=(), evaluation_instant=INSTANT,
            )
        return
    plan = InstallationPlanAssembler().assemble(
        catalog=augmented, artifact_observation=artifact,
        evidence_observations=(), evaluation_instant=INSTANT,
    )
    assert len(plan.prerequisites) == 64
