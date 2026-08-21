"""Bounded, pure release-evaluation contract for one merged Discovery item.

This module is deterministic and side-effect free. It compares the
authoritative baseline version of an item against the freshest dynamic
release evidence and reports a bounded status plus, only when a positive
comparison is permitted, the latest candidate version considered.

Precedence:

- baseline: the curated release claim is authoritative over ``item.version``;
- any curated or dynamic conflict: ``CONFLICTED`` with no latest version
  selected, taking precedence over every state below it (including the
  no-baseline state);
- no baseline at all: ``NO_BASELINE``;
- no dynamic evidence: ``NO_DYNAMIC_EVIDENCE``;
- no fresh dynamic evidence: ``STALE_EVIDENCE`` and never a positive
  assertion;
- a non-strict baseline or no strict numeric fresh candidate:
  ``INSUFFICIENT_INFORMATION``;
- fresh, strict numeric evidence: ``UP_TO_DATE``, ``UPDATE_AVAILABLE``, or
  ``BASELINE_AHEAD``.

Only strict numeric ``X.Y.Z`` versions are comparable. A numeric component
carrying a leading zero (anything other than the exact value ``"0"``) is not
strict and is treated as non-comparable, so it can never yield a positive
status. The latest candidate is the fresh observation with the greatest
integer triple, compared as integer triples.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_NUMERIC_PART = 2**31 - 1


class ReleaseEvaluationFreshness(StrEnum):
    """Freshness of one dynamic release observation."""

    FRESH = "fresh"
    STALE = "stale"


class ReleaseEvaluationStatus(StrEnum):
    """Bounded release-evaluation states."""

    NO_BASELINE = "no_baseline"
    NO_DYNAMIC_EVIDENCE = "no_dynamic_evidence"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    STALE_EVIDENCE = "stale_evidence"
    CONFLICTED = "conflicted"
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    BASELINE_AHEAD = "baseline_ahead"


class ReleaseEvaluationBaselineSource(StrEnum):
    """Origin of the authoritative baseline version."""

    CURATED = "curated"
    ITEM_VERSION = "item_version"


class ReleaseEvaluationBaseline(BaseModel):
    """The authoritative baseline version and where it came from.

    The version is preserved as provided; comparability is reported by the
    evaluation status, so a non-strict baseline still yields a bounded result.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version: str = Field(min_length=1, max_length=64)
    source: ReleaseEvaluationBaselineSource


class ReleaseEvaluationResult(BaseModel):
    """Bounded, deterministic release evaluation for one merged item."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    status: ReleaseEvaluationStatus
    baseline: ReleaseEvaluationBaseline | None = None
    latest_candidate: str | None = Field(
        default=None, min_length=1, max_length=64
    )
    reason: str | None = None

    @field_validator("latest_candidate")
    @classmethod
    def validate_latest_candidate(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value != value.strip():
            raise ValueError("latest_candidate must not contain surrounding whitespace")
        return value


def parse_strict_numeric_version(version: str | None) -> tuple[int, int, int] | None:
    """Parse a strict numeric ``X.Y.Z`` version into an integer triple.

    Anything else, including pre-release suffixes, build metadata, whitespace,
    non-numeric parts, components with a leading zero (the exact value
    ``"0"`` is allowed), and out-of-range components, returns ``None``.
    """

    if version is None:
        return None
    parts = version.split(".")
    if len(parts) != 3:
        return None
    parsed: list[int] = []
    for part in parts:
        if not part or not part.isdigit() or not part.isascii():
            return None
        if part.startswith("0") and part != "0":
            return None
        value = int(part)
        if value > _MAX_NUMERIC_PART:
            return None
        parsed.append(value)
    return (parsed[0], parsed[1], parsed[2])


def _baseline(
    item_version: str | None, curated_version: str | None
) -> ReleaseEvaluationBaseline | None:
    if curated_version:
        return ReleaseEvaluationBaseline(
            version=curated_version,
            source=ReleaseEvaluationBaselineSource.CURATED,
        )
    if item_version:
        return ReleaseEvaluationBaseline(
            version=item_version,
            source=ReleaseEvaluationBaselineSource.ITEM_VERSION,
        )
    return None


def _select_latest_fresh(
    evidence: tuple[tuple[str, ReleaseEvaluationFreshness], ...],
) -> tuple[str, tuple[int, int, int]] | None:
    """Select the fresh observation with the greatest numeric version.

    Stale observations are never candidates. Returns ``(version, key)`` or
    ``None`` when no fresh observation parses as strict numeric ``X.Y.Z``.
    """

    best: tuple[tuple[int, int, int], str] | None = None
    for version, freshness in evidence:
        if freshness is not ReleaseEvaluationFreshness.FRESH:
            continue
        key = parse_strict_numeric_version(version)
        if key is None:
            continue
        candidate = (key, version)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None
    key, version = best
    return version, key


def _result(
    status: ReleaseEvaluationStatus,
    baseline: ReleaseEvaluationBaseline | None,
    latest_candidate: str | None = None,
    reason: str | None = None,
) -> ReleaseEvaluationResult:
    return ReleaseEvaluationResult(
        status=status,
        baseline=baseline,
        latest_candidate=latest_candidate,
        reason=reason,
    )


def evaluate_release(
    *,
    item_version: str | None,
    curated_release_version: str | None,
    conflicted: bool,
    evidence: tuple[tuple[str, ReleaseEvaluationFreshness], ...],
) -> ReleaseEvaluationResult:
    """Pure deterministic release evaluation from already-merged evidence.

    ``evidence`` holds one ``(version, freshness)`` observation per visible
    dynamic latest-stable-release claim, already bounded to fresh or stale.
    """

    baseline = _baseline(item_version, curated_release_version)
    if conflicted:
        # Conflict takes precedence over the no-baseline bounded state so a
        # contradictory set of claims always surfaces as CONFLICTED, with the
        # best-available baseline attached when one is present.
        return _result(
            ReleaseEvaluationStatus.CONFLICTED,
            baseline,
            reason="conflicting release claims",
        )
    if baseline is None:
        return _result(
            ReleaseEvaluationStatus.NO_BASELINE,
            None,
            reason="no baseline version",
        )
    if not evidence:
        return _result(
            ReleaseEvaluationStatus.NO_DYNAMIC_EVIDENCE,
            baseline,
            reason="no dynamic release evidence",
        )
    if not any(
        freshness is ReleaseEvaluationFreshness.FRESH
        for _, freshness in evidence
    ):
        return _result(
            ReleaseEvaluationStatus.STALE_EVIDENCE,
            baseline,
            reason="latest dynamic release evidence is stale",
        )
    selected = _select_latest_fresh(evidence)
    if selected is None:
        return _result(
            ReleaseEvaluationStatus.INSUFFICIENT_INFORMATION,
            baseline,
            reason="no fresh strict numeric X.Y.Z candidate",
        )
    candidate_version, candidate_key = selected
    baseline_key = parse_strict_numeric_version(baseline.version)
    if baseline_key is None:
        return _result(
            ReleaseEvaluationStatus.INSUFFICIENT_INFORMATION,
            baseline,
            latest_candidate=candidate_version,
            reason="baseline is not a strict numeric X.Y.Z version",
        )
    if candidate_key > baseline_key:
        status = ReleaseEvaluationStatus.UPDATE_AVAILABLE
    elif candidate_key < baseline_key:
        status = ReleaseEvaluationStatus.BASELINE_AHEAD
    else:
        status = ReleaseEvaluationStatus.UP_TO_DATE
    return _result(status, baseline, latest_candidate=candidate_version)
