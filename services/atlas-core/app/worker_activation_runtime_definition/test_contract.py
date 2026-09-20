from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.worker_activation_runtime_definition import contract as c


def definition() -> c.WorkerActivationRuntimeDefinitionV1:
    raw = {
        "definition_id": "00000000-0000-5000-8000-000000000000",
        "operator_id": "operator-1",
        "candidate_record_id": "00000000-0000-4000-8000-000000000000",
        "runtime_name": "atlas-worker",
        "runtime_version": "1",
        "artifact_digest": "a" * 64,
        "capabilities": ("cpu", "memory", "pid", "filesystem"),
        "resources": {"cpu_millis": 100, "memory_bytes": 1024, "pid_limit": 10},
        "filesystem": {"writable_paths": ()},
        "network": {"mode": "none"},
        "valid_until": "2099-01-01T00:00:00Z",
    }
    raw["definition_fingerprint"] = c.definition_fingerprint(raw)
    return c.WorkerActivationRuntimeDefinitionV1.model_validate(raw)


def test_definition_is_closed_immutable_and_deterministic() -> None:
    value = definition()
    assert value == c.WorkerActivationRuntimeDefinitionV1.model_validate_json(
        value.model_dump_json()
    )
    with pytest.raises(ValidationError):
        value.runtime_name = "changed"
    with pytest.raises(ValidationError):
        c.WorkerActivationRuntimeDefinitionV1.model_validate(
            {**value.model_dump(mode="python"), "unexpected": "rejected"}
        )
    with pytest.raises(ValueError, match="duplicate"):
        c.WorkerActivationRuntimeDefinitionV1.model_validate_json(
            b'{"schema":"worker-activation-runtime-definition-v1","schema":"duplicate"}'
        )


def test_evaluation_is_pure_and_never_grants_effect_authority() -> None:
    value = definition()
    raw = value.model_dump(mode="python")
    before = copy.deepcopy(raw)
    result = c.evaluate_worker_activation_runtime_definition(
        raw, evaluated_at="2026-01-01T00:00:00Z"
    )
    assert raw == before
    assert result.state == "recorded"
    assert result.eligibility == c.MARKER
    assert result.evaluation_fingerprint == c.evaluation_fingerprint(result)
    assert value.runtime_effect_allowed is False
    assert value.worker_start_allowed is False
    assert value.activation_allowed is False


def test_incompatible_network_and_expired_definition_refuse() -> None:
    value = definition().model_dump(mode="python")
    value["network"] = {"mode": "allowlist", "egress_hosts": ()}
    with pytest.raises(ValidationError):
        c.WorkerActivationRuntimeDefinitionV1.model_validate(value)
    expired_raw = definition().model_dump(mode="python")
    expired_raw["valid_until"] = "2020-01-01T00:00:00Z"
    expired_raw["definition_fingerprint"] = c.definition_fingerprint(expired_raw)
    expired = c.WorkerActivationRuntimeDefinitionV1.model_validate(expired_raw)
    result = c.evaluate_worker_activation_runtime_definition(
        expired, evaluated_at="2026-01-01T00:00:00Z"
    )
    assert result.state == "blocked"
