"""Adversarial tests for the closed v0.65 control-plane contract."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.control_plane.contract import (
    ControlPlaneInputV1,
    ControlPlaneLineageV1,
    ControlPlanePolicyV1,
    evaluate_control_plane,
    input_fingerprint,
    lineage_fingerprint,
    policy_fingerprint,
)

NOW = "2026-09-23T12:00:00Z"
LATER = "2026-09-23T12:01:00Z"
PREDECESSOR = "a" * 64


def _lineage() -> ControlPlaneLineageV1:
    raw = {"lineage_id": "lineage-1", "predecessor_fingerprint": PREDECESSOR}
    raw["lineage_fingerprint"] = lineage_fingerprint(raw)
    return ControlPlaneLineageV1.model_validate(raw)


def _input() -> ControlPlaneInputV1:
    raw = {"subject_id": "subject-1", "lineage": _lineage(), "policy": ControlPlanePolicyV1(), "observed_fingerprint": "0" * 64, "observed_at": NOW, "valid_until": LATER}
    raw["observed_fingerprint"] = input_fingerprint(raw)
    return ControlPlaneInputV1.model_validate(raw)


def test_valid_evaluation_is_reference_only_and_deterministic() -> None:
    item = _input()
    kwargs = {"expected_lineage_fingerprint": item.lineage.lineage_fingerprint, "expected_policy_fingerprint": policy_fingerprint(item.policy), "evaluated_at": NOW}
    result = evaluate_control_plane(item, **kwargs)
    assert result.outcome == "accepted"
    assert result.authority_granted is False
    assert result.payload_bytes == 0
    assert result == evaluate_control_plane(item, **kwargs)


@pytest.mark.parametrize("field", ["command", "payload"])
def test_authority_bearing_payload_is_blocked(field: str) -> None:
    raw = deepcopy(_input().model_dump())
    raw[field] = "run"
    result = evaluate_control_plane(raw, expected_lineage_fingerprint="a" * 64, expected_policy_fingerprint="b" * 64, evaluated_at=NOW)
    assert result.outcome == "blocked"
    assert result.reason == "authority_payload"


def test_unknown_fields_and_policy_widening_are_rejected() -> None:
    raw = _input().model_dump()
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        ControlPlaneInputV1.model_validate(raw)
    with pytest.raises(ValidationError):
        ControlPlanePolicyV1(max_items=1)


def test_foreign_lineage_and_expiry_fail_closed() -> None:
    item = _input()
    foreign = evaluate_control_plane(item, expected_lineage_fingerprint="b" * 64, expected_policy_fingerprint=policy_fingerprint(item.policy), evaluated_at=NOW)
    assert foreign.reason == "foreign_lineage"
    expired = evaluate_control_plane(item, expected_lineage_fingerprint=item.lineage.lineage_fingerprint, expected_policy_fingerprint=policy_fingerprint(item.policy), evaluated_at=LATER)
    assert expired.reason == "expired"


def test_models_are_immutable_and_do_not_alias_mutable_inputs() -> None:
    raw = _input().model_dump()
    item = ControlPlaneInputV1.model_validate(raw)
    raw["subject_id"] = "changed"
    assert item.subject_id == "subject-1"
    with pytest.raises(ValidationError):
        item.subject_id = "changed"
