import hashlib
import json

import pytest

from app.n183e_direct_probe_helper import (
    PROBE_DOMAIN,
    PROBE_OUTCOMES,
    build_direct_probe_receipt,
)

TARGET = "target:atlas-core:direct-probe"
OUTCOME = "reached"


def _expected_receipt(target: str, outcome: str) -> str:
    canonical = json.dumps(
        {"outcome": outcome, "target": target},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROBE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()


def test_receipt_is_deterministic() -> None:
    first = build_direct_probe_receipt(target=TARGET, outcome=OUTCOME)
    second = build_direct_probe_receipt(target=TARGET, outcome=OUTCOME)

    assert first == second
    assert first == _expected_receipt(TARGET, OUTCOME)


def test_receipt_is_lowercase_sha256_hex() -> None:
    receipt = build_direct_probe_receipt(target=TARGET, outcome=OUTCOME)

    assert len(receipt) == 64
    assert all(character in "0123456789abcdef" for character in receipt)


def test_receipt_changes_when_any_field_changes() -> None:
    baseline = build_direct_probe_receipt(target=TARGET, outcome=OUTCOME)

    changed_target = build_direct_probe_receipt(
        target="target:atlas-core:direct-probe:retry",
        outcome=OUTCOME,
    )
    changed_outcome = build_direct_probe_receipt(
        target=TARGET,
        outcome="unreachable",
    )

    assert changed_target != baseline
    assert changed_outcome != baseline


def test_supported_outcomes_are_exactly_reached_and_unreachable() -> None:
    assert PROBE_OUTCOMES == ("reached", "unreachable")


@pytest.mark.parametrize(
    "target",
    [
        "",
        "  ",
        "target:\u00e9",
        "target:atlas-core:direct-probe\n",
        " target:atlas-core:direct-probe",
    ],
)
def test_rejects_invalid_target(target: str) -> None:
    with pytest.raises(ValueError):
        build_direct_probe_receipt(target=target, outcome=OUTCOME)


@pytest.mark.parametrize(
    "outcome",
    ["", "  ", "REACHED", "Reached", "ok", "fail", "timeout", "\u00e9"],
)
def test_rejects_unsupported_outcome(outcome: str) -> None:
    with pytest.raises(ValueError):
        build_direct_probe_receipt(target=TARGET, outcome=outcome)
