from __future__ import annotations

import ast
import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
)
from app.installation_targets.fingerprint import (
    _canonical_hash,
    build_destination_fingerprint,
    build_enumeration_token,
    build_request_digest,
    build_selection_fingerprint,
)
from app.installation_targets.resolver import (
    CurrentDestinationIdentity,
    DestinationNotSelectableError,
    DestinationResolutionError,
    observe_destination_identity,
    project_destination,
)
from app.installation_targets.service import (
    InstallationDestinationSelectionService,
    SelectionClockError,
    SelectionDestinationStaleError,
)
from app.installation_targets.store import (
    InstallationDestinationSelectionStore,
    SelectionActiveLimitError,
    SelectionIdempotencyConflictError,
    SelectionNotFoundError,
    SelectionStoreError,
)
from app.models.resources import (
    ProviderResource,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
)
from app.providers.capabilities import ProviderWorkspace
from app.providers.models import ProviderMetadata
from app.providers.proxmox import ProxmoxProvider
from app.services.operational_target_fingerprint import (
    build_operational_target_fingerprint,
)
from app.services.provider_resource_identity import (
    OperationalTargetIdentityUnavailableError,
    OperationalTargetResourceNotFoundError,
    ProviderResourceOperationError,
    ResolvedOperationalTarget,
)

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
UUIDS = iter(UUID(f"00000000-0000-4000-8000-{value:012x}") for value in range(1, 100))


def target(
    *,
    state: str = "running",
    token: str = "identity-a",
    node: str = "node-a",
    template: object = False,
    lock: object = None,
    migrating: object = False,
    identity: bool = True,
    metadata_changes: dict[str, object] | None = None,
    resource_type: str = "qemu",
    resource_id: str = "110",
) -> ResolvedOperationalTarget:
    metadata = {
        "node": node,
        "template": template,
        "lock": lock,
        "migrating": migrating,
        "vmgenid": "raw-secret",
    }
    metadata.update(metadata_changes or {})
    resource = ProviderResource(
        provider_id="proxmox",
        resource_id=resource_id,
        display_name="secret-hostname",
        resource_type=resource_type,
        current_state=state,
        identity=(
            ProviderResourceIdentity(token=token, token_version="identity-v1")
            if identity
            else None
        ),
        expectation=ProviderResourceExpectation(),
        configured=False,
        metadata=metadata,
    )
    return ResolvedOperationalTarget(
        provider=ProviderMetadata(
            id="proxmox", name="Proxmox", workspace=ProviderWorkspace.OPERATIONS
        ),
        resource=resource,
        resource_fingerprint=f"operational-target-fingerprint-v1:{token}:{node}",
    )


class MutableResolver:
    def __init__(self, current: ResolvedOperationalTarget | Exception) -> None:
        self.current = current

    async def __call__(
        self, provider: str, resource_id: str, resource_type: str
    ) -> ResolvedOperationalTarget:
        assert (provider, resource_id, resource_type) == ("proxmox", "110", "qemu")
        if isinstance(self.current, Exception):
            raise self.current
        return self.current


def service(tmp_path: Path, resolver: MutableResolver, *, clock=lambda: NOW):
    return InstallationDestinationSelectionService(
        store=InstallationDestinationSelectionStore(tmp_path / "selections.db"),
        resolver=resolver,
        clock=clock,
        uuid_factory=lambda: next(UUIDS),
    )


async def create_one(svc, *, operator="operator-a", key="0123456789abcdef"):
    destination = await svc.enumerate_one("110")
    return await svc.create(
        selected_by=operator, destination=destination, idempotency_key=key
    )


def test_contracts_are_closed_frozen_exact_and_sanitized() -> None:
    destination = project_destination(target())
    assert destination.provider == "proxmox"
    assert destination.resource_type == "qemu"
    assert destination.placement_kind == "existing-guest"
    serialized = destination.model_dump_json()
    assert "vmgenid" not in serialized and "secret-hostname" not in serialized
    with pytest.raises(ValidationError):
        ProspectiveInstallationDestinationV1(**destination.model_dump(), extra="no")
    with pytest.raises(ValidationError):
        destination.resource_id = "111"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ProspectiveInstallationDestinationV1(
            **{**destination.model_dump(), "provider": "docker"}
        )


