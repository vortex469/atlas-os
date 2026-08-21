from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.discovery.release_evaluation import (
    ReleaseEvaluationBaseline,
    ReleaseEvaluationBaselineSource,
    ReleaseEvaluationFreshness,
    ReleaseEvaluationResult,
    ReleaseEvaluationStatus,
    evaluate_release,
    parse_strict_numeric_version,
)

FRESH = ReleaseEvaluationFreshness.FRESH
STALE = ReleaseEvaluationFreshness.STALE
S = ReleaseEvaluationStatus


def evaluate(
    *,
    item_version: str | None = "0.15.0",
    curated: str | None = None,
    conflicted: bool = False,
    evidence: tuple[tuple[str, ReleaseEvaluationFreshness], ...] = (),
) -> ReleaseEvaluationResult:
    return evaluate_release(
        item_version=item_version,
        curated_release_version=curated,
        conflicted=conflicted,
        evidence=evidence,
    )


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("0.10.0", (0, 10, 0)),
        ("0.16.1", (0, 16, 1)),
        ("0.0.0", (0, 0, 0)),
        ("999999999.1.1", (999999999, 1, 1)),
        ("2147483647.0.0", (2147483647, 0, 0)),
    ],
)
def test_parse_strict_numeric_version_accepts(version, expected) -> None:
    assert parse_strict_numeric_version(version) == expected


@pytest.mark.parametrize(
    "version",
    [
        None,
        "",
        "1",
        "1.2",
        "1.2.3.4",
        "1.2.3-rc.1",
        "1.2.3+build.1",
        "1.2.3.4rc1",
        " 1.2.3",
        "1.2.3 ",
        "1.2. 3",
        "01.2.3.4",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "007.0.1",
        "1.a.3",
        "1.2.x",
        "v1.2.3",
        "1.-2.3",
        "1.2.-3",
        "1.2.3\r",
        "١.2.3",
        "2147483648.0.0",
        "1.2147483648.3",
        "1.2.2147483648",
    ],
)
def test_parse_strict_numeric_version_rejects(version) -> None:
    assert parse_strict_numeric_version(version) is None


def test_parse_rejects_non_ascii_digits() -> None:
    assert parse_strict_numeric_version("\u00b2.2.3") is None
    assert parse_strict_numeric_version("1.\u0662.3") is None


def test_parse_rejects_leading_zero_components_but_allows_zero() -> None:
    # Exact "0" is a valid component; anything with a leading zero is not strict.
    assert parse_strict_numeric_version("0.0.0") == (0, 0, 0)
    for version in ("1.2.03", "01.2.3", "1.02.3", "007.0.1", "0.10.01"):
        assert parse_strict_numeric_version(version) is None


@pytest.mark.parametrize(
    "leading_zero_version",
    ["1.2.03", "01.2.3", "1.02.3"],
)
def test_leading_zero_versions_are_non_comparable_and_fail_closed(
    leading_zero_version,
) -> None:
    # A leading-zero version can never yield a positive status, whether it
    # appears as the baseline or as fresh candidate evidence.
    result = evaluate(
        item_version=leading_zero_version,
        evidence=(("1.2.3", FRESH),),
    )
    assert result.status is S.INSUFFICIENT_INFORMATION
    assert result.status not in {S.UP_TO_DATE, S.UPDATE_AVAILABLE, S.BASELINE_AHEAD}
    assert result.reason is not None

    candidate_result = evaluate(
        item_version="1.2.3",
        evidence=((leading_zero_version, FRESH),),
    )
    assert candidate_result.status is S.INSUFFICIENT_INFORMATION
    assert candidate_result.status not in {
        S.UP_TO_DATE,
        S.UPDATE_AVAILABLE,
        S.BASELINE_AHEAD,
    }
    assert candidate_result.reason is not None


def test_baseline_ahead_uses_only_fresh_candidates_ignoring_stale_high() -> None:
    # Fresh 0.14.0 with stale 9.9.9 against baseline 0.15.0: the stale 9.9.9
    # must not be selected; only 0.14.0 is compared, and it is behind 0.15.0.
    result = evaluate(
        item_version="0.15.0",
        evidence=(("0.14.0", FRESH), ("9.9.9", STALE)),
    )
    assert result.status is S.BASELINE_AHEAD
    assert result.latest_candidate == "0.14.0"
    assert result.baseline is not None
    assert result.baseline.version == "0.15.0"
    assert result.reason is None


def test_conflict_beats_stale_evidence() -> None:
    # A conflict reports CONFLICTED even when only stale evidence is present;
    # conflict takes precedence over the stale-evidence bounded state.
    result = evaluate(
        item_version="0.15.0",
        conflicted=True,
        evidence=(("9.9.9", STALE), ("0.1.0", STALE)),
    )
    assert result.status is S.CONFLICTED
    assert result.latest_candidate is None
    assert result.reason is not None


