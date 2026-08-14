"""Contract tests for side-effect-free operational translation."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.candidate_planning.models import (
    OPERATIONAL_EXECUTION_INTENTS,
    operational_action_request_digest,
)
from app.candidate_planning.operational import operational_plan_fingerprint
from app.candidate_planning.operational_translation import (
    translate_operational_action_request,
)
from app.workflow.models import WorkflowEffectKind
from tests.candidate_planning.test_operational_models import operational_plan

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def translate(plan=None, *, supplied_action=None):
    return translate_operational_action_request(
        plan=plan or operational_plan(),
        workflow_session_id="workflow-1",
        generated_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        supplied_provider_action_id=supplied_action,
    )


def test_plan_fingerprint_binds_target_and_verification() -> None:
    plan = operational_plan()
    assert operational_plan_fingerprint(plan) == operational_plan_fingerprint(plan)
    assert operational_plan_fingerprint(plan) != operational_plan_fingerprint(
        replace(plan, target_fingerprint="sha256:replaced")
    )
    assert operational_plan_fingerprint(plan) != operational_plan_fingerprint(
        replace(
            plan,
            verification=replace(plan.verification, health_requirement="ready"),
        )
    )


def test_translation_is_deterministic_immutable_and_narrowly_enabled() -> None:
    first = translate()
    repeated = translate()
    assert first == repeated
    assert first.request_digest == operational_action_request_digest(first)
    assert first.idempotency_key == repeated.idempotency_key
    assert first.provider_action_id == "proxmox-qemu-graceful-restart-v1"
    assert OPERATIONAL_EXECUTION_INTENTS == frozenset({"restart-service"})
    with pytest.raises(FrozenInstanceError):
        first.resource_id = "qemu/999"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("candidate_fingerprint", "candidate-fingerprint-v1:changed"),
        ("target_fingerprint", "sha256:changed"),
        ("resource_id", "qemu/102"),
    ],
)
def test_security_relevant_changes_change_digest(change: str, value: str) -> None:
    original = translate()
    changed = translate(replace(operational_plan(), **{change: value}))
    assert original.request_digest != changed.request_digest
    assert original.idempotency_key != changed.idempotency_key


def test_closed_mapping_rejects_unsupported_and_injected_actions() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        translate(replace(operational_plan(), provider_id="docker"))
    with pytest.raises(ValueError, match="closed translation"):
        translate(supplied_action="attacker-selected-action")
    with pytest.raises(ValueError, match="effect kind"):
        translate(replace(operational_plan(), effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE))
    with pytest.raises(ValueError, match="target fingerprint"):
        translate(replace(operational_plan(), target_fingerprint=""))


def test_contract_contains_no_executable_or_native_provider_fields() -> None:
    fields = set(type(translate()).__dataclass_fields__)
    assert fields.isdisjoint(
        {
            "argv",
            "command",
            "endpoint",
            "environment",
            "parameters",
            "provider_payload",
            "repository_root",
            "request_body",
            "url",
            "working_directory",
        }
    )
