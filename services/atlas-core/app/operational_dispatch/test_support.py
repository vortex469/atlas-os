"""Test-only constructors for operational dispatch contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.resources import (
    ProviderResource,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
)
from app.operational_dispatch.models import (
    OperationalApprovalBinding,
    OperationalDispatchRequest,
    OperationalVerificationSpecification,
    operational_idempotency_key,
    operational_request_digest,
    operational_verification_digest,
)
from app.providers import ProviderMetadata, ProviderWorkspace
from app.services.provider_resources import ResolvedOperationalTarget


def make_request(**changes: object) -> OperationalDispatchRequest:
    generated_at = datetime.now(UTC)
    verification = OperationalVerificationSpecification(
        pre_state="running",
        expected_post_state="running-and-healthy",
        identity_fingerprint="target-fingerprint-v1:aaa",
        health_requirement="healthy",
        unknown_outcome_policy="stop-and-reconcile",
    )
    values: dict[str, object] = {
        "schema_version": 1,
        "request_id": "operational-action-1",
        "request_digest": "",
        "idempotency_key": "",
        "workflow_session_id": "workflow-1",
        "candidate_planning_session_id": "planning-1",
        "candidate_id": "candidate-1",
        "candidate_fingerprint": "candidate-fingerprint-v1:aaa",
        "candidate_plan_id": "operational-plan-1",
        "candidate_plan_fingerprint": "operational-plan-fingerprint-v1:aaa",
        "effect_kind": "operational_action",
        "execution_intent": "restart-service",
        "provider_id": "proxmox",
        "resource_id": "qemu/101",
        "resource_type": "qemu",
        "provider_action_id": "proxmox-qemu-graceful-restart-v1",
        "target_fingerprint": "target-fingerprint-v1:aaa",
        "target_version": "uid-v1",
        "expected_pre_state": "running",
        "disruption_scope": "one service interruption",
        "evidence_ids": ("evidence-1",),
        "verification": verification,
        "generated_at": generated_at,
        "expires_at": generated_at + timedelta(minutes=5),
        "translator_version": "operational-action-translator-v1",
    }
    values.update(changes)
    provisional = OperationalDispatchRequest.model_construct(
        **values,
        approval=None,
    )
    digest = operational_request_digest(provisional)
    values["request_digest"] = digest
    values["idempotency_key"] = operational_idempotency_key(
        str(values["request_id"]), digest
    )
    values["approval"] = OperationalApprovalBinding(
        approval_request_id="approval-operational-1",
        action_request_id=str(values["request_id"]),
        action_request_digest=digest,
        candidate_id=str(values["candidate_id"]),
        candidate_fingerprint=str(values["candidate_fingerprint"]),
        operational_plan_fingerprint=str(values["candidate_plan_fingerprint"]),
        provider_id=str(values["provider_id"]),
        resource_id=str(values["resource_id"]),
        resource_type=str(values["resource_type"]),
        target_fingerprint=str(values["target_fingerprint"]),
        target_version=values["target_version"],  # type: ignore[arg-type]
        operation_intent=str(values["execution_intent"]),
        disruption_scope=str(values["disruption_scope"]),
        verification_digest=operational_verification_digest(
            values["verification"]  # type: ignore[arg-type]
        ),
        generated_at=values["generated_at"],  # type: ignore[arg-type]
        expires_at=values["expires_at"],  # type: ignore[arg-type]
    )
    return OperationalDispatchRequest.model_validate(values)


def make_target(**resource_changes: object) -> ResolvedOperationalTarget:
    resource_values: dict[str, object] = {
        "provider_id": "proxmox",
        "resource_id": "qemu/101",
        "display_name": "VM 101",
        "resource_type": "qemu",
        "current_state": "running",
        "identity": ProviderResourceIdentity(
            token="native-uid-1", token_version="uid-v1"
        ),
        "expectation": ProviderResourceExpectation(),
        "configured": False,
    }
    resource_values.update(resource_changes)
    return ResolvedOperationalTarget(
        provider=ProviderMetadata(
            id="proxmox",
            name="Proxmox",
            workspace=ProviderWorkspace.OPERATIONS,
        ),
        resource=ProviderResource.model_validate(resource_values),
        resource_fingerprint="target-fingerprint-v1:aaa",
    )
