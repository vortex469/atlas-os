import hashlib
import json

import pytest

from app.n223_backlog_probe import (
    BACKLOG_VERDICTS,
    PROOF_DOMAIN,
    build_backlog_binding_proof,
)

BACKLOG_ITEM = "backlog:atlas-core:n22.3"
BINDING_TARGET = "binding:atlas-core:coding-job"
VERDICT = "bound"


def _expected_proof(
    backlog_item: str, binding_target: str, observed_verdict: str
) -> str:
    canonical = json.dumps(
        {
            "backlog_item": backlog_item,
            "binding_target": binding_target,
            "observed_verdict": observed_verdict,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROOF_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()


def test_proof_is_deterministic() -> None:
    first = build_backlog_binding_proof(
        backlog_item=BACKLOG_ITEM,
        binding_target=BINDING_TARGET,
        observed_verdict=VERDICT,
    )
    second = build_backlog_binding_proof(
        backlog_item=BACKLOG_ITEM,
        binding_target=BINDING_TARGET,
        observed_verdict=VERDICT,
    )

    assert first == second
    assert first == _expected_proof(BACKLOG_ITEM, BINDING_TARGET, VERDICT)


def test_proof_is_lowercase_sha256_hex() -> None:
    proof = build_backlog_binding_proof(
        backlog_item=BACKLOG_ITEM,
        binding_target=BINDING_TARGET,
        observed_verdict=VERDICT,
    )

    assert len(proof) == 64
    assert all(character in "0123456789abcdef" for character in proof)


def test_proof_changes_when_any_field_changes() -> None:
    baseline = build_backlog_binding_proof(
        backlog_item=BACKLOG_ITEM,
        binding_target=BINDING_TARGET,
        observed_verdict=VERDICT,
    )

    changed_item = build_backlog_binding_proof(
        backlog_item="backlog:atlas-core:n22.4",
        binding_target=BINDING_TARGET,
        observed_verdict=VERDICT,
    )
    changed_target = build_backlog_binding_proof(
        backlog_item=BACKLOG_ITEM,
        binding_target="binding:atlas-core:coding-job:retry",
        observed_verdict=VERDICT,
    )
    changed_verdict = build_backlog_binding_proof(
        backlog_item=BACKLOG_ITEM,
        binding_target=BINDING_TARGET,
        observed_verdict="unbound",
    )

    assert changed_item != baseline
    assert changed_target != baseline
    assert changed_verdict != baseline


def test_supported_verdicts_are_exactly_bound_and_unbound() -> None:
    assert BACKLOG_VERDICTS == ("bound", "unbound")


@pytest.mark.parametrize(
    "backlog_item",
    [
        "",
        "  ",
        "backlog:\u00e9",
        "backlog:atlas-core:n22.3\n",
        " backlog:atlas-core:n22.3",
    ],
)
def test_rejects_invalid_backlog_item(backlog_item: str) -> None:
    with pytest.raises(ValueError):
        build_backlog_binding_proof(
            backlog_item=backlog_item,
            binding_target=BINDING_TARGET,
            observed_verdict=VERDICT,
        )


@pytest.mark.parametrize(
    "binding_target",
    [
        "",
        "  ",
        "binding:\u00e9",
        "binding:atlas-core:coding-job\n",
        " binding:atlas-core:coding-job",
    ],
)
def test_rejects_invalid_binding_target(binding_target: str) -> None:
    with pytest.raises(ValueError):
        build_backlog_binding_proof(
            backlog_item=BACKLOG_ITEM,
            binding_target=binding_target,
            observed_verdict=VERDICT,
        )


@pytest.mark.parametrize(
    "observed_verdict",
    ["", "  ", "BOUND", "Bound", "ok", "fail", "timeout", "\u00e9"],
)
def test_rejects_unsupported_observed_verdict(observed_verdict: str) -> None:
    with pytest.raises(ValueError):
        build_backlog_binding_proof(
            backlog_item=BACKLOG_ITEM,
            binding_target=BINDING_TARGET,
            observed_verdict=observed_verdict,
        )