def test_baseline_precedence_curated_over_item_version() -> None:
    result = evaluate(curated="0.16.0", evidence=(("0.16.0", FRESH),))
    assert result.status is S.UP_TO_DATE
    assert result.baseline == ReleaseEvaluationBaseline(
        version="0.16.0", source=ReleaseEvaluationBaselineSource.CURATED
    )
    assert result.latest_candidate == "0.16.0"


def test_baseline_from_item_version_when_no_curated_claim() -> None:
    result = evaluate(item_version="0.15.0", evidence=(("0.15.0", FRESH),))
    assert result.status is S.UP_TO_DATE
    assert result.baseline == ReleaseEvaluationBaseline(
        version="0.15.0", source=ReleaseEvaluationBaselineSource.ITEM_VERSION
    )


def test_no_baseline_without_curated_claim_or_item_version() -> None:
    result = evaluate(
        item_version=None,
        evidence=(("1.0.0", FRESH), ("2.0.0", STALE)),
    )
    assert result.status is S.NO_BASELINE
    assert result.baseline is None
    assert result.latest_candidate is None
    assert result.reason is not None


def test_conflict_takes_precedence_over_no_baseline() -> None:
    # A contradictory set of claims is CONFLICTED even when no baseline exists;
    # the no-baseline bounded state must not mask the conflict.
    result = evaluate(
        item_version=None,
        curated=None,
        conflicted=True,
        evidence=(("9.0.0", FRESH), ("10.0.0", FRESH)),
    )
    assert result.status is S.CONFLICTED
    assert result.baseline is None
    assert result.latest_candidate is None
    assert result.reason is not None


def test_curated_conflict_reports_conflicted_without_candidate() -> None:
    result = evaluate(
        curated="0.16.0",
        conflicted=True,
        evidence=(("9.9.9", FRESH), ("0.1.0", STALE)),
    )
    assert result.status is S.CONFLICTED
    assert result.baseline is not None
    assert result.baseline.version == "0.16.0"
    assert result.latest_candidate is None
    assert result.reason is not None


def test_dynamic_conflict_also_reports_conflicted() -> None:
    result = evaluate(
        item_version="0.15.0",
        conflicted=True,
        evidence=(("0.15.0", FRESH),),
    )
    assert result.status is S.CONFLICTED
    assert result.latest_candidate is None


def test_no_dynamic_evidence_reports_bounded_state() -> None:
    result = evaluate(item_version="0.15.0")
    assert result.status is S.NO_DYNAMIC_EVIDENCE
    assert result.baseline is not None
    assert result.latest_candidate is None
    assert result.reason is not None


def test_stale_only_evidence_is_stale_and_never_positive() -> None:
    result = evaluate(
        item_version="0.15.0",
        evidence=(("9.9.9", STALE), ("0.0.1", STALE)),
    )
    assert result.status is S.STALE_EVIDENCE
    assert result.latest_candidate is None
    assert result.reason is not None


def test_non_positive_states_are_bounded_without_candidate() -> None:
    cases = [
        evaluate(item_version=None, curated=None),
        evaluate(item_version="0.15.0", conflicted=True),
        evaluate(item_version="0.15.0", evidence=()),
        evaluate(item_version="0.15.0", evidence=(("1.0.0", STALE),)),
        evaluate(item_version="latest", evidence=(("1.0.0", FRESH),)),
        evaluate(item_version="0.15.0", evidence=(("v1.2.3", FRESH),)),
    ]
    for result in cases:
        assert result.status in {
            S.NO_BASELINE,
            S.CONFLICTED,
            S.NO_DYNAMIC_EVIDENCE,
            S.STALE_EVIDENCE,
            S.INSUFFICIENT_INFORMATION,
        }
        assert result.status not in {S.UP_TO_DATE, S.UPDATE_AVAILABLE, S.BASELINE_AHEAD}
        assert result.reason is not None


def test_non_strict_baseline_is_insufficient_information() -> None:
    for baseline in ("latest", "1.2", "1.2.3-rc.1", "v1.2.3", "1.2.3.4", "1.2.3 "):
        result = evaluate(item_version=baseline, evidence=(("1.0.0", FRESH),))
        assert result.status is S.INSUFFICIENT_INFORMATION
        assert result.baseline is not None
        assert result.baseline.version == baseline
        assert result.latest_candidate is None or result.latest_candidate == "1.0.0"
        assert result.reason is not None


