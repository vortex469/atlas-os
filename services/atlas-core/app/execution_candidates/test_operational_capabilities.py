"""Provider-neutral operational capability descriptor tests."""

import json

from app.execution_candidates.operational_capabilities import (
    RESTART_PROXMOX_QEMU_CAPABILITY_ID,
    project_operational_capabilities,
)
from app.operational_dispatch.ledger import OperationalDispatchLedger
from app.operational_dispatch.registry import (
    OperationalHandlerRegistration,
    OperationalHandlerRegistry,
)
from app.operational_dispatch.service import OperationalDispatchService


async def _handler(_request, _target):  # pragma: no cover - descriptor never invokes it
    raise AssertionError("descriptor projection must never invoke a handler")


def _service(tmp_path, *, gate=True, handler=True):
    registry = OperationalHandlerRegistry(
        (
            OperationalHandlerRegistration(
                operation_intent="restart-service",
                provider_id="proxmox",
                resource_type="qemu",
                handler=_handler,
            ),
        )
        if handler
        else ()
    )
    return OperationalDispatchService(
        ledger=OperationalDispatchLedger(tmp_path / "descriptor.db"),
        registry=registry,
        execution_intents=frozenset({"restart-service"}) if gate else frozenset(),
    )


def test_exact_production_descriptor_is_sanitized_and_deterministic(tmp_path) -> None:
    first = project_operational_capabilities(_service(tmp_path))
    second = project_operational_capabilities(_service(tmp_path))

    assert first == second
    assert len(first.capabilities) == 1
    descriptor = first.capabilities[0]
    assert descriptor.capability_id == RESTART_PROXMOX_QEMU_CAPABILITY_ID
    assert (
        descriptor.execution_intent,
        descriptor.provider_id,
        descriptor.resource_type,
    ) == ("restart-service", "proxmox", "qemu")
    assert descriptor.production_enabled is True
    encoded = json.dumps(descriptor.model_dump(mode="json"))
    for forbidden in (
        "provider_action_id",
        "command",
        "credentials",
        "handler_class",
        "callback",
        "payload_schema",
        "vmgenid",
    ):
        assert forbidden not in encoded


def test_descriptor_mismatch_is_non_executable_and_does_not_repair_sources(tmp_path) -> None:
    service = _service(tmp_path, gate=False, handler=True)

    descriptor = project_operational_capabilities(service).capabilities[0]

    assert descriptor.core_gate_enabled is False
    assert descriptor.handler_registered is True
    assert descriptor.production_enabled is False
    assert descriptor.consistency == "mismatch"
    assert service.capability_boundary("restart-service", "proxmox", "qemu") == (
        False,
        True,
    )