@pytest.mark.parametrize(
    "resource_id", ["x101y", "101x", "x101", "+101", " 101", "101 ", "0"]
)
def test_resource_id_rejects_numeric_substrings(resource_id: str) -> None:
    with pytest.raises(ValidationError):
        ProspectiveInstallationDestinationV1(
            resource_id=resource_id,
            destination_fingerprint="a" * 64,
            enumeration_token="b" * 64,
        )


def test_valid_resource_id_still_passes() -> None:
    destination = ProspectiveInstallationDestinationV1(
        resource_id="101",
        destination_fingerprint="a" * 64,
        enumeration_token="b" * 64,
    )
    assert destination.resource_id == "101"


@pytest.mark.parametrize(
    "selection_id",
    [
        "prefix-00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000001-suffix",
        "prefix-00000000-0000-4000-8000-000000000001-suffix",
    ],
)
def test_selection_id_rejects_uuid4_substrings(selection_id: str) -> None:
    with pytest.raises(ValidationError):
        InstallationDestinationSelectionV1(
            selection_id=selection_id,
            resource_id="101",
            selected_destination_fingerprint="a" * 64,
            selected_at="2026-08-27T12:00:00Z",
            expires_at="2026-08-28T12:00:00Z",
            selected_by="operator-a",
            request_digest="b" * 64,
            selection_fingerprint="c" * 64,
            status="active",
            terminated_at=None,
        )


def test_exact_lowercase_uuid4_selection_id_still_passes() -> None:
    selection = InstallationDestinationSelectionV1(
        selection_id="00000000-0000-4000-8000-000000000001",
        resource_id="101",
        selected_destination_fingerprint="a" * 64,
        selected_at="2026-08-27T12:00:00Z",
        expires_at="2026-08-28T12:00:00Z",
        selected_by="operator-a",
        request_digest="b" * 64,
        selection_fingerprint="c" * 64,
        status="active",
        terminated_at=None,
    )
    assert selection.selection_id == "00000000-0000-4000-8000-000000000001"


def test_fingerprints_are_deterministic_sensitive_and_fail_closed() -> None:
    args = {
        "selected_by": "op",
        "enumeration_token": "a" * 64,
        "resource_id": "110",
        "destination_fingerprint": "b" * 64,
        "idempotency_key": "0123456789abcdef",
    }
    first = build_request_digest(**args)
    assert first == build_request_digest(**args)
    assert first != build_request_digest(
        **{**args, "idempotency_key": "fedcba9876543210"}
    )
    assert first != build_request_digest(
        **{**args, "destination_fingerprint": "c" * 64}
    )
    assert first != build_request_digest(**{**args, "resource_id": "111"})
    keys = frozenset({"a", "z"})
    assert _canonical_hash(
        "domain", {"z": None, "a": [True, 1, "é"]}, keys
    ) == _canonical_hash("domain", {"a": [True, 1, "é"], "z": None}, keys)
    with pytest.raises(ValueError, match="NFC"):
        _canonical_hash("domain", {"value": "e\u0301"}, frozenset({"value"}))
    with pytest.raises(TypeError):
        _canonical_hash("domain", {"value": 1.5}, frozenset({"value"}))
    with pytest.raises(ValueError, match="safe integers"):
        _canonical_hash("domain", {"value": 2**53}, frozenset({"value"}))
    with pytest.raises(TypeError):
        _canonical_hash("domain", {"value": (1, 2)}, frozenset({"value"}))
    with pytest.raises(TypeError):
        _canonical_hash("domain", {1: "unknown"}, frozenset({1}))  # type: ignore[arg-type,dict-item]


