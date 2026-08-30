import hashlib
import json

import pytest

from app.n190_readiness_probe import (
    PROBE_DOMAIN,
    PROBE_VERDICTS,
    build_readiness_probe_receipt,
)

TARGET = "target:atlas-core:readiness-probe"
CAPABILITY = "capability:atlas-core:readiness"
VERDICT = "ready"


def _expected_receipt(
    target: str, required_capability: str, observed_verdict: str
) -> str:
    canonical = json.dumps(
        {
            "observed_verdict": observed_verdict,
            "required_capability": required_capability,
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
    first = build_readiness_probe_receipt(
        target=TARGET,
        required_capability=CAPABILITY,
        observed_verdict=VERDICT,
    )
    second = build_readiness_probe_receipt(
        target=TARGET,
        required_capability=CAPABILITY,
        observed_verdict=VERDICT,
    )

    assert first == second
    assert first == _expected_receipt(TARGET, CAPABILITY, VERDICT)


def test_receipt_is_lowercase_sha256_hex() -> None:
    receipt = build_readiness_probe_receipt(
        target=TARGET,
        required_capability=CAPABILITY,
        observed_verdict=VERDICT,
    )

    assert len(receipt) == 64
    assert all(character in "0123456789abcdef" for character in receipt)


def test_receipt_changes_when_any_field_changes() -> None:
    baseline = build_readiness_probe_receipt(
        target=TARGET,
        required_capability=CAPABILITY,
        observed_verdict=VERDICT,
    )

    changed_target = build_readiness_probe_receipt(
        target="target:atlas-core:readiness-probe:retry",
        required_capability=CAPABILITY,
        observed_verdict=VERDICT,
    )
    changed_capability = build_readiness_probe_receipt(
        target=TARGET,
        required_capability="capability:atlas-core:readiness:strict",
        observed_verdict=VERDICT,
    )
    changed_verdict = build_readiness_probe_receipt(
        target=TARGET,
        required_capability=CAPABILITY,
        observed_verdict="not_ready",
    )

    assert changed_target != baseline
    assert changed_capability != baseline
    assert changed_verdict != baseline


def test_supported_verdicts_are_exactly_ready_and_not_ready() -> None:
    assert PROBE_VERDICTS == ("ready", "not_ready")


@pytest.mark.parametrize(
    "target",
    [
        "",
        "  ",
        "target:\u00e9",
        "target:atlas-core:readiness-probe\n",
        " target:atlas-core:readiness-probe",
    ],
)
def test_rejects_invalid_target(target: str) -> None:
    with pytest.raises(ValueError):
        build_readiness_probe_receipt(
            target=target,
            required_capability=CAPABILITY,
            observed_verdict=VERDICT,
        )


@pytest.mark.parametrize(
    "required_capability",
    [
        "",
        "  ",
        "capability:\u00e9",
        "capability:atlas-core:readiness\n",
        " capability:atlas-core:readiness",
    ],
)
def test_rejects_invalid_required_capability(required_capability: str) -> None:
    with pytest.raises(ValueError):
        build_readiness_probe_receipt(
            target=TARGET,
            required_capability=required_capability,
            observed_verdict=VERDICT,
        )


@pytest.mark.parametrize(
    "observed_verdict",
    ["", "  ", "READY", "Ready", "ok", "fail", "timeout", "\u00e9"],
)
def test_rejects_unsupported_observed_verdict(observed_verdict: str) -> None:
    with pytest.raises(ValueError):
        build_readiness_probe_receipt(
            target=TARGET,
            required_capability=CAPABILITY,
            observed_verdict=observed_verdict,
        )
