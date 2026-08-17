from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.discovery.dynamic_evaluation import (
    ClaimEvaluationError,
    ConflictEvaluation,
    ConflictState,
    CuratedClaimProvenance,
    EvaluatedDynamicClaim,
    ExplicitCuratedReleaseClaim,
    FreshnessFailureReason,
    FreshnessState,
    NormalizedDynamicProvenance,
    _claim_digest,
    _claim_sort_key,
    evaluate_freshness,
    evaluate_release_conflict,
)
from app.discovery.dynamic_sources import (
    DYNAMIC_RELEASE_FACT_SCHEMA,
    DynamicReleaseFact,
    DynamicSourceProvenance,
)

RETRIEVED = datetime(2026, 8, 1, 12, tzinfo=UTC)
PUBLISHED = datetime(2026, 7, 31, 18, tzinfo=UTC)


def provenance(
    source_id: str = "source-one",
    *,
    retrieved_at: datetime = RETRIEVED,
    release_id: int = 1,
) -> NormalizedDynamicProvenance:
    return NormalizedDynamicProvenance(
        source_id=source_id,
        source_type="github_latest_release",
        origin_class="public_https_allowlisted",
        trust_tier="supplemental",
        repository="synthetic/fixture",
        upstream_release_id=release_id,
        retrieved_at=retrieved_at,
        expires_at=retrieved_at + timedelta(hours=24),
        response_etag='"fixture"',
        api_version="2022-11-28",
    )


def fact(version: str = "1.2.3", published_at: datetime = PUBLISHED):
    return DynamicReleaseFact(
        schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
        catalog_item_id="frigate",
        fact_kind="latest_stable_release",
        version=version,
        published_at=published_at,
    )


def dynamic(
    source_id: str = "source-one",
    *,
    version: str = "1.2.3",
    retrieved_at: datetime = RETRIEVED,
    now: datetime | None = None,
    release_id: int = 1,
) -> EvaluatedDynamicClaim:
    candidate_provenance = provenance(
        source_id, retrieved_at=retrieved_at, release_id=release_id
    )
    evaluated_at = now or retrieved_at
    freshness = evaluate_freshness(candidate_provenance, now=evaluated_at)
    assert freshness.state is not None
    return EvaluatedDynamicClaim(
        schema_version="discovery-evaluated-dynamic-claim-v1",
        fact=fact(version),
        provenance=candidate_provenance,
        freshness=freshness.state,
        evaluated_at=evaluated_at,
    )


def curated(version: str = "1.2.3") -> ExplicitCuratedReleaseClaim:
    claim = dynamic(version=version)
    return ExplicitCuratedReleaseClaim(
        schema_version="discovery-curated-release-claim-v1",
        key=claim.key,
        value=claim.value,
        provenance=CuratedClaimProvenance(
            source_class="curated",
            source_id="atlas-curated-catalog",
            trust_tier="curated",
        ),
    )


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (RETRIEVED, FreshnessState.FRESH),
        (RETRIEVED + timedelta(hours=24), FreshnessState.FRESH),
        (RETRIEVED + timedelta(hours=24, microseconds=1), FreshnessState.STALE),
        (RETRIEVED + timedelta(days=30), FreshnessState.STALE),
        (RETRIEVED + timedelta(days=30, microseconds=1), FreshnessState.EXPIRED),
    ],
)
def test_exact_freshness_boundaries(now: datetime, expected: FreshnessState):
    assert evaluate_freshness(provenance(), now=now).state is expected


def test_offset_now_is_normalized_and_deterministic():
    offset_now = (RETRIEVED + timedelta(hours=24)).astimezone(
        timezone(timedelta(hours=-4))
    )
    assert evaluate_freshness(provenance(), now=offset_now) == evaluate_freshness(
        provenance(), now=RETRIEVED + timedelta(hours=24)
    )


@pytest.mark.parametrize(
    "offset",
    [timedelta(hours=5, minutes=30), -timedelta(hours=7), timedelta(hours=9)],
)
def test_equivalent_offset_provenance_and_now_normalize_identically(offset):
    zone = timezone(offset)
    offset_retrieved = RETRIEVED.astimezone(zone)
    offset_provenance = provenance(retrieved_at=offset_retrieved)
    assert offset_provenance.retrieved_at == RETRIEVED
    assert offset_provenance.expires_at == RETRIEVED + timedelta(hours=24)
    assert evaluate_freshness(
        offset_provenance,
        now=(RETRIEVED + timedelta(hours=24, microseconds=1)).astimezone(zone),
    ) == evaluate_freshness(
        provenance(), now=RETRIEVED + timedelta(hours=24, microseconds=1)
    )


