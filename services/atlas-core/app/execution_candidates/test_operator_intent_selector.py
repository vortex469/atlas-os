from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.execution_candidates.operator_intent_selector import (
    OperatorIntentResourceCollectionError,
    OperatorIntentResourceReason,
    collect_operator_intent_resources,
)
from app.models.resources import (
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
    ProviderResourceSummary,
)
from app.operator_auth.audit import OperatorSecurityAuditStore
from app.operator_auth.models import OPERATIONAL_INTENT_CREATE, OperatorCredential
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.providers.capabilities import ProviderWorkspace
from app.providers.models import ProviderMetadata
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.routes import execution_candidates as routes
from app.services.operational_target_fingerprint import (
    build_operational_target_fingerprint,
)
from app.services.provider_resources import (
    OperationalTargetIdentityUnavailableError,
    ProviderResourceOperationError,
    ResolvedOperationalTarget,
)

FINGERPRINT_A = "operational-target-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "operational-target-fingerprint-v1:" + "b" * 64


def resource(
    resource_id: str,
    *,
    resource_type: str = "qemu",
    state: str = "running",
    identity: bool = True,
    template: bool = False,
    lock: str | None = None,
    migrating: bool = False,
    qmp: str | None = None,
) -> ProviderResource:
    metadata: dict[str, object] = {
        "node": "vorex469",
        "vmid": int(resource_id),
        "template": template,
        "lock": lock,
        "migrating": migrating,
        "native_private_value": "must-not-leak",
        "vmgenid": "must-not-leak",
    }
    if qmp is not None:
        metadata["qmp"] = qmp
    return ProviderResource(
        provider_id="proxmox",
        resource_id=resource_id,
        display_name=f"VM {resource_id}",
        resource_type=resource_type,
        current_state=state,
        identity=(
            ProviderResourceIdentity(
                token=f"opaque-identity-{resource_id}",
                token_version="proxmox-qemu-identity-v1",
            )
            if identity
            else None
        ),
        expectation=ProviderResourceExpectation(
            value="running",
            label="Expected Running",
            state="configured",
        ),
        configured=True,
        metadata=metadata,
    )


def collection(*resources: ProviderResource) -> ProviderResourceCollection:
    return ProviderResourceCollection(
        provider_id="proxmox",
        provider_name="Proxmox",
        refreshed_at=datetime.now(UTC),
        resources=list(resources),
        summary=ProviderResourceSummary(
            total=len(resources),
            configured=len(resources),
            needs_review=0,
            missing=0,
            ignored=0,
        ),
    )


def resolved(current: ProviderResource, fingerprint: str = FINGERPRINT_A):
    return ResolvedOperationalTarget(
        provider=ProviderMetadata(
            id="proxmox",
            name="Proxmox",
            workspace=ProviderWorkspace.OPERATIONS,
        ),
        resource=current,
        resource_fingerprint=fingerprint,
    )


@pytest.mark.anyio
async def test_selector_returns_only_sanitized_fields_and_authoritative_fingerprint() -> None:
    current = resource("110", qmp="running")

    async def collector(_provider: str):
        return collection(current)

    async def resolver(_provider: str, _resource: str, _type: str):
        return resolved(current)

    result = await collect_operator_intent_resources(collector=collector, resolver=resolver)
    selected = result.resources[0]
    assert selected.requestable is True
    assert selected.reason is None
    assert selected.operational_target_fingerprint == FINGERPRINT_A
    assert set(selected.model_dump()) == {
        "provider_id",
        "resource_id",
        "resource_type",
        "display_name",
        "node",
        "current_state",
        "authoritative_identity_present",
        "template",
        "locked",
        "migrating",
        "operational_target_fingerprint",
        "requestable",
        "reason",
    }
    rendered = selected.model_dump_json()
    for forbidden in (
        '"identity":',
        "vmgenid",
        "token",
        "native_private_value",
        "provider_action_id",
    ):
        assert forbidden not in rendered


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"state": "stopped"}, OperatorIntentResourceReason.STOPPED),
        ({"template": True}, OperatorIntentResourceReason.TEMPLATE),
        ({"lock": "backup"}, OperatorIntentResourceReason.LOCKED),
        ({"lock": "migrate"}, OperatorIntentResourceReason.MIGRATING),
        ({"migrating": True}, OperatorIntentResourceReason.MIGRATING),
        ({"qmp": "stopped"}, OperatorIntentResourceReason.UNAVAILABLE_STATE),
    ],
)
async def test_selector_classifies_non_requestable_qemu(
    updates: dict[str, object], reason: OperatorIntentResourceReason
) -> None:
    current = resource("110", **updates)

    async def collector(_provider: str):
        return collection(current)

    async def resolver(_provider: str, _resource: str, _type: str):
        return resolved(current)

    selected = (
        await collect_operator_intent_resources(collector=collector, resolver=resolver)
    ).resources[0]
    assert selected.requestable is False
    assert selected.reason is reason
    assert selected.operational_target_fingerprint == FINGERPRINT_A


@pytest.mark.anyio
async def test_selector_classifies_identity_unavailable_and_wrong_type() -> None:
    no_identity = resource("110", identity=False)
    lxc = resource("109", resource_type="lxc", identity=False)

    async def collector(_provider: str):
        return collection(no_identity, lxc)

    async def resolver(_provider: str, _resource: str, _type: str):
        raise OperationalTargetIdentityUnavailableError("identity unavailable")

    result = await collect_operator_intent_resources(collector=collector, resolver=resolver)
    by_id = {item.resource_id: item for item in result.resources}
    assert by_id["110"].reason is OperatorIntentResourceReason.IDENTITY_UNAVAILABLE
    assert by_id["110"].operational_target_fingerprint is None
    assert by_id["109"].reason is OperatorIntentResourceReason.UNSUPPORTED_RESOURCE_TYPE


