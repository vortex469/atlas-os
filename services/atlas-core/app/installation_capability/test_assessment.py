from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.installation_capability.assessment import assess_installation_capability
from app.installation_capability.provider_facts import (
    ProviderCapabilityFactV1,
    ProviderInstallationCapabilityFactsV1,
)
from app.installation_plan.assembly import default_installation_plan_dependency
from app.installation_plan.contract import Prerequisite
from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
)

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
DEST = "a" * 64


def plan(*descriptions: str, ready: bool = True):
    value = default_installation_plan_dependency(
        repository_root=Path("/opt/atlas"),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    ).assemble("home-assistant")
    prerequisites = tuple(
        Prerequisite(
            prerequisite_id=f"{index:064x}",
            kind="storage" if "storage" in description else "platform",
            state="unknown",
            description=description,
        )
        for index, description in enumerate(descriptions, 1)
    )
    return value.model_copy(
        update={
            "status": "plan_ready_for_review" if ready else value.status,
            "prerequisites": prerequisites,
        }
    )


def selection(**updates: object):
    values = {
        "selection_id": "00000000-0000-4000-8000-000000000001",
        "resource_id": "101",
        "selected_destination_fingerprint": DEST,
        "selected_at": "2026-08-27T11:00:00Z",
        "expires_at": "2026-08-28T11:00:00Z",
        "selected_by": "operator-a",
        "request_digest": "b" * 64,
        "selection_fingerprint": "c" * 64,
        "status": "active",
        "terminated_at": None,
    }
    values.update(updates)
    return InstallationDestinationSelectionV1.model_validate(values)


def destination(**updates: object):
    values = {
        "resource_id": "101",
        "destination_fingerprint": DEST,
        "enumeration_token": "d" * 64,
    }
    values.update(updates)
    return ProspectiveInstallationDestinationV1.model_validate(values)


def provider_facts(
    *,
    cpu: object = 4,
    memory: object = 8 * 1024**3,
    disk: object = 64 * 1024**3,
    state: str = "observed",
    fingerprint: str = DEST,
    fresh_until: str = "2026-08-27T12:05:00Z",
):
    rows = (
        ("current_destination_identity", "observed", True),
        ("current_lifecycle_state", "observed", "running"),
        ("configured_cpu_cores", state, cpu if state == "observed" else None),
        ("configured_memory_bytes", state, memory if state == "observed" else None),
        (
            "configured_disk_capacity_bytes",
            state,
            disk if state == "observed" else None,
        ),
        ("guest_agent_configured", "observed", False),
    )
    return ProviderInstallationCapabilityFactsV1(
        resource_id="101",
        destination_fingerprint=fingerprint,
        observed_at="2026-08-27T12:00:00Z",
        fresh_until=fresh_until,
        facts=tuple(
            ProviderCapabilityFactV1(
                code=code,
                state=fact_state,
                value=value,
                observed_at="2026-08-27T12:00:00Z",
                destination_fingerprint=fingerprint,
            )
            for code, fact_state, value in rows
        ),
    )


def assess(value=None, **updates: object):
    inputs = {
        "plan": value or plan("Requires at least 2 CPU cores."),
        "selection": selection(),
        "current_destination": destination(),
        "provider_facts": provider_facts(),
        "evaluated_at": NOW,
    }
    inputs.update(updates)
    return assess_installation_capability(**inputs)


def test_all_comparison_states_and_exact_units() -> None:
    value = plan(
        "Requires at least 4 CPU cores.",
        "Requires at least 8192 MB memory.",
        "Requires at least 64 GB storage.",
        "Requires capability container-orchestration.",
    )
    assert [row.result for row in assess(value).comparisons] == [
        "satisfied",
        "satisfied",
        "satisfied",
        "not_assessable",
    ]
    assert (
        assess(plan("Requires at least 5 CPU cores.")).comparisons[0].result
        == "not_satisfied"
    )
    assert (
        assess(provider_facts=provider_facts(state="conflicted")).comparisons[0].result
        == "unknown"
    )


def test_status_precedence_and_non_authority_invariants() -> None:
    contradicted = assess(plan("Requires at least 5 CPU cores."))
    assert contradicted.assessment_status == "blocked"
    assert "requirement_not_satisfied" in contradicted.reason_codes
    unknown = assess(provider_facts=provider_facts(state="unavailable"))
    assert unknown.assessment_status == "insufficient_provider_facts"
    unsupported = assess(plan("Requires runtime docker."))
    assert unsupported.assessment_status == "insufficient_provider_facts"
    satisfied = assess()
    assert satisfied.assessment_status == "requirements_satisfied_but_non_authorizing"
    assert not any(
        (
            satisfied.candidate_eligibility_evaluated,
            satisfied.candidate_creation_allowed,
            satisfied.agent_execution_supported,
            satisfied.provider_mutation_allowed,
        )
    )


def test_fingerprint_stability_and_sensitivity() -> None:
    first = assess()
    assert first.assessment_fingerprint == assess().assessment_fingerprint
    assert (
        first.assessment_fingerprint
        != assess(
            evaluated_at=datetime(2026, 8, 27, 12, 0, 1, tzinfo=UTC)
        ).assessment_fingerprint
    )
    assert (
        first.assessment_fingerprint
        != assess(provider_facts=provider_facts(cpu=5)).assessment_fingerprint
    )


@pytest.mark.parametrize(
    "updates,reason",
    [
        (
            {
                "selection": selection(
                    status="stale", terminated_at="2026-08-27T11:30:00Z"
                )
            },
            "destination_selection_not_current",
        ),
        (
            {"current_destination": destination(destination_fingerprint="e" * 64)},
            "destination_identity_not_current",
        ),
        (
            {"provider_facts": provider_facts(fingerprint="e" * 64)},
            "provider_facts_not_current",
        ),
        (
            {"evaluated_at": datetime(2026, 8, 27, 12, 5, tzinfo=UTC)},
            "provider_facts_not_current",
        ),
        (
            {"evaluated_at": datetime(2026, 8, 27, 10, 59, 59, tzinfo=UTC)},
            "destination_selection_not_current",
        ),
    ],
)
def test_stale_moved_and_conflicting_inputs_fail_closed(
    updates: dict[str, object], reason: str
) -> None:
    result = assess(**updates)
    assert result.assessment_status == "blocked"
    assert reason in result.reason_codes
    assert result.comparisons[0].result == "unknown"


def test_home_assistant_golden_preserves_plan_blockers_and_provenance() -> None:
    home = plan(ready=False)
    result = assess(home)
    assert result.assessment_status == "blocked"
    assert (
        result.plan.fingerprint.value
        == "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"
    )
    assert (
        result.plan.deployment_artifact.repository_path == "compose/home-assistant.yaml"
    )
    assert result.plan.deployment_artifact.state == "missing"
    assert result.plan.blockers == home.blockers
    assert result.plan.provenance == home.provenance
    assert result.agent_execution_supported is False


def test_assessment_has_no_side_effect_or_authority_imports() -> None:
    source = Path(__file__).with_name("assessment.py")
    tree = ast.parse(source.read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden = {
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "sqlite3",
        "open",
        "write_text",
        "write_bytes",
        "execution_candidates",
        "operational_dispatch",
        "provider_intents",
        "get_proxmox_client",
        "get_proxmox_guests",
    }
    assert not imports & forbidden
    assert not calls & forbidden