@pytest.mark.parametrize(
    "candidate",
    [
        provenance().model_copy(update={"expires_at": RETRIEVED + timedelta(hours=23)}),
        provenance().model_copy(
            update={"retrieved_at": RETRIEVED.replace(tzinfo=None)}
        ),
        provenance().model_copy(
            update={
                "expires_at": (RETRIEVED + timedelta(hours=24)).replace(tzinfo=None)
            }
        ),
        provenance().model_copy(update={"retrieved_at": RETRIEVED + timedelta(days=1)}),
    ],
)
def test_invalid_provenance_fails_closed(candidate):
    result = evaluate_freshness(candidate, now=RETRIEVED)
    assert result.state is None
    assert result.failure_reason is FreshnessFailureReason.INVALID_CHRONOLOGY


def test_future_retrieval_and_naive_now_fail_closed():
    future = evaluate_freshness(provenance(), now=RETRIEVED - timedelta(microseconds=1))
    naive = evaluate_freshness(provenance(), now=RETRIEVED.replace(tzinfo=None))
    assert future.failure_reason is FreshnessFailureReason.INVALID_CHRONOLOGY
    assert naive.failure_reason is FreshnessFailureReason.INVALID_CHRONOLOGY


def test_p1_fact_and_provenance_factory_preserves_validated_identity():
    p1_provenance = DynamicSourceProvenance(
        source_id="frigate-github-latest-release-v1",
        source_type="github_latest_release",
        origin_class="public_https_allowlisted",
        trust_tier="supplemental",
        repository="blakeblackshear/frigate",
        upstream_release_id=42,
        retrieved_at=RETRIEVED,
        expires_at=RETRIEVED + timedelta(hours=24),
        response_etag='"p1"',
        api_version="2022-11-28",
    )
    claim = EvaluatedDynamicClaim.from_p1(
        fact=fact(), provenance=p1_provenance, now=RETRIEVED
    )
    assert claim.provenance.source_id == "frigate-github-latest-release-v1"
    assert claim.freshness is FreshnessState.FRESH