def test_fingerprint_golden_vectors() -> None:
    destination = build_destination_fingerprint(
        resource_id="110",
        operational_fingerprint="operational-target-fingerprint-v1:identity-a:node-a",
    )
    enumeration = build_enumeration_token(
        resource_id="110", destination_fingerprint=destination
    )
    request = build_request_digest(
        selected_by="operator-a",
        enumeration_token=enumeration,
        resource_id="110",
        destination_fingerprint=destination,
        idempotency_key="0123456789abcdef",
    )
    base = InstallationDestinationSelectionV1(
        selection_id="00000000-0000-4000-8000-000000000001",
        resource_id="110",
        selected_destination_fingerprint=destination,
        selected_at="2026-08-27T12:00:00Z",
        expires_at="2026-08-28T12:00:00Z",
        selected_by="operator-a",
        request_digest=request,
        selection_fingerprint="0" * 64,
        status="active",
        terminated_at=None,
    )
    assert (
        destination
        == "505b3caa22d2c3d902acf0cda17e943af2aaacb6a54d34ff3b28e7380ba00ffd"
    )
    assert (
        enumeration
        == "cb9731ba94c96f2422a2cbe76e389d2ce1174425f7aae0594cc6ee7df8b99829"
    )
    assert request == "90666d41b2856d3776b54e96f543ddcae0d3f216e3fbe8c48d70fa7eb5baab37"
    assert (
        build_selection_fingerprint(base)
        == "11ad2e7e685ca5179f0af98f943a5aafd4111d823aa7aa7dab15b02d3bcd7b53"
    )


def test_running_and_stopped_accepted_and_ineligible_states_rejected() -> None:
    assert project_destination(target(state="running"))
    assert project_destination(target(state="stopped"))
    for kwargs in (
        {"template": True},
        {"lock": "backup"},
        {"migrating": True},
        {"state": "unknown"},
        {"state": "migrating"},
        {"identity": False},
        {"resource_type": "lxc"},
        {"template": 0},
        {"lock": False},
        {"migrating": "false"},
    ):
        with pytest.raises(DestinationNotSelectableError):
            project_destination(target(**kwargs))
    for missing_key in ("template", "lock"):
        current = target()
        metadata = dict(current.resource.metadata)
        metadata.pop(missing_key)
        malformed = current.__class__(
            provider=current.provider,
            resource=current.resource.model_copy(update={"metadata": metadata}),
            resource_fingerprint=current.resource_fingerprint,
        )
        with pytest.raises(DestinationNotSelectableError):
            project_destination(malformed)


def test_production_proxmox_projection_preserves_explicit_unlocked_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.providers.proxmox as proxmox_module

    monkeypatch.setattr(
        proxmox_module,
        "get_proxmox_guests",
        lambda: {
            "node": "node-a",
            "running": 1,
            "stopped": 0,
            "guests": [
                {
                    "vmid": 110,
                    "name": "guest",
                    "type": "qemu",
                    "status": "running",
                    "vmgenid": "11111111-1111-1111-1111-111111111111",
                    "template": False,
                    "lock": None,
                    "migrating": False,
                }
            ],
        },
    )
    provider = ProxmoxProvider({"name": "Proxmox"})
    resource = asyncio.run(provider.list_resources()).resources[0]
    assert resource.metadata["template"] is False
    assert resource.metadata["lock"] is None
    assert resource.metadata["migrating"] is False
    projected = ResolvedOperationalTarget(
        provider=provider.metadata,
        resource=resource,
        resource_fingerprint=build_operational_target_fingerprint(
            provider.metadata, resource
        ),
    )
    assert project_destination(projected)


def test_create_replay_conflict_and_selection_fingerprint(tmp_path: Path) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    first = asyncio.run(create_one(svc))
    replay = asyncio.run(create_one(svc))
    assert replay == first
    assert first.expires_at == "2026-08-28T12:00:00Z"
    assert first.resource_id == "110"
    assert first.selection_fingerprint == build_selection_fingerprint(first)
    assert "0123456789abcdef" not in first.model_dump_json()
    changed = project_destination(target(token="identity-b"))
    resolver.current = target(token="identity-b")
    with pytest.raises(SelectionIdempotencyConflictError):
        asyncio.run(
            svc.create(
                selected_by="operator-a",
                destination=changed,
                idempotency_key="0123456789abcdef",
            )
        )