def test_non_strict_fresh_candidate_without_any_numeric_candidate() -> None:
    result = evaluate(
        item_version="1.2.3",
        evidence=(("v2.0.0", FRESH), ("2.0.0-rc.1", STALE)),
    )
    assert result.status is S.INSUFFICIENT_INFORMATION
    assert result.latest_candidate is None
    assert result.reason is not None


def test_update_available_when_fresh_candidate_is_newer() -> None:
    result = evaluate(
        item_version="0.15.0",
        evidence=(("0.16.0", FRESH), ("0.14.0", FRESH)),
    )
    assert result.status is S.UPDATE_AVAILABLE
    assert result.latest_candidate == "0.16.0"
    assert result.reason is None


def test_baseline_ahead_when_fresh_candidate_is_older() -> None:
    result = evaluate(
        item_version="0.16.0",
        evidence=(("0.15.9", FRESH), ("0.15.0", FRESH)),
    )
    assert result.status is S.BASELINE_AHEAD
    assert result.latest_candidate == "0.15.9"
    assert result.reason is None


def test_up_to_date_when_fresh_candidate_matches_baseline() -> None:
    result = evaluate(
        item_version="0.15.0",
        evidence=(("0.15.0", FRESH), ("0.15.0", FRESH)),
    )
    assert result.status is S.UP_TO_DATE
    assert result.latest_candidate == "0.15.0"
    assert result.reason is None


def test_numeric_not_lexicographic_ordering_selects_true_maximum() -> None:
    result = evaluate(
        item_version="0.1.0",
        evidence=(
            ("0.10.0", FRESH),
            ("0.9.9", FRESH),
            ("0.2.0", FRESH),
        ),
    )
    assert result.status is S.UPDATE_AVAILABLE
    assert result.latest_candidate == "0.10.0"


def test_numeric_ordering_handles_major_and_patch_components() -> None:
    result = evaluate(
        item_version="1.0.0",
        evidence=(
            ("2.0.0", FRESH),
            ("1.10.0", FRESH),
            ("1.9.9", FRESH),
            ("1.0.10", FRESH),
        ),
    )
    assert result.status is S.UPDATE_AVAILABLE
    assert result.latest_candidate == "2.0.0"
    assert (
        parse_strict_numeric_version("2.0.0")
        > parse_strict_numeric_version("1.10.0")
        > parse_strict_numeric_version("1.9.9")
        > parse_strict_numeric_version("1.0.10")
        > parse_strict_numeric_version("1.0.9")
    )


def test_stale_observations_never_influence_selection_or_status() -> None:
    result = evaluate(
        item_version="0.15.0",
        evidence=(("0.15.0", FRESH), ("99.0.0", STALE)),
    )
    assert result.status is S.UP_TO_DATE
    assert result.latest_candidate == "0.15.0"


def test_non_numeric_fresh_observations_are_skipped_over_numeric() -> None:
    result = evaluate(
        item_version="1.0.0",
        evidence=(("v2.0.0", FRESH), ("1.1.0", FRESH)),
    )
    assert result.status is S.UPDATE_AVAILABLE
    assert result.latest_candidate == "1.1.0"


def test_deterministic_for_identical_inputs_and_input_order_independent() -> None:
    first = evaluate(
        item_version="0.15.0",
        evidence=(("0.16.0", FRESH), ("0.15.0", FRESH), ("0.10.0", STALE)),
    )
    for _ in range(2):
        assert evaluate(
            item_version="0.15.0",
            evidence=(
                ("0.10.0", STALE),
                ("0.16.0", FRESH),
                ("0.15.0", FRESH),
            ),
        ).model_dump() == first.model_dump()


def test_results_are_frozen_and_round_trip() -> None:
    result = evaluate(item_version="0.15.0", evidence=(("0.16.0", FRESH),))
    json_payload = result.model_dump(mode="json")
    assert json_payload["status"] == "update_available"
    assert json_payload["baseline"] == {
        "version": "0.15.0",
        "source": "item_version",
    }
    assert json_payload["latest_candidate"] == "0.16.0"
    restored = ReleaseEvaluationResult.model_validate(result.model_dump())
    assert restored == result
    with pytest.raises((TypeError, ValidationError)):
        result.status = S.UP_TO_DATE  # type: ignore[misc]


def test_status_enum_is_exactly_bounded() -> None:
    assert {status.value for status in ReleaseEvaluationStatus} == {
        "no_baseline",
        "no_dynamic_evidence",
        "insufficient_information",
        "stale_evidence",
        "conflicted",
        "up_to_date",
        "update_available",
        "baseline_ahead",
    }


def test_freshness_enum_is_exactly_bounded() -> None:
    assert {freshness.value for freshness in ReleaseEvaluationFreshness} == {
        "fresh",
        "stale",
    }
