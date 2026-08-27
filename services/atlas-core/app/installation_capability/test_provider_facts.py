from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_capability.provider_facts import (
    ProviderCapabilityFactV1,
    adapt_proxmox_qemu_capability_facts,
)
from app.installation_targets.fingerprint import build_destination_fingerprint
from app.models.resources import (
    ProviderResource,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
)
from app.providers.models import ProviderMetadata
from app.services.provider_resource_identity import ResolvedOperationalTarget
from app.services.proxmox_service import _capability_observation

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
OPERATIONAL_FINGERPRINT = "a" * 64


def target(*, metadata: dict | None = None, state: str = "running") -> ResolvedOperationalTarget:
    return ResolvedOperationalTarget(
        provider=ProviderMetadata(id="proxmox", name="Proxmox", workspace="operations"),
        resource=ProviderResource(
            provider_id="proxmox", resource_id="101", display_name="redacted",
            resource_type="qemu", current_state=state,
            identity=ProviderResourceIdentity(token="opaque", token_version="v1"),
            expectation=ProviderResourceExpectation(), configured=False,
            metadata=metadata or {
                "installation_capability": {
                    "cpu_cores": {"state": "observed", "value": 4},
                    "memory_bytes": {"state": "observed", "value": 8 * 1024**3},
                    "disk_capacity_bytes": {"state": "observed", "value": 64 * 1024**3},
                    "guest_agent_configured": {"state": "observed", "value": False},
                },
                "host": "must-not-leak", "token": "secret",
            },
        ),
        resource_fingerprint=OPERATIONAL_FINGERPRINT,
    )


def fingerprint(value: ResolvedOperationalTarget) -> str:
    return build_destination_fingerprint(
        resource_id=value.resource.resource_id,
        operational_fingerprint=value.resource_fingerprint,
    )


def adapt(value: ResolvedOperationalTarget | None = None):
    resolved = value or target()
    return adapt_proxmox_qemu_capability_facts(
        resolved, expected_destination_fingerprint=fingerprint(resolved), observed_at=NOW
    )


def test_complete_closed_vocabulary_and_typed_values() -> None:
    facts = adapt()
    assert [fact.code for fact in facts.facts] == [
        "current_destination_identity", "current_lifecycle_state",
        "configured_cpu_cores", "configured_memory_bytes",
        "configured_disk_capacity_bytes", "guest_agent_configured",
    ]
    assert [fact.value for fact in facts.facts] == [
        True, "running", 4, 8 * 1024**3, 64 * 1024**3, False
    ]
    assert facts.observed_at == "2026-08-27T12:00:00Z"
    assert facts.fresh_until == "2026-08-27T12:05:00Z"


def test_provider_projection_reconciles_capacity_and_parses_disks() -> None:
    projected = _capability_observation(
        {
            "cores": 4, "memory": 8192, "agent": "enabled=1,fstrim_cloned_disks=1",
            "scsi0": "local:vm-101-disk-0,size=32G",
            "virtio1": "local:vm-101-disk-1,size=512M",
            "ide2": "local:cloudinit,media=cdrom",
        },
        {"maxcpu": 4, "maxmem": 8192 * 1024**2},
    )
    assert projected == {
        "cpu_cores": {"state": "observed", "value": 4},
        "memory_bytes": {"state": "observed", "value": 8192 * 1024**2},
        "disk_capacity_bytes": {"state": "observed", "value": 32 * 1024**3 + 512 * 1024**2},
        "guest_agent_configured": {"state": "observed", "value": True},
    }


@pytest.mark.parametrize(
    ("config", "inventory", "key", "state"),
    [
        (None, {}, "cpu_cores", "unavailable"),
        ({}, {}, "cpu_cores", "not_observed"),
        ({"cores": "four"}, {}, "cpu_cores", "malformed"),
        ({"cores": 4}, {"maxcpu": 8}, "cpu_cores", "conflicted"),
        ({"memory": 1024}, {"maxmem": 1}, "memory_bytes", "conflicted"),
        ({"scsi0": "private-volume-without-size"}, {}, "disk_capacity_bytes", "malformed"),
        ({"agent": "enabled=yes"}, {}, "guest_agent_configured", "malformed"),
    ],
)
def test_absent_malformed_unavailable_and_conflicted_inputs(
    config: dict | None, inventory: dict, key: str, state: str
) -> None:
    assert _capability_observation(config, inventory)[key] == {"state": state, "value": None}


def test_adapter_bounds_hostile_projection_and_never_leaks_raw_payload() -> None:
    raw = "https://root:secret@private.example/qemu/101"
    resolved = target(metadata={
        "installation_capability": {
            "cpu_cores": {"state": "observed", "value": raw, "payload": raw},
            "memory_bytes": {"state": "mystery", "value": 10},
            "disk_capacity_bytes": {"state": "observed", "value": 2**100},
            "guest_agent_configured": {"state": "not_observed", "value": raw},
        },
        "raw": raw,
    })
    serialized = adapt(resolved).model_dump_json()
    assert raw not in serialized
    assert [fact.state for fact in adapt(resolved).facts[2:]] == [
        "malformed", "malformed", "malformed", "not_observed"
    ]


def test_exact_current_identity_and_observation_time_are_required() -> None:
    resolved = target()
    with pytest.raises(ValueError, match="does not match"):
        adapt_proxmox_qemu_capability_facts(
            resolved, expected_destination_fingerprint="b" * 64, observed_at=NOW
        )
    with pytest.raises(ValueError, match="whole-second UTC"):
        adapt_proxmox_qemu_capability_facts(
            resolved, expected_destination_fingerprint=fingerprint(resolved),
            observed_at=NOW.replace(microsecond=1),
        )


def test_output_is_deterministic_and_detached() -> None:
    resolved = target()
    first = adapt(resolved)
    resolved.resource.metadata["installation_capability"]["cpu_cores"]["value"] = 99
    assert first.facts[2].value == 4
    assert adapt(target()).model_dump_json() == adapt(target()).model_dump_json()


def test_fact_contract_rejects_values_for_unknown_states() -> None:
    with pytest.raises(ValidationError, match="only observed facts carry values"):
        ProviderCapabilityFactV1(
            code="configured_cpu_cores", state="unavailable", value=4,
            observed_at="2026-08-27T12:00:00Z", destination_fingerprint="a" * 64,
        )


def test_adapter_has_no_forbidden_authority_imports_or_calls() -> None:
    source_path = Path(__file__).with_name("provider_facts.py")
    tree = ast.parse(source_path.read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden = {
        "requests", "httpx", "subprocess", "socket", "paramiko", "sqlite3",
        "operational_dispatch", "execution_candidates", "provider_intents",
        "get_proxmox_client", "get_proxmox_guests", "update_resource_expectation",
        "open", "write_text", "write_bytes",
    }
    assert not imports & forbidden
    assert not calls & forbidden
