from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.execution_candidates.intake import CandidatePlanningIntakeRequest
from app.execution_candidates.models import ExecutionCandidateStatus
from app.execution_candidates.operator_intents import (
    OPERATOR_INTENT_SOURCE,
    OperatorIntentStore,
    OperatorIntentStoreConflictError,
    OperatorOperationalIntentRequest,
    build_operator_intent_identity,
    create_operator_intent,
    project_operator_intent,
    record_from_request,
)
from app.models.resources import (
    ProviderResource,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
)
from app.operator_auth.audit import OperatorSecurityAuditStore
from app.operator_auth.models import OPERATIONAL_INTENT_CREATE, OperatorCredential
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.providers.capabilities import ProviderWorkspace
from app.providers.models import ProviderMetadata
from app.routes import execution_candidates as routes
from app.services.execution_candidate_intake import validate_candidate_planning_intake
from app.services.provider_resources import (
    ProviderResourceOperationError,
    ResolvedOperationalTarget,
)
from app.testing import ASGITestClient


def target(
    *,
    fingerprint: str = "operational-target-fingerprint-v1:" + "a" * 64,
    state: str = "running",
    identity: bool = True,
    template: bool = False,
    lock: str | None = None,
    migrating: bool = False,
) -> ResolvedOperationalTarget:
    return ResolvedOperationalTarget(
        provider=ProviderMetadata(
            id="proxmox",
            name="Proxmox",
            workspace=ProviderWorkspace.OPERATIONS,
        ),
        resource=ProviderResource(
            provider_id="proxmox",
            resource_id="110",
            display_name="Frigate",
            resource_type="qemu",
            current_state=state,
            identity=(
                ProviderResourceIdentity(token="vmgenid-redacted", token_version="proxmox-qemu-v1")
                if identity
                else None
            ),
            expectation=ProviderResourceExpectation(
                value="monitor",
                label="Monitor",
                state="configured",
            ),
            configured=True,
            metadata={"template": template, "lock": lock, "migrating": migrating},
        ),
        resource_fingerprint=fingerprint,
    )


def intent_request(*, expires_at: datetime | None = None, **updates: object):
    payload: dict[str, object] = {
        "execution_intent": "restart-service",
        "provider_id": "proxmox",
        "resource_id": "110",
        "resource_type": "qemu",
        "expires_at": expires_at or datetime.now(UTC) + timedelta(hours=1),
    }
    payload.update(updates)
    return OperatorOperationalIntentRequest.model_validate(payload)