def test_active_bound_and_operator_isolation(tmp_path: Path) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    for index in range(16):
        asyncio.run(create_one(svc, key=f"key-{index:012d}"))
    with pytest.raises(SelectionActiveLimitError):
        asyncio.run(create_one(svc, key="key-999999999999"))
    other = asyncio.run(create_one(svc, operator="operator-b"))
    with pytest.raises(SelectionNotFoundError):
        asyncio.run(svc.get(selection_id=other.selection_id, selected_by="operator-a"))


def test_expiry_exact_boundary_and_no_reactivation(tmp_path: Path) -> None:
    instant = [NOW]
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver, clock=lambda: instant[0])
    record = asyncio.run(create_one(svc))
    instant[0] += timedelta(hours=24)
    expired = asyncio.run(
        svc.get(selection_id=record.selection_id, selected_by="operator-a")
    )
    assert expired.status == "expired" and expired.terminated_at == expired.expires_at
    instant[0] += timedelta(hours=1)
    assert (
        asyncio.run(svc.get(selection_id=record.selection_id, selected_by="operator-a"))
        == expired
    )


def test_cancel_terminal_idempotence_and_reselection(tmp_path: Path) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    first = asyncio.run(create_one(svc))
    cancelled = svc.cancel(selection_id=first.selection_id, selected_by="operator-a")
    assert cancelled.status == "cancelled"
    assert (
        svc.cancel(selection_id=first.selection_id, selected_by="operator-a")
        == cancelled
    )
    second = asyncio.run(create_one(svc, key="fedcba9876543210"))
    assert second.selection_id != first.selection_id


@pytest.mark.parametrize("terminal", ["cancelled", "expired", "stale"])
def test_terminal_replay_returns_same_tombstone_without_resolution(
    tmp_path: Path, terminal: str
) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    destination = asyncio.run(svc.enumerate_one("110"))
    first = asyncio.run(
        svc.create(
            selected_by="operator-a",
            destination=destination,
            idempotency_key="0123456789abcdef",
        )
    )
    svc._store.transition(
        selection_id=first.selection_id,
        selected_by=first.selected_by,
        status=terminal,
        terminated_at="2026-08-27T12:00:01Z",
    )
    resolver.current = RuntimeError("must not resolve a terminal replay")
    replay = asyncio.run(
        svc.create(
            selected_by="operator-a",
            destination=destination,
            idempotency_key="0123456789abcdef",
        )
    )
    assert replay.selection_id == first.selection_id
    assert replay.status == terminal


def test_replacement_and_node_movement_transition_stale(tmp_path: Path) -> None:
    for replacement in (target(token="identity-b"), target(node="node-b")):
        resolver = MutableResolver(target())
        svc = service(tmp_path / replacement.resource_fingerprint[-1], resolver)
        record = asyncio.run(create_one(svc))
        resolver.current = replacement
        stale = asyncio.run(
            svc.get(selection_id=record.selection_id, selected_by="operator-a")
        )
        assert stale.status == "stale"
        resolver.current = target()
        assert (
            asyncio.run(
                svc.get(selection_id=record.selection_id, selected_by="operator-a")
            )
            == stale
        )


def test_stale_enumeration_and_provider_unavailable_fail_closed(tmp_path: Path) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    enumerated = asyncio.run(svc.enumerate_one("110"))
    resolver.current = target(token="replacement")
    with pytest.raises(SelectionDestinationStaleError):
        asyncio.run(
            svc.create(
                selected_by="operator-a",
                destination=enumerated,
                idempotency_key="0123456789abcdef",
            )
        )
    resolver.current = RuntimeError("native secret")
    with pytest.raises(DestinationResolutionError, match="unavailable") as captured:
        asyncio.run(svc.enumerate_one("110"))
    assert "native secret" not in str(captured.value)


