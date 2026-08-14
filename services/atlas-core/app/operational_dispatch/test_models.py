from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.operational_dispatch.models import OperationalDispatchRequest
from app.operational_dispatch.registry import (
    OPERATIONAL_EXECUTION_INTENTS,
    production_operational_handler_registry,
)
from app.operational_dispatch.test_support import make_request


def test_production_registry_and_semantic_gate_are_empty() -> None:
    assert OPERATIONAL_EXECUTION_INTENTS == frozenset()
    assert len(production_operational_handler_registry) == 0


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
