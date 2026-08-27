from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_assessment.assessment import assess_installation_admission
from app.installation_assessment.cache import (
    AssessmentIdempotencyConflictError,
    EphemeralAssessmentRetryCache,
)
from app.installation_assessment.contract import (
    REASON_ORDER,
    InstallationAdmissionAssessmentV1,
    InstallationInterestV1,
)
from app.installation_assessment.fingerprint import build_interest_fingerprint
from app.installation_assessment.interest import create_installation_interest
from app.installation_assessment.service import assess_installation_request
from app.installation_plan.assembly import default_installation_plan_dependency
from app.installation_targets.contract import InstallationDestinationSelectionV1

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
NOW_TEXT = "2026-08-27T12:00:00Z"
PLAN_FP = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"
DEST_FP = "a" * 64


def plan():
    return default_installation_plan_dependency(
        repository_root=Path("/opt/atlas"), clock=lambda: datetime(2026, 8, 25, tzinfo=UTC)
    ).assemble("home-assistant")


def selection(**updates: object) -> InstallationDestinationSelectionV1:
    values = {
        "selection_id": "00000000-0000-4000-8000-000000000001",
        "resource_id": "110",
        "selected_destination_fingerprint": DEST_FP,
        "selected_at": "2026-08-27T11:00:00Z",
        "expires_at": "2026-08-28T11:00:00Z",
        "selected_by": "operator-a",
        "request_digest": "b" * 64,
        "selection_fingerprint": "c" * 64,
        "status": "active",
        "terminated_at": None,
    }
    values.update(updates)
    return InstallationDestinationSelectionV1.model_validate(values)


def interest(sel: InstallationDestinationSelectionV1 | None = None, **updates: object):
    value = create_installation_interest(
        plan=plan(),
        plan_fingerprint=PLAN_FP,
        selection=sel or selection(),
        principal_id="operator-a",
        idempotency_key="0123456789abcdef",
        requested_at=NOW,
    )
    return value.model_copy(update=updates)


def assess(**updates: object) -> InstallationAdmissionAssessmentV1:
    values = {
        "plan": plan(),
        "plan_fingerprint": PLAN_FP,
        "selection": selection(),
        "selected_destination_fingerprint": DEST_FP,
        "destination_available": True,
        "destination_identity_available": True,
        "current_destination_fingerprint": DEST_FP,
        "interest": interest(),
        "evaluation_time": NOW_TEXT,
    }
    values.update(updates)
    return assess_installation_admission(**values)  # type: ignore[arg-type]


def test_interest_is_closed_frozen_exact_bounded_and_sanitized() -> None:
    value = interest()
    assert value.schema_version == "installation-interest-v1"
    assert value.interest_kind == "install-container-assessment"
    assert value.expires_at == "2026-08-27T12:05:00Z"
    assert set(InstallationInterestV1.model_fields) == {
        "schema_version", "item_id", "catalog_entry_id",
        "installation_plan_fingerprint", "interest_kind", "selection_id",
        "selected_destination_fingerprint", "requested_at", "expires_at",
        "interest_fingerprint",
    }
    with pytest.raises(ValidationError):
        value.item_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        InstallationInterestV1(**value.model_dump(), command="rm")
    for bad in ("Home Assistant", "../escape", "http://host", "é"):
        with pytest.raises(ValidationError):
            InstallationInterestV1.model_validate({**value.model_dump(), "item_id": bad})
    for bad_time in ("2026-08-27T12:00:00.1Z", "2026-08-27T12:00:00+00:00"):
        with pytest.raises(ValidationError):
            InstallationInterestV1.model_validate({**value.model_dump(), "requested_at": bad_time})


@pytest.mark.parametrize("opaque_id", ["127.0.0.1", "atlas.internal"])
def test_interest_and_assessment_use_exact_plan_id64_domain(opaque_id: str) -> None:
    value = interest()
    assert InstallationInterestV1.model_validate(
        {**value.model_dump(), "item_id": opaque_id, "catalog_entry_id": opaque_id}
    ).item_id == opaque_id
    result = assess()
    assert InstallationAdmissionAssessmentV1.model_validate(
        {**result.model_dump(), "item_id": opaque_id, "catalog_entry_id": opaque_id}
    ).catalog_entry_id == opaque_id