def test_current_identity_observation_distinguishes_exact_identity_states() -> None:
    exact = asyncio.run(
        observe_destination_identity("110", resolver=MutableResolver(target()))
    )
    assert exact.destination_available is True
    assert exact.destination_identity_available is True
    assert exact.current_destination_fingerprint is not None

    identity_unknown = asyncio.run(
        observe_destination_identity(
            "110",
            resolver=MutableResolver(
                OperationalTargetIdentityUnavailableError("raw identity detail")
            ),
        )
    )
    assert identity_unknown == CurrentDestinationIdentity(True, False, None)

    unavailable = asyncio.run(
        observe_destination_identity(
            "110",
            resolver=MutableResolver(
                OperationalTargetResourceNotFoundError("raw provider detail")
            ),
        )
    )
    assert unavailable == CurrentDestinationIdentity(False, False, None)

    with pytest.raises(DestinationResolutionError, match="observation failed") as captured:
        asyncio.run(
            observe_destination_identity(
                "110",
                resolver=MutableResolver(ProviderResourceOperationError("adapter secret")),
            )
        )
    assert "adapter secret" not in str(captured.value)


def test_persistence_round_trip_preserves_tombstone(tmp_path: Path) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    record = asyncio.run(create_one(svc))
    cancelled = svc.cancel(selection_id=record.selection_id, selected_by="operator-a")
    restored = InstallationDestinationSelectionStore(tmp_path / "selections.db")
    assert restored.get(record.selection_id, "operator-a").record == cancelled


def test_reopen_before_expiry_preserves_active_selection(tmp_path: Path) -> None:
    svc = service(tmp_path, MutableResolver(target()))
    record = asyncio.run(create_one(svc))

    restored = InstallationDestinationSelectionStore(
        tmp_path / "selections.db",
        open_clock=lambda: NOW + timedelta(hours=23, seconds=59),
    ).get(record.selection_id, "operator-a")

    assert restored.record.status == "active"
    assert restored.record.selection_fingerprint == record.selection_fingerprint
    assert restored.record_version == 1


def test_reopen_after_expiry_creates_immutable_tombstone_without_reactivation(
    tmp_path: Path,
) -> None:
    svc = service(tmp_path, MutableResolver(target()))
    record = asyncio.run(create_one(svc))
    database = tmp_path / "selections.db"
    expired_at = NOW + timedelta(hours=24)

    expired = InstallationDestinationSelectionStore(
        database, open_clock=lambda: expired_at
    ).get(record.selection_id, "operator-a")
    reopened = InstallationDestinationSelectionStore(
        database, open_clock=lambda: NOW
    ).list_for_principal("operator-a")[0]

    assert expired.record.status == "expired"
    assert expired.record.terminated_at == expired_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert expired.record.selection_fingerprint == record.selection_fingerprint
    assert expired.record_version == 2
    assert reopened == expired


def test_terminal_transition_has_one_winner(tmp_path: Path) -> None:
    resolver = MutableResolver(target())
    svc = service(tmp_path, resolver)
    record = asyncio.run(create_one(svc))
    store = svc._store
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda status: (
                    store.transition(
                        selection_id=record.selection_id,
                        selected_by="operator-a",
                        status=status,
                        terminated_at="2026-08-27T12:00:01Z",
                    ).record.status
                ),
                ("cancelled", "stale"),
            )
        )
    assert len(set(results)) == 1
    assert results[0] in {"cancelled", "stale"}