@pytest.mark.anyio
async def test_selector_is_deterministic_deduplicated_and_fingerprint_sensitive() -> None:
    first = resource("110")
    second = resource("9")

    async def collector(_provider: str):
        return collection(first, second, first)

    fingerprint = FINGERPRINT_A

    async def resolver(_provider: str, resource_id: str, _type: str):
        current = first if resource_id == "110" else second
        return resolved(current, fingerprint)

    initial = await collect_operator_intent_resources(collector=collector, resolver=resolver)
    assert [item.resource_id for item in initial.resources] == ["9", "110"]
    assert len(initial.resources) == 2
    fingerprint = FINGERPRINT_B
    changed = await collect_operator_intent_resources(collector=collector, resolver=resolver)
    assert changed.resources[1].operational_target_fingerprint == FINGERPRINT_B


@pytest.mark.anyio
async def test_changed_vmgenid_changes_selector_fingerprint() -> None:
    first = resource("110")
    first.identity = build_proxmox_qemu_identity(
        node="vorex469",
        vmid="110",
        vmgenid="11111111-1111-1111-1111-111111111111",
    )
    second = first.model_copy(deep=True)
    second.identity = build_proxmox_qemu_identity(
        node="vorex469",
        vmid="110",
        vmgenid="22222222-2222-2222-2222-222222222222",
    )
    provider = ProviderMetadata(
        id="proxmox",
        name="Proxmox",
        workspace=ProviderWorkspace.OPERATIONS,
    )
    selected_resource = first

    async def collector(_provider: str):
        return collection(selected_resource)

    async def resolver(_provider: str, _resource: str, _type: str):
        return ResolvedOperationalTarget(
            provider=provider,
            resource=selected_resource,
            resource_fingerprint=build_operational_target_fingerprint(
                provider, selected_resource
            ),
        )

    initial = await collect_operator_intent_resources(collector=collector, resolver=resolver)
    selected_resource = second
    changed = await collect_operator_intent_resources(collector=collector, resolver=resolver)
    assert (
        initial.resources[0].operational_target_fingerprint
        != changed.resources[0].operational_target_fingerprint
    )


@pytest.mark.anyio
async def test_selector_fails_closed_on_temporary_provider_failure() -> None:
    async def collector(_provider: str):
        raise ProviderResourceOperationError("temporary")

    with pytest.raises(OperatorIntentResourceCollectionError):
        await collect_operator_intent_resources(collector=collector)


def route_client(tmp_path: Path, *, permissions=(OPERATIONAL_INTENT_CREATE,)):
    app = FastAPI()
    app.state.operator_auth_enabled = True
    app.state.operator_session_store = OperatorSessionStore(tmp_path / "sessions.db", 300)
    app.state.operator_security_audit = OperatorSecurityAuditStore(tmp_path / "audit.db")
    app.state.operator_mutation_rate_limiter = OperatorRateLimiter(10, 60)
    app.state.operational_dispatch_service = SimpleNamespace(
        capability_boundary=lambda _intent, _provider, _resource_type: (True, True)
    )
    created = app.state.operator_session_store.create(
        OperatorCredential(
            operator_id="kenny",
            password_hash="unused",
            permissions=permissions,
        )
    )
    app.include_router(routes.router, prefix="/api/v1")
    client = TestClient(app, base_url="https://atlas.test")
    client.cookies.set("atlas_operator_session", created.session_token)
    return client


def test_selector_route_requires_operator_permission_but_not_csrf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def selector():
        current = resource("110")

        async def collector(_provider: str):
            return collection(current)

        async def resolver(_provider: str, _resource: str, _type: str):
            return resolved(current)

        return await collect_operator_intent_resources(collector=collector, resolver=resolver)

    monkeypatch.setattr(routes, "collect_operator_intent_resources", selector)
    client = route_client(tmp_path / "valid")
    response = client.get("/api/v1/execution-candidates/operator-intents/resources")
    assert response.status_code == 200
    assert response.json()["resources"][0]["requestable"] is True

    client.cookies.clear()
    forged = client.get(
        "/api/v1/execution-candidates/operator-intents/resources",
        headers={"X-Atlas-Operator": "kenny", "Authorization": "Bearer agent-token"},
    )
    assert forged.status_code == 401

    forbidden = route_client(tmp_path / "forbidden", permissions=())
    assert forbidden.get(
        "/api/v1/execution-candidates/operator-intents/resources"
    ).status_code == 403


def test_capability_route_is_authenticated_and_unknown_selector_is_closed(
    tmp_path: Path,
) -> None:
    client = route_client(tmp_path / "capability")
    response = client.get(
        "/api/v1/execution-candidates/operator-intents/capabilities"
    )
    assert response.status_code == 200
    descriptor = response.json()["capabilities"][0]
    assert descriptor["production_enabled"] is True
    assert descriptor["capability_id"] == "restart-service--proxmox--qemu"

    unknown = client.get(
        "/api/v1/execution-candidates/operator-intents/capabilities/https:%2F%2Fevil.invalid/resources"
    )
    assert unknown.status_code == 404
    client.cookies.clear()
    assert client.get(
        "/api/v1/execution-candidates/operator-intents/capabilities"
    ).status_code == 401


def test_selector_source_has_no_mutation_or_execution_dependencies() -> None:
    source = Path(__file__).with_name("operator_intent_selector.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "operational_dispatch",
        "ProxmoxOperational",
        "provider_action_id",
        "subprocess",
        "docker",
        "agent",
        "workflow",
        "create_operator_intent",
        "candidate_from_record",
    )
    assert not any(value in source for value in forbidden)