def test_interest_fingerprint_stability_sensitivity_unicode_and_scope() -> None:
    value = interest()
    assert value.interest_fingerprint == interest().interest_fingerprint
    assert value.interest_fingerprint != build_interest_fingerprint(
        item_id=value.item_id, catalog_entry_id=value.catalog_entry_id,
        installation_plan_fingerprint=value.installation_plan_fingerprint,
        selection_id=value.selection_id,
        selected_destination_fingerprint=value.selected_destination_fingerprint,
        requested_at=value.requested_at, expires_at=value.expires_at,
        idempotency_key="fedcba9876543210",
    )
    with pytest.raises(ValueError, match="NFC"):
        build_interest_fingerprint(
            item_id="e\u0301", catalog_entry_id=value.catalog_entry_id,
            installation_plan_fingerprint=value.installation_plan_fingerprint,
            selection_id=value.selection_id,
            selected_destination_fingerprint=value.selected_destination_fingerprint,
            requested_at=value.requested_at, expires_at=value.expires_at,
            idempotency_key="0123456789abcdef",
        )
    with pytest.raises(ValueError, match="principal"):
        create_installation_interest(
            plan=plan(), plan_fingerprint=PLAN_FP, selection=selection(), principal_id="operator-b",
            idempotency_key="0123456789abcdef", requested_at=NOW,
        )


@pytest.mark.parametrize("status,reason", [
    ("conflicted", "installation_plan_conflicted"),
    ("missing_deployment_artifact", "installation_plan_missing_deployment_artifact"),
    ("incompatible", "installation_plan_incompatible"),
    ("stale_evidence", "installation_plan_stale_evidence"),
    ("insufficient_information", "installation_plan_insufficient_information"),
    ("plan_ready_for_review", None),
])
def test_exact_plan_status_mapping(status: str, reason: str | None) -> None:
    result = assess(plan=plan().model_copy(update={"status": status}))
    assert (reason in result.reason_codes) if reason else not any(
        r.startswith("installation_plan_") for r in result.reason_codes
    )


def test_destination_and_interest_reasons_and_canonical_order() -> None:
    expired = selection(status="expired", terminated_at=NOW_TEXT)
    stale_interest = interest(expired).model_copy(update={
        "expires_at": NOW_TEXT,
        "installation_plan_fingerprint": "d" * 64,
        "selection_id": "00000000-0000-4000-8000-000000000002",
    })
    result = assess(
        selection=expired, selected_destination_fingerprint=DEST_FP,
        destination_available=False, destination_identity_available=False,
        current_destination_fingerprint=None, interest=stale_interest,
    )
    assert result.reason_codes == tuple(r for r in REASON_ORDER if r in {
        "installation_plan_missing_deployment_artifact", "destination_selection_expired",
        "destination_unavailable", "installation_interest_expired",
        "installation_interest_plan_stale", "installation_interest_destination_stale",
        "agent_install_container_unsupported",
    })
    assert len(result.reason_codes) == len(set(result.reason_codes))


@pytest.mark.parametrize("updates,reason", [
    ({"selection": None, "selected_destination_fingerprint": None,
      "destination_available": False, "destination_identity_available": False,
      "current_destination_fingerprint": None}, "destination_selection_missing"),
    ({"destination_available": False, "destination_identity_available": False,
      "current_destination_fingerprint": None}, "destination_unavailable"),
    ({"destination_identity_available": False, "current_destination_fingerprint": None}, "destination_identity_unavailable"),
    ({"current_destination_fingerprint": "e" * 64}, "destination_replaced_or_moved"),
    ({"interest": None}, "installation_interest_missing"),
])
def test_individual_destination_and_interest_reasons(updates: dict[str, object], reason: str) -> None:
    assert reason in assess(**updates).reason_codes


@pytest.mark.parametrize("updates", [
    {"selection": None, "selected_destination_fingerprint": DEST_FP,
     "destination_available": False, "destination_identity_available": False,
     "current_destination_fingerprint": None},
    {"selected_destination_fingerprint": None},
    {"selection": None, "selected_destination_fingerprint": None, "destination_available": True},
    {"selection": None, "selected_destination_fingerprint": None, "destination_identity_available": True},
    {"selection": None, "selected_destination_fingerprint": None, "current_destination_fingerprint": DEST_FP},
    {"destination_available": False, "destination_identity_available": True},
    {"destination_available": False, "destination_identity_available": False, "current_destination_fingerprint": DEST_FP},
    {"destination_available": True, "destination_identity_available": True, "current_destination_fingerprint": None},
    {"destination_available": True, "destination_identity_available": False, "current_destination_fingerprint": DEST_FP},
])
def test_contradictory_destination_facts_fail_before_assessment(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="contradictory destination facts"):
        assess(**updates)