def test_same_key_concurrency_across_service_instances(tmp_path: Path) -> None:
    database = tmp_path / "selections.db"
    resolver = MutableResolver(target())
    services = [
        InstallationDestinationSelectionService(
            store=InstallationDestinationSelectionStore(database),
            resolver=resolver,
            clock=lambda: NOW,
            uuid_factory=lambda value=value: UUID(
                f"00000000-0000-4000-8000-{value:012x}"
            ),
        )
        for value in (80, 81)
    ]

    def create(svc: InstallationDestinationSelectionService):
        return asyncio.run(create_one(svc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(create, services))
    assert records[0] == records[1]


def test_concurrent_create_enforces_sixteen_active_limit(tmp_path: Path) -> None:
    database = tmp_path / "selections.db"
    resolver = MutableResolver(target())
    services = [
        InstallationDestinationSelectionService(
            store=InstallationDestinationSelectionStore(database),
            resolver=resolver,
            clock=lambda: NOW,
            uuid_factory=lambda value=value: UUID(
                f"00000000-0000-4000-8001-{value:012x}"
            ),
        )
        for value in range(1, 18)
    ]

    def attempt(pair):
        index, svc = pair
        try:
            return asyncio.run(create_one(svc, key=f"race-{index:011d}"))
        except SelectionActiveLimitError as error:
            return error

    with ThreadPoolExecutor(max_workers=17) as pool:
        results = list(pool.map(attempt, enumerate(services)))
    assert (
        sum(isinstance(item, InstallationDestinationSelectionV1) for item in results)
        == 16
    )
    assert sum(isinstance(item, SelectionActiveLimitError) for item in results) == 1


def test_conflicting_same_key_concurrency_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "selections.db"
    targets = (target(token="identity-a"), target(token="identity-b"))
    services = [
        InstallationDestinationSelectionService(
            store=InstallationDestinationSelectionStore(database),
            resolver=MutableResolver(current),
            clock=lambda: NOW,
            uuid_factory=lambda value=value: UUID(
                f"00000000-0000-4000-8000-{value:012x}"
            ),
        )
        for value, current in zip((82, 83), targets, strict=True)
    ]

    def attempt(svc: InstallationDestinationSelectionService):
        try:
            return asyncio.run(create_one(svc))
        except SelectionIdempotencyConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, services))
    assert (
        sum(isinstance(item, InstallationDestinationSelectionV1) for item in results)
        == 1
    )
    assert (
        sum(isinstance(item, SelectionIdempotencyConflictError) for item in results)
        == 1
    )


def test_selection_deserialization_rejects_unknown_and_invalid_lifecycle(
    tmp_path: Path,
) -> None:
    svc = service(tmp_path, MutableResolver(target()))
    record = asyncio.run(create_one(svc))
    with pytest.raises(ValidationError):
        InstallationDestinationSelectionV1(**record.model_dump(), provider_payload={})
    with pytest.raises(ValidationError):
        InstallationDestinationSelectionV1(
            **{**record.model_dump(), "expires_at": record.selected_at}
        )
    with pytest.raises(ValidationError, match="before selected_at"):
        InstallationDestinationSelectionV1.model_validate(
            {
                **record.model_dump(),
                "status": "cancelled",
                "terminated_at": "2026-08-27T11:59:59Z",
            }
        )
    with pytest.raises(ValidationError):
        InstallationDestinationSelectionV1.model_validate(
            {
                **record.model_dump(),
                "resource_id": "0",
            }
        )


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [
        ("selection_id", "00000000-0000-4000-8000-000000000099"),
        ("selected_by", "operator-b"),
        ("request_digest", "f" * 64),
        ("resource_id", "111"),
        ("status", "cancelled"),
        ("expires_at", "2026-08-29T12:00:00Z"),
        ("record_version", "invalid"),
    ],
)
def test_store_rejects_conflicting_duplicated_columns(
    tmp_path: Path, column: str, bad_value: object
) -> None:
    svc = service(tmp_path, MutableResolver(target()))
    asyncio.run(create_one(svc))
    database = tmp_path / "selections.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"UPDATE installation_destination_selections SET {column}=?",
            (bad_value,),
        )
    with pytest.raises(SelectionStoreError):
        InstallationDestinationSelectionStore(database).list_for_principal(
            "operator-a" if column != "selected_by" else "operator-b"
        )


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [
        ("record_json", "{"),
        ("idempotency_identity", "0" * 64),
        ("idempotency_key_verifier", "f" * 64),
    ],
)
def test_store_normalizes_decode_and_idempotency_corruption(
    tmp_path: Path, column: str, bad_value: str
) -> None:
    svc = service(tmp_path, MutableResolver(target()))
    asyncio.run(create_one(svc))
    database = tmp_path / "selections.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"UPDATE installation_destination_selections SET {column}=?", (bad_value,)
        )
    restored = InstallationDestinationSelectionStore(database)
    with pytest.raises(SelectionStoreError):
        restored.list_for_principal("operator-a")


