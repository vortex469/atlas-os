from datetime import timedelta
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.context import AtlasContext
from app.operational_dispatch.models import OperationalDispatchRequest
from app.operational_dispatch.production import (
    build_production_operational_handler_registry,
)
from app.operational_dispatch.registry import (
    OPERATIONAL_EXECUTION_INTENTS,
    production_operational_handler_registry,
)
from app.operational_dispatch.test_support import make_request
from app.providers.proxmox_operational import ProxmoxQemuGracefulRestartHandler


def test_production_registry_is_exact_and_semantic_gate_is_narrow() -> None:
    assert OPERATIONAL_EXECUTION_INTENTS == frozenset({"restart-service"})
    assert len(production_operational_handler_registry) == 0
    registry = build_production_operational_handler_registry(Mock(spec=AtlasContext))
    assert len(registry) == 1
    handler = registry.resolve("restart-service", "proxmox", "qemu")
    assert type(handler) is ProxmoxQemuGracefulRestartHandler
    assert registry.resolve("restart-service", "proxmox", "lxc") is None
    assert registry.resolve("restart-service", "docker", "qemu") is None
    assert registry.resolve("stop-service", "proxmox", "qemu") is None


def test_request_is_strict_immutable_and_has_no_native_payload_fields() -> None:
    request = make_request()
    with pytest.raises(ValidationError):
        OperationalDispatchRequest.model_validate(
            {**request.model_dump(), "parameters": {"force": True}}
        )
    with pytest.raises(ValidationError):
        request.resource_id = "qemu/999"  # type: ignore[misc]
    assert set(OperationalDispatchRequest.model_fields).isdisjoint(
        {"command", "endpoint", "environment", "parameters", "request_body", "url"}
    )


def test_request_rejects_digest_action_approval_and_expiry_drift() -> None:
    request = make_request()
    for change in (
        {"request_digest": "operational-action-request-digest-v1:" + "0" * 64},
        {"provider_action_id": "injected-action"},
        {"expires_at": request.generated_at - timedelta(seconds=1)},
        {
            "approval": request.approval.model_copy(
                update={"target_fingerprint": "target-fingerprint-v1:replaced"}
            )
        },
    ):
        with pytest.raises(ValidationError):
            OperationalDispatchRequest.model_validate(
                {**request.model_dump(), **change}
            )