def test_terminal_selection_with_positive_replacement_evidence_is_blocked() -> None:
    terminal = selection(status="cancelled", terminated_at=NOW_TEXT)
    result = assess(
        selection=terminal,
        destination_available=True,
        destination_identity_available=True,
        current_destination_fingerprint="e" * 64,
    )
    assert result.assessment_status == "blocked"
    assert "destination_unavailable" in result.reason_codes
    assert "destination_replaced_or_moved" in result.reason_codes


@pytest.mark.parametrize("item_mismatch,catalog_mismatch", [
    (True, False), (False, True), (True, True),
])
def test_interest_plan_identifier_mismatch_is_malformed(
    item_mismatch: bool, catalog_mismatch: bool,
) -> None:
    value = interest().model_copy(update={
        "item_id": "wrong-item" if item_mismatch else "home-assistant",
        "catalog_entry_id": "wrong-catalog" if catalog_mismatch else "d5-home-assistant",
    })
    with pytest.raises(ValueError, match="identifiers must match"):
        assess(
            plan=plan().model_copy(update={"status": "plan_ready_for_review"}),
            interest=value,
        )


def test_unsupported_status_has_one_exact_rule_and_fingerprint_is_sensitive() -> None:
    ready = plan().model_copy(update={"status": "plan_ready_for_review"})
    result = assess(plan=ready)
    assert result.assessment_status == "preconditions_satisfied_but_unsupported"
    assert result.reason_codes == (
        "destination_installation_capability_unknown",
        "agent_install_container_unsupported",
    )
    assert result.candidate_eligibility_evaluated is False
    assert result.assessment_fingerprint == assess(plan=ready).assessment_fingerprint
    assert result.assessment_fingerprint != assess(
        plan=ready, evaluation_time="2026-08-27T12:00:01Z"
    ).assessment_fingerprint
    assert assess(plan=ready, interest=None).assessment_status == "blocked"


def test_assessment_is_closed_frozen_and_null_linkage_changes_fingerprint() -> None:
    present = assess()
    absent = assess(
        selection=None,
        selected_destination_fingerprint=None,
        destination_available=False,
        destination_identity_available=False,
        current_destination_fingerprint=None,
        interest=None,
    )
    assert absent.selection_id is None
    assert absent.selected_destination_fingerprint is None
    assert absent.current_destination_fingerprint is None
    assert absent.interest_fingerprint is None
    assert absent.assessment_fingerprint != present.assessment_fingerprint
    with pytest.raises(ValidationError):
        present.assessment_status = "blocked"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        InstallationAdmissionAssessmentV1(**present.model_dump(), ready=True)


def test_interest_expiry_exact_half_open_boundary() -> None:
    assert "installation_interest_expired" not in assess(
        evaluation_time="2026-08-27T12:04:59Z"
    ).reason_codes
    assert "installation_interest_expired" in assess(
        evaluation_time="2026-08-27T12:05:00Z"
    ).reason_codes


def test_home_assistant_golden_no_target_override() -> None:
    result = assess()
    assert result.assessment_status == "blocked"
    assert result.reason_codes == (
        "installation_plan_missing_deployment_artifact",
        "destination_installation_capability_unknown",
        "agent_install_container_unsupported",
    )
    assert result.plan_fingerprint == PLAN_FP


def test_cache_replay_conflict_expiry_capacity_principal_and_restart() -> None:
    calls = 0
    def factory(instant: datetime) -> InstallationAdmissionAssessmentV1:
        nonlocal calls
        calls += 1
        return assess(evaluation_time=instant.strftime("%Y-%m-%dT%H:%M:%SZ"))
    cache = EphemeralAssessmentRetryCache(capacity=2)
    first, first_bytes, retained = cache.get_or_create(
        principal_id="a", route="assessment", idempotency_key="key",
        canonical_request=b"one", now=NOW, factory=factory,
    )
    replay, replay_bytes, replay_time = cache.get_or_create(
        principal_id="a", route="assessment", idempotency_key="key",
        canonical_request=b"one", now=NOW + timedelta(minutes=1), factory=factory,
    )
    assert (first, first_bytes, retained) == (replay, replay_bytes, replay_time)
    assert calls == 1
    with pytest.raises(AssessmentIdempotencyConflictError):
        cache.get_or_create(principal_id="a", route="assessment", idempotency_key="key",
                            canonical_request=b"two", now=NOW, factory=factory)
    cache.get_or_create(principal_id="b", route="assessment", idempotency_key="key",
                        canonical_request=b"two", now=NOW, factory=factory)
    cache.get_or_create(principal_id="c", route="assessment", idempotency_key="key",
                        canonical_request=b"three", now=NOW, factory=factory)
    assert len(cache) == 2
    cache.get_or_create(principal_id="a", route="assessment", idempotency_key="key",
                        canonical_request=b"new", now=NOW + timedelta(minutes=5), factory=factory)
    assert calls == 4
    assert len(EphemeralAssessmentRetryCache()) == 0