def test_models_are_strict_closed_and_relationships_are_enforced():
    claim = dynamic()
    with pytest.raises(ValidationError):
        EvaluatedDynamicClaim.model_validate({**claim.model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        EvaluatedDynamicClaim(**(claim.model_dump() | {"freshness": "stale"}))
    with pytest.raises(ValidationError):
        CuratedClaimProvenance(
            source_class="dynamic",
            source_id="source-one",
            trust_tier="curated",
        )


def test_empty_and_curated_only_evaluations():
    assert evaluate_release_conflict(curated_claim=None, dynamic_claims=()) is None
    result = evaluate_release_conflict(curated_claim=curated(), dynamic_claims=())
    assert result is not None and result.state is ConflictState.NONE


def test_one_dynamic_without_curated_is_none():
    claim = dynamic()
    result = evaluate_release_conflict(curated_claim=None, dynamic_claims=(claim,))
    assert result is not None
    assert result.state is ConflictState.NONE
    assert result.dynamic_claims == (claim,)


def test_multiple_dynamic_agreement_and_conflict_have_no_winner():
    one = dynamic("source-one")
    two = dynamic("source-two", release_id=2)
    agreement = evaluate_release_conflict(curated_claim=None, dynamic_claims=(two, one))
    assert agreement is not None
    assert agreement.state is ConflictState.AGREEMENT
    assert [claim.provenance.source_id for claim in agreement.dynamic_claims] == [
        "source-one",
        "source-two",
    ]

    conflict = evaluate_release_conflict(
        curated_claim=None,
        dynamic_claims=(one, dynamic("source-two", version="2.0.0", release_id=2)),
    )
    assert conflict is not None
    assert conflict.state is ConflictState.DYNAMIC_CONFLICT
    assert len(conflict.dynamic_claims) == 2
    assert "winner" not in conflict.model_dump()


def test_curated_agreement_and_conflict_retain_all_claims():
    claims = (dynamic("source-one"), dynamic("source-two", release_id=2))
    agreement = evaluate_release_conflict(
        curated_claim=curated(), dynamic_claims=claims
    )
    assert agreement is not None and agreement.state is ConflictState.AGREEMENT
    conflict = evaluate_release_conflict(
        curated_claim=curated("9.9.9"), dynamic_claims=claims
    )
    assert conflict is not None
    assert conflict.state is ConflictState.CURATED_CONFLICT
    assert conflict.curated_claim == curated("9.9.9")
    assert conflict.dynamic_claims == claims


def test_mixed_fresh_stale_and_expired_behavior():
    fresh = dynamic("source-one", now=RETRIEVED)
    stale_same = dynamic(
        "source-two",
        now=RETRIEVED + timedelta(days=2),
        release_id=2,
    )
    stale_different = dynamic(
        "source-three",
        version="2.0.0",
        now=RETRIEVED + timedelta(days=2),
        release_id=3,
    )
    expired = dynamic(
        "source-four",
        now=RETRIEVED + timedelta(days=31),
        release_id=4,
    )
    agreement = evaluate_release_conflict(
        curated_claim=None, dynamic_claims=(stale_same, fresh, expired)
    )
    assert agreement is not None and agreement.state is ConflictState.AGREEMENT
    assert [claim.freshness for claim in agreement.dynamic_claims] == [
        FreshnessState.FRESH,
        FreshnessState.STALE,
    ]
    conflict = evaluate_release_conflict(
        curated_claim=None, dynamic_claims=(fresh, stale_different)
    )
    assert conflict is not None and conflict.state is ConflictState.DYNAMIC_CONFLICT
    assert (
        evaluate_release_conflict(curated_claim=None, dynamic_claims=(expired,)) is None
    )
    curated_only = evaluate_release_conflict(
        curated_claim=curated(), dynamic_claims=(expired,)
    )
    assert curated_only is not None
    assert curated_only.state is ConflictState.NONE
    assert curated_only.dynamic_claims == ()


def test_all_permutations_are_identical():
    claims = (
        dynamic("source-three", version="3.0.0", release_id=3),
        dynamic("source-one"),
        dynamic("source-two", version="2.0.0", release_id=2),
    )
    expected = evaluate_release_conflict(curated_claim=None, dynamic_claims=claims)
    for permutation in itertools.permutations(claims):
        assert (
            evaluate_release_conflict(curated_claim=None, dynamic_claims=permutation)
            == expected
        )


def test_exact_duplicate_is_deduplicated_and_digest_is_stable():
    claim = dynamic()
    result = evaluate_release_conflict(
        curated_claim=None, dynamic_claims=(claim, claim)
    )
    assert result is not None and result.dynamic_claims == (claim,)
    assert _claim_digest(claim) == _claim_digest(claim.model_copy())

    offset = timezone(timedelta(hours=5, minutes=30))
    equivalent = EvaluatedDynamicClaim.model_validate(
        claim.model_dump()
        | {
            "fact": claim.fact.model_dump()
            | {"published_at": claim.fact.published_at.astimezone(offset)},
            "provenance": claim.provenance.model_dump()
            | {
                "retrieved_at": claim.provenance.retrieved_at.astimezone(offset),
                "expires_at": claim.provenance.expires_at.astimezone(offset),
            },
            "evaluated_at": claim.evaluated_at.astimezone(offset),
        }
    )
    assert equivalent == claim
    assert _claim_digest(equivalent) == _claim_digest(claim)


def test_contradictory_duplicate_identity_is_rejected():
    one = dynamic()
    contradictory = dynamic(version="2.0.0")
    with pytest.raises(ClaimEvaluationError, match="contradictory duplicate"):
        evaluate_release_conflict(
            curated_claim=None, dynamic_claims=(one, contradictory)
        )


@pytest.mark.parametrize(
    "change",
    [
        {"fact": fact(published_at=PUBLISHED + timedelta(seconds=1))},
        {"provenance": provenance(release_id=2)},
        {
            "provenance": provenance().model_copy(
                update={"response_etag": '"different"'}
            )
        },
        {"provenance": provenance().model_copy(update={"api_version": "2023-01-01"})},
        {"evaluated_at": RETRIEVED + timedelta(hours=1)},
    ],
)
def test_same_source_retrieval_with_any_evidence_difference_is_contradictory(change):
    one = dynamic()
    contradictory = EvaluatedDynamicClaim.model_validate(one.model_dump() | change)
    with pytest.raises(ClaimEvaluationError, match="contradictory duplicate"):
        evaluate_release_conflict(
            curated_claim=None, dynamic_claims=(one, contradictory)
        )


def test_invalid_expired_claim_is_revalidated_before_exclusion():
    expired = dynamic(now=RETRIEVED + timedelta(days=31))
    bypassed = expired.model_copy(update={"evaluated_at": RETRIEVED})
    with pytest.raises(ValidationError, match="freshness does not match"):
        evaluate_release_conflict(curated_claim=None, dynamic_claims=(bypassed,))


def test_result_model_rejects_contradictory_duplicate_identity_directly():
    one = dynamic()
    contradictory = dynamic(version="2.0.0")
    valid = evaluate_release_conflict(
        curated_claim=None,
        dynamic_claims=(one, dynamic("source-two", version="2.0.0")),
    )
    assert valid is not None
    with pytest.raises(ValidationError, match="identities must be unique"):
        ConflictEvaluation(
            schema_version="discovery-release-conflict-evaluation-v1",
            key=valid.key,
            state=ConflictState.DYNAMIC_CONFLICT,
            dynamic_claims=tuple(sorted((one, contradictory), key=_claim_sort_key)),
        )


def test_claims_with_different_keys_are_rejected():
    one = dynamic()
    other = one.model_copy(
        update={
            "fact": one.fact.model_copy(update={"catalog_item_id": "other"}),
        }
    )
    with pytest.raises((ClaimEvaluationError, ValidationError)):
        evaluate_release_conflict(curated_claim=None, dynamic_claims=(one, other))
