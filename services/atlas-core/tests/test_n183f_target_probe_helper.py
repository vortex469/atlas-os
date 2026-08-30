import hashlib
import json

import pytest

from app.n183f_target_probe_helper import (
    PROBE_DOMAIN,
    PROBE_OUTCOMES,
    build_target_aware_probe_receipt,
)

TARGET = "target:atlas-core:target-aware-probe"
EXPECTED = "reached"
OBSERVED = "reached"


def _expected_receipt(
    target: str, expected_outcome: str, observed_outcome: str
) -> str:
    canonical = json.dumps(
        {
            "expected_outcome": expected_outcome,
            "observed_outcome": observed_outcome,
            "target": target,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROBE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()


def test_receipt_is_deterministic() -> None:
    first = build_target_aware_probe_receipt(
        target=TARGET, expected_outcome=EXPECTED, observed_outcome=OBSERVED
    )
    second = build_target_aware_probe_receipt(
        target=TARGET, expected_outcome=EXPECTED, observed_outcome=OBSERVED
    )

    assert first == second
    assert first == _expected_receipt(TARGET, EXPECTED, OBSERVED)


def test_receipt_is_lowercase_sha256_hex() -> None:
    receipt = build_target_aware_probe_receipt(
        target=TARGET, expected_outcome=EXPECTED, observed_outcome=OBSERVED
    )

    assert len(receipt) == 64
    assert all(character in "0123456789abcdef" for character in receipt)


def test_receipt_changes_when_any_field_changes() -> None:
    baseline = build_target_aware_probe_receipt(
        target=TARGET, expected_outcome=EXPECTED, observed_outcome=OBSERVED
    )

    changed_target = build_target_aware_probe_receipt(
        target="target:atlas-core:target-aware-probe:retry",
        expected_outcome=EXPECTED,
        observed_outcome=OBSERVED,
    )
    changed_expected = build_target_aware_probe_receipt(
        target=TARGET,
        expected_outcome="unreachable",
        observed_outcome=OBSERVED,
    )
    changed_observed = build_target_aware_probe_receipt(
        target=TARGET,
        expected_outcome=EXPECTED,
        observed_outcome="unreachable",
    )

    assert changed_target != baseline
    assert changed_expected != baseline
    assert changed_observed != baseline


def test_supported_outcomes_are_exactly_reached_and_unreachable() -> None:
    assert PROBE_OUTCOMES == ("reached", "unreachable")


@pytest.mark.parametrize(
    "target",
    [
        "",
        "  ",
        "target:\u00e9",
        "target:atlas-core:target-aware-probe\n",
        " target:atlas-core:target-aware-probe",
    ],
)
def test_rejects_invalid_target(target: str) -> None:
    with pytest.raises(ValueError):
        build_target_aware_probe_receipt(
            target=target, expected_outcome=EXPECTED, observed_outcome=OBSERVED
        )


@pytest.mark.parametrize(
    "expected_outcome",
    ["", "  ", "REACHED", "Reached", "ok", "fail", "timeout", "\u00e9"],
)
def test_rejects_unsupported_expected_outcome(expected_outcome: str) -> None:
    with pytest.raises(ValueError):
        build_target_aware_probe_receipt(
            target=TARGET,
            expected_outcome=expected_outcome,
            observed_outcome=OBSERVED,
        )


@pytest.mark.parametrize(
    "observed_outcome",
    ["", "  ", "REACHED", "Reached", "ok", "fail", "timeout", "\u00e9"],
)
def test_rejects_unsupported_observed_outcome(observed_outcome: str) -> None:
    with pytest.raises(ValueError):
        build_target_aware_probe_receipt(
            target=TARGET,
            expected_outcome=EXPECTED,
            observed_outcome=observed_outcome,
        )