def test_internal_service_verifies_interest_and_retains_one_instant() -> None:
    cache = EphemeralAssessmentRetryCache()
    supplied = interest()
    first = assess_installation_request(
        plan=plan(), plan_fingerprint=PLAN_FP, selection=selection(),
        principal_id="operator-a", idempotency_key="0123456789abcdef",
        requested_at=NOW, destination_available=True,
        destination_identity_available=True, current_destination_fingerprint=DEST_FP,
        retry_cache=cache, interest=supplied,
    )
    replay = assess_installation_request(
        plan=plan(), plan_fingerprint=PLAN_FP, selection=selection(),
        principal_id="operator-a", idempotency_key="0123456789abcdef",
        requested_at=NOW + timedelta(minutes=1), destination_available=True,
        destination_identity_available=True, current_destination_fingerprint=DEST_FP,
        retry_cache=cache, interest=supplied,
    )
    assert first == replay
    for forged, key in (
        (supplied.model_copy(update={"interest_fingerprint": "f" * 64}), "0123456789abcdef"),
        (supplied, "fedcba9876543210"),
    ):
        with pytest.raises(ValueError, match="fingerprint verification failed"):
            assess_installation_request(
                plan=plan(), plan_fingerprint=PLAN_FP, selection=selection(),
                principal_id="operator-a", idempotency_key=key, requested_at=NOW,
                destination_available=True, destination_identity_available=True,
                current_destination_fingerprint=DEST_FP,
                retry_cache=EphemeralAssessmentRetryCache(), interest=forged,
            )


def test_supplied_interest_caps_cache_replay_at_interest_expiry() -> None:
    cache = EphemeralAssessmentRetryCache()
    supplied = interest()

    def request(*, requested_at: datetime, destination_available: bool = True):
        return assess_installation_request(
            plan=plan(), plan_fingerprint=PLAN_FP, selection=selection(),
            principal_id="operator-a", idempotency_key="0123456789abcdef",
            requested_at=requested_at, destination_available=destination_available,
            destination_identity_available=destination_available,
            current_destination_fingerprint=DEST_FP if destination_available else None,
            retry_cache=cache, interest=supplied,
        )

    first = request(requested_at=NOW + timedelta(minutes=4, seconds=58))
    replay = request(requested_at=NOW + timedelta(minutes=4, seconds=59))
    assert replay == first

    at_expiry = request(requested_at=NOW + timedelta(minutes=5))
    assert at_expiry != first
    assert at_expiry[2] == NOW + timedelta(minutes=5)
    assert "installation_interest_expired" in at_expiry[0].reason_codes


def test_supplied_interest_conflict_at_expiry_is_a_new_request() -> None:
    cache = EphemeralAssessmentRetryCache()
    supplied = interest()
    common = {
        "plan": plan(), "plan_fingerprint": PLAN_FP, "selection": selection(),
        "principal_id": "operator-a", "idempotency_key": "0123456789abcdef",
        "retry_cache": cache, "interest": supplied,
    }
    assess_installation_request(
        **common, requested_at=NOW + timedelta(minutes=4, seconds=58),
        destination_available=True, destination_identity_available=True,
        current_destination_fingerprint=DEST_FP,
    )
    result = assess_installation_request(
        **common, requested_at=NOW + timedelta(minutes=5),
        destination_available=False, destination_identity_available=False,
        current_destination_fingerprint=None,
    )
    assert result[2] == NOW + timedelta(minutes=5)
    assert "destination_unavailable" in result[0].reason_codes