def test_atomic_expiry_cleanup_frees_capacity_at_exact_boundary(tmp_path: Path) -> None:
    instant = [NOW]
    svc = service(tmp_path, MutableResolver(target()), clock=lambda: instant[0])
    for index in range(16):
        asyncio.run(create_one(svc, key=f"key-{index:012d}"))
    instant[0] += timedelta(hours=24)
    created = asyncio.run(create_one(svc, key="boundary-key-000"))
    assert created.status == "active"
    records = svc._store.list_for_principal("operator-a")
    assert sum(item.record.status == "active" for item in records) == 1
    assert sum(item.record.status == "expired" for item in records) == 16


def test_clock_failure_and_invalid_uuid_factory_fail_closed(tmp_path: Path) -> None:
    resolver = MutableResolver(target())

    def broken_clock() -> datetime:
        raise RuntimeError("clock secret")

    with pytest.raises(SelectionClockError, match="unavailable"):
        asyncio.run(
            create_one(service(tmp_path / "clock", resolver, clock=broken_clock))
        )

    invalid = InstallationDestinationSelectionService(
        store=InstallationDestinationSelectionStore(tmp_path / "uuid.db"),
        resolver=resolver,
        clock=lambda: NOW,
        uuid_factory=lambda: "not-a-uuid",  # type: ignore[arg-type,return-value]
    )
    with pytest.raises(ValueError, match="failed closed"):
        asyncio.run(create_one(invalid))


def test_corrupted_sqlite_database_is_normalized(tmp_path: Path) -> None:
    database = tmp_path / "corrupt.db"
    database.write_bytes(b"not sqlite")
    with pytest.raises(SelectionStoreError, match="initialization"):
        InstallationDestinationSelectionStore(database)


def test_authority_isolation_has_no_forbidden_imports() -> None:
    root = Path(__file__).parent
    forbidden = (
        "execution_candidates",
        "agent",
        "workflow",
        "approval",
        "operational_dispatch",
        "worker",
        "repository",
        "provider_intents",
    )
    for path in root.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        source = path.read_text()
        assert not any(f"app.{name}" in source for name in forbidden)
    assert "idempotency_key" not in json.dumps(
        InstallationDestinationSelectionV1.model_json_schema()["properties"]
    )


def test_provider_resource_dependency_uses_read_only_facade() -> None:
    root = Path(__file__).parent
    source = (root / "resolver.py").read_text()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "app.services.provider_resource_identity"
        for alias in node.names
    }
    assert imports == {
        "OperationalTargetIdentityUnavailableError",
        "OperationalTargetMarkedMissingError",
        "OperationalTargetResolutionError",
        "OperationalTargetResourceNotFoundError",
        "ProviderResourceError",
        "ResolvedOperationalTarget",
        "get_provider",
        "list_provider_resource_identities",
        "resolve_operational_target",
    }
    facade = root.parent / "services" / "provider_resource_identity.py"
    facade_source = facade.read_text()
    forbidden = (
        "app.actions",
        "app.provider_intents",
        "app.execution_candidates",
        "app.operational_dispatch",
        "app.workflows",
        "app.workers",
    )
    assert not any(name in facade_source for name in forbidden)
    assert "provider_resources" not in source
