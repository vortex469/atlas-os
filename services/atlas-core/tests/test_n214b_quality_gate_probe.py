import hashlib
import json

import pytest

from app.n214b_quality_gate_probe import (
    GATE_VERDICTS,
    PROOF_DOMAIN,
    build_quality_gate_proof,
)

GATE_ID = "gate:atlas-core:quality-gate"
VERDICT = "passed"


def _expected_proof(gate_id: str, observed_verdict: str) -> str:
    canonical = json.dumps(
        {"gate_id": gate_id, "observed_verdict": observed_verdict},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROOF_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()


def test_proof_is_deterministic() -> None:
    first = build_quality_gate_proof(gate_id=GATE_ID, observed_verdict=VERDICT)
    second = build_quality_gate_proof(gate_id=GATE_ID, observed_verdict=VERDICT)

    assert first == second
    assert first == _expected_proof(GATE_ID, VERDICT)


def test_proof_is_lowercase_sha256_hex() -> None:
    proof = build_quality_gate_proof(gate_id=GATE_ID, observed_verdict=VERDICT)

    assert len(proof) == 64
    assert all(character in "0123456789abcdef" for character in proof)


def test_proof_changes_when_any_field_changes() -> None:
    baseline = build_quality_gate_proof(gate_id=GATE_ID, observed_verdict=VERDICT)

    changed_gate = build_quality_gate_proof(
        gate_id="gate:atlas-core:quality-gate:retry",
        observed_verdict=VERDICT,
    )
    changed_verdict = build_quality_gate_proof(
        gate_id=GATE_ID,
        observed_verdict="failed",
    )

    assert changed_gate != baseline
    assert changed_verdict != baseline


def test_supported_verdicts_are_exactly_passed_and_failed() -> None:
    assert GATE_VERDICTS == ("passed", "failed")


@pytest.mark.parametrize(
    "gate_id",
    [
        "",
        "  ",
        "gate:\u00e9",
        "gate:atlas-core:quality-gate\n",
        " gate:atlas-core:quality-gate",
    ],
)
def test_rejects_invalid_gate_id(gate_id: str) -> None:
    with pytest.raises(ValueError):
        build_quality_gate_proof(gate_id=gate_id, observed_verdict=VERDICT)


@pytest.mark.parametrize(
    "observed_verdict",
    ["", "  ", "PASSED", "Passed", "ok", "fail", "timeout", "\u00e9"],
)
def test_rejects_unsupported_observed_verdict(observed_verdict: str) -> None:
    with pytest.raises(ValueError):
        build_quality_gate_proof(
            gate_id=GATE_ID,
            observed_verdict=observed_verdict,
        )
