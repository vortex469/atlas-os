import hashlib
import json

import pytest

from app.n17_smoke_helper import (
    SMOKE_DOMAIN,
    SMOKE_RESULTS,
    build_smoke_receipt,
)

STAGE = "n17:smoke"
RESULT = "ok"


def _expected_receipt(stage: str, result: str) -> str:
    canonical = json.dumps(
        {"result": result, "stage": stage},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        SMOKE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()


def test_receipt_is_deterministic() -> None:
    first = build_smoke_receipt(stage=STAGE, result=RESULT)
    second = build_smoke_receipt(stage=STAGE, result=RESULT)

    assert first == second
    assert first == _expected_receipt(STAGE, RESULT)


def test_receipt_is_lowercase_sha256_hex() -> None:
    receipt = build_smoke_receipt(stage=STAGE, result=RESULT)

    assert len(receipt) == 64
    assert all(character in "0123456789abcdef" for character in receipt)


def test_receipt_changes_when_any_field_changes() -> None:
    baseline = build_smoke_receipt(stage=STAGE, result=RESULT)

    changed_stage = build_smoke_receipt(
        stage="n17:smoke:retry",
        result=RESULT,
    )
    changed_result = build_smoke_receipt(
        stage=STAGE,
        result="fail",
    )

    assert changed_stage != baseline
    assert changed_result != baseline


def test_supported_results_are_exactly_ok_and_fail() -> None:
    assert SMOKE_RESULTS == ("ok", "fail")


@pytest.mark.parametrize(
    "stage",
    ["", "  ", "n17:\u00e9", "n17:smoke\n", " n17:smoke"],
)
def test_rejects_invalid_stage(stage: str) -> None:
    with pytest.raises(ValueError):
        build_smoke_receipt(stage=stage, result=RESULT)


@pytest.mark.parametrize(
    "result",
    ["", "  ", "OK", "Ok", "pass", "passed", "FAIL", "\u00e9"],
)
def test_rejects_unsupported_result(result: str) -> None:
    with pytest.raises(ValueError):
        build_smoke_receipt(stage=STAGE, result=result)