def record(*, now: datetime | None = None, **target_updates: object):
    current = now or datetime.now(UTC)
    return record_from_request(
        intent_request(expires_at=current + timedelta(hours=1)),
        operator_id="kenny",
        target=target(**target_updates),
        now=current,
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"provider_id": "docker"},
        {"resource_type": "lxc"},
        {"execution_intent": "update-compose-stack"},
        {"resource_id": "Frigate"},
        {"resource_id": "*"},
        {"provider_action_id": "proxmox-qemu-graceful-restart-v1"},
        {"parameters": {}},
        {"command": "reboot"},
        {"url": "https://provider.invalid"},
        {"operator_id": "forged"},
    ],
)
def test_request_model_is_closed_strict_and_semantic(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        intent_request(**extra)


def test_request_expiry_is_aware_future_and_bounded() -> None:
    with pytest.raises(ValidationError):
        intent_request(expires_at=datetime(2030, 1, 1))  # noqa: DTZ001 - intentionally naive
    with pytest.raises(ValidationError):
        intent_request(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        intent_request(expires_at=datetime.now(UTC) + timedelta(days=2))


def test_store_is_deterministic_idempotent_restart_safe_and_mode_0600(tmp_path: Path) -> None:
    database = tmp_path / "operator-intents.db"
    current = datetime.now(UTC)
    request = intent_request(expires_at=current + timedelta(hours=1))
    first = record_from_request(request, operator_id="kenny", target=target(), now=current)
    same = record_from_request(
        request,
        operator_id="kenny",
        target=target(),
        now=current + timedelta(seconds=1),
    )
    assert first.record_id == same.record_id
    assert first.request_digest == same.request_digest

    store = OperatorIntentStore(database)
    stored, created = store.put(first)
    reused, duplicate_created = store.put(same)
    assert created is True
    assert duplicate_created is False
    assert reused == stored == first
    assert database.stat().st_mode & 0o777 == 0o600
    assert OperatorIntentStore(database).list() == (first,)


def test_store_concurrent_duplicates_converge(tmp_path: Path) -> None:
    store = OperatorIntentStore(tmp_path / "operator-intents.db")
    current = record()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(pool.map(lambda _index: store.put(current), range(16)))
    assert sum(created for _stored, created in results) == 1
    assert store.list() == (current,)


def test_store_rejects_conflicting_identity_reuse(tmp_path: Path) -> None:
    store = OperatorIntentStore(tmp_path / "operator-intents.db")
    current = record()
    store.put(current)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE operator_intents SET request_digest=? WHERE record_id=?",
            ("operator-intent-request-v1:" + "b" * 64, current.record_id),
        )
    with pytest.raises(OperatorIntentStoreConflictError):
        store.put(current)


def test_identity_binds_security_relevant_semantics() -> None:
    base = {
        "operator_id": "kenny",
        "execution_intent": "restart-service",
        "provider_id": "proxmox",
        "resource_id": "110",
        "resource_type": "qemu",
        "target_fingerprint": "fingerprint-a",
        "target_version": "version-a",
        "expected_state": "running",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    identities = {
        build_operator_intent_identity(**(base | {key: value}))[0]
        for key, value in (
            ("resource_id", "111"),
            ("target_fingerprint", "fingerprint-b"),
            ("target_version", "version-b"),
            ("expires_at", base["expires_at"] + timedelta(seconds=1)),
        )
    }
    assert len(identities) == 4


@pytest.mark.anyio
@pytest.mark.parametrize(
    "target_updates",
    [
        {"state": "stopped"},
        {"identity": False},
        {"template": True},
        {"lock": "backup"},
        {"migrating": True},
    ],
)
async def test_creation_rejects_ineligible_authoritative_targets(
    tmp_path: Path, target_updates: dict[str, object]
) -> None:
    async def resolver(_provider: str, _resource: str, _type: str):
        return target(**target_updates)

    with pytest.raises(ValueError):
        await create_operator_intent(
            intent_request(),
            operator_id="kenny",
            store=OperatorIntentStore(tmp_path / "intents.db"),
            resolver=resolver,
        )


@pytest.mark.anyio
async def test_creation_is_candidate_only_and_expected_fingerprint_is_cas(tmp_path: Path) -> None:
    current_target = target()

    async def resolver(provider: str, resource_id: str, resource_type: str):
        assert (provider, resource_id, resource_type) == ("proxmox", "110", "qemu")
        return current_target

    store = OperatorIntentStore(tmp_path / "intents.db")
    result = await create_operator_intent(
        intent_request(expected_target_fingerprint=current_target.resource_fingerprint),
        operator_id="kenny",
        store=store,
        resolver=resolver,
    )
    assert result.candidate.source_subsystem == OPERATOR_INTENT_SOURCE
    assert result.candidate.status is ExecutionCandidateStatus.ELIGIBLE
    assert result.candidate.operational_target.resource_fingerprint == current_target.resource_fingerprint
    assert store.list()[0].operator_id == "kenny"

    with pytest.raises(ValueError, match="stale"):
        await create_operator_intent(
            intent_request(expected_target_fingerprint="operational-target-fingerprint-v1:" + "b" * 64),
            operator_id="kenny",
            store=store,
            resolver=resolver,
        )


@pytest.mark.anyio
async def test_projection_revalidates_stale_expired_and_temporary_failure() -> None:
    current = datetime.now(UTC)
    active = record(now=current)

    async def changed(_provider: str, _resource: str, _type: str):
        return target(fingerprint="operational-target-fingerprint-v1:" + "b" * 64)

    stale = await project_operator_intent(active, resolver=changed, now=current)
    assert stale.status is ExecutionCandidateStatus.NOT_ELIGIBLE

    async def unavailable(_provider: str, _resource: str, _type: str):
        raise ProviderResourceOperationError("temporary provider failure")

    unavailable_candidate = await project_operator_intent(active, resolver=unavailable, now=current)
    assert unavailable_candidate.status is ExecutionCandidateStatus.NOT_ELIGIBLE
    expired = await project_operator_intent(active, resolver=changed, now=active.expires_at)
    assert expired.status is ExecutionCandidateStatus.NOT_ELIGIBLE


@pytest.mark.anyio
async def test_planning_intake_revalidates_operator_candidate(tmp_path: Path) -> None:
    current = datetime.now(UTC)
    stored = record(now=current)
    store = OperatorIntentStore(tmp_path / "intents.db")
    store.put(stored)
    calls = 0

    async def resolver(_provider: str, _resource: str, _type: str):
        nonlocal calls
        calls += 1
        return target()

    from app.services.execution_candidates import get_current_execution_candidate

    projected = await project_operator_intent(stored, resolver=resolver, now=current)
    candidate = await get_current_execution_candidate(
        projected.id,
        finding_collector=lambda: (),
        operator_intent_store=store,
        operational_target_resolver=resolver,
        now=current,
    )
    result = await validate_candidate_planning_intake(
        candidate.id,
        CandidatePlanningIntakeRequest(),
        candidate_resolver=lambda candidate_id, **kwargs: get_current_execution_candidate(
            candidate_id,
            finding_collector=lambda: (),
            operator_intent_store=store,
            operational_target_resolver=resolver,
            now=current,
        ),
        now=current,
    )
    assert result.planning_allowed is True
    assert calls >= 2


def _route_client(tmp_path: Path, *, permissions=(OPERATIONAL_INTENT_CREATE,), limit=10):
    app = FastAPI()
    app.state.operator_auth_enabled = True
    app.state.operator_auth_trusted_origins = frozenset({"https://atlas.test"})
    app.state.operator_session_store = OperatorSessionStore(tmp_path / "sessions.db", 300)
    app.state.operator_security_audit = OperatorSecurityAuditStore(tmp_path / "security.db")
    app.state.operator_mutation_rate_limiter = OperatorRateLimiter(limit, 60)
    app.state.operator_intent_store = OperatorIntentStore(tmp_path / "intents.db")
    created = app.state.operator_session_store.create(
        OperatorCredential(
            operator_id="kenny",
            password_hash="not-used",
            permissions=permissions,
        )
    )
    app.include_router(routes.router, prefix="/api/v1")
    client = ASGITestClient(app, base_url="https://atlas.test")
    client.cookies.set("atlas_operator_session", created.session_token)
    headers = {"Origin": "https://atlas.test", "X-Atlas-CSRF-Token": created.csrf_token}
    return client, headers


def test_operator_intent_route_enforces_auth_origin_csrf_permission_rate_and_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def resolver(_provider: str, _resource: str, _type: str):
        return target()

    monkeypatch.setattr(routes, "resolve_operational_target", resolver)
    body = intent_request().model_dump(mode="json")

    # The boundary is exercised on a configured app so forged identity headers remain inert.
    client, headers = _route_client(tmp_path / "valid", limit=1)
    client.cookies.clear()
    assert client.post(
        "/api/v1/execution-candidates/operator-intents",
        headers={**headers, "X-Atlas-Operator": "kenny"},
        json=body,
    ).status_code == 401
    client, headers = _route_client(tmp_path / "checks", limit=1)
    assert client.post(
        "/api/v1/execution-candidates/operator-intents", json=body
    ).status_code == 403
    assert client.post(
        "/api/v1/execution-candidates/operator-intents",
        headers={"Origin": "https://atlas.test", "X-Atlas-CSRF-Token": "wrong"},
        json=body,
    ).status_code == 403
    accepted = client.post(
        "/api/v1/execution-candidates/operator-intents", headers=headers, json=body
    )
    assert accepted.status_code == 201
    assert accepted.json()["candidate"]["source_subsystem"] == OPERATOR_INTENT_SOURCE
    assert "operational_target" not in accepted.json()["candidate"]
    assert client.post(
        "/api/v1/execution-candidates/operator-intents", headers=headers, json=body
    ).status_code == 429

    forbidden, forbidden_headers = _route_client(tmp_path / "forbidden", permissions=())
    assert forbidden.post(
        "/api/v1/execution-candidates/operator-intents",
        headers=forbidden_headers,
        json=body,
    ).status_code == 403


def test_operator_intent_source_has_no_execution_or_mutation_imports() -> None:
    source = Path(__file__).with_name("operator_intents.py").read_text(encoding="utf-8")
    forbidden = (
        "operational_dispatch",
        "ProxmoxOperational",
        "OperationalActionRequest",
        "subprocess",
        "docker",
        "agent",
        "workflow",
    )
    assert not any(value in source for value in forbidden)