def test_cache_without_expiry_ceiling_retains_existing_five_minute_maximum() -> None:
    calls = 0

    def factory(instant: datetime) -> InstallationAdmissionAssessmentV1:
        nonlocal calls
        calls += 1
        return assess(evaluation_time=instant.strftime("%Y-%m-%dT%H:%M:%SZ"))

    cache = EphemeralAssessmentRetryCache()
    first = cache.get_or_create(
        principal_id="a", route="r", idempotency_key="k",
        canonical_request=b"same", now=NOW, factory=factory,
    )
    assert cache.get_or_create(
        principal_id="a", route="r", idempotency_key="k",
        canonical_request=b"same", now=NOW + timedelta(minutes=4, seconds=59),
        factory=factory,
    ) == first
    boundary = cache.get_or_create(
        principal_id="a", route="r", idempotency_key="k",
        canonical_request=b"same", now=NOW + timedelta(minutes=5), factory=factory,
    )
    assert boundary[2] == NOW + timedelta(minutes=5)
    assert calls == 2


def test_internal_service_constructs_interest_at_retained_evaluation_instant() -> None:
    result, _, retained = assess_installation_request(
        plan=plan(), plan_fingerprint=PLAN_FP, selection=selection(),
        principal_id="operator-a", idempotency_key="0123456789abcdef",
        requested_at=NOW, destination_available=True,
        destination_identity_available=True, current_destination_fingerprint=DEST_FP,
        retry_cache=EphemeralAssessmentRetryCache(),
    )
    assert retained == NOW
    assert result.interest_fingerprint == build_interest_fingerprint(
        item_id="home-assistant", catalog_entry_id="d5-home-assistant",
        installation_plan_fingerprint=PLAN_FP,
        selection_id=selection().selection_id,
        selected_destination_fingerprint=DEST_FP,
        requested_at=NOW_TEXT, expires_at="2026-08-27T12:05:00Z",
        idempotency_key="0123456789abcdef",
    )


def test_concurrent_cache_equivalent_calls_converge() -> None:
    cache = EphemeralAssessmentRetryCache()
    calls = 0

    def factory(instant: datetime) -> InstallationAdmissionAssessmentV1:
        nonlocal calls
        calls += 1
        return assess(evaluation_time=instant.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def invoke(_: int):
        return cache.get_or_create(
            principal_id="a", route="r", idempotency_key="k",
            canonical_request=b"same", now=NOW, factory=factory,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(invoke, range(32)))
    assert calls == 1
    assert all(result == results[0] for result in results)


def test_concurrent_cache_conflict_has_one_winner() -> None:
    cache = EphemeralAssessmentRetryCache()

    def invoke(payload: bytes) -> str:
        try:
            cache.get_or_create(
                principal_id="a", route="r", idempotency_key="k",
                canonical_request=payload, now=NOW,
                factory=lambda instant: assess(
                    evaluation_time=instant.strftime("%Y-%m-%dT%H:%M:%SZ")
                ),
            )
        except AssessmentIdempotencyConflictError:
            return "conflict"
        return "success"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(invoke, (b"one", b"two")))
    assert sorted(outcomes) == ["conflict", "success"]


def test_concurrent_cache_half_open_expiry_and_capacity_bound() -> None:
    cache = EphemeralAssessmentRetryCache(capacity=4)

    def invoke(index: int) -> None:
        cache.get_or_create(
            principal_id=str(index), route="r", idempotency_key="k",
            canonical_request=str(index).encode(), now=NOW,
            factory=lambda instant: assess(
                evaluation_time=instant.strftime("%Y-%m-%dT%H:%M:%SZ")
            ),
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(invoke, range(32)))
    assert len(cache) == 4
    calls = 0

    def expiring_factory(instant: datetime) -> InstallationAdmissionAssessmentV1:
        nonlocal calls
        calls += 1
        return assess(evaluation_time=instant.strftime("%Y-%m-%dT%H:%M:%SZ"))

    cache = EphemeralAssessmentRetryCache()
    cache.get_or_create(principal_id="a", route="r", idempotency_key="k",
                        canonical_request=b"old", now=NOW, factory=expiring_factory)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda _: cache.get_or_create(
                principal_id="a", route="r", idempotency_key="k",
                canonical_request=b"new", now=NOW + timedelta(minutes=5),
                factory=expiring_factory,
            ),
            range(16),
        ))
    assert calls == 2
    assert all(result == results[0] for result in results)


def test_authority_isolation_has_no_forbidden_imports_or_calls() -> None:
    root = Path(__file__).parent
    forbidden = (
        "execution_candidates", "agent", "workflow", "approval", "operational_dispatch",
        "worker", "provider", "repository", "dispatch",
    )
    for source in root.glob("*.py"):
        if source.name.startswith("test_"):
            continue
        tree = ast.parse(source.read_text())
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        assert not any(word in imported for imported in imports for word in forbidden)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert not names & {"create_candidate", "dispatch", "worker", "approve", "execute"}
