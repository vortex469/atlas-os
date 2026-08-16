"""Activated schema-v2 Provider Intent fixture and recovery proofs."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import policies as policy_config
from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.models.provider_intents import (
    ProviderIntentCoordinateMutationCommand,
    ProviderIntentKind,
    ProviderIntentValue,
)
from app.models.provider_management import (
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
)
from app.models.resources import (
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceSummary,
)
from app.provider_intents.activation import validate_provider_intent_activation
from app.provider_intents.authority import ProxmoxMonitoringIntentAuthority
from app.provider_intents.legacy_import import (
    import_legacy_policy,
    load_legacy_policy_import,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreConflictError,
)
from app.providers.management import provider_resource_management_registry
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_management import project_managed_resource
from pydantic import ValidationError

NOW = datetime(2026, 8, 15, tzinfo=UTC)
REQUEST_110 = "provider-intent-mutation-" + "1" * 64
REQUEST_200 = "provider-intent-mutation-" + "2" * 64


def resource(resource_id: str, vmgenid: str) -> ProviderResource:
    return ProviderResource(
        provider_id="proxmox", resource_id=resource_id,
        display_name=f"Recovery QEMU {resource_id}", resource_type="qemu",
        current_state="running",
        identity=build_proxmox_qemu_identity(
            node="node-a", vmid=resource_id, vmgenid=vmgenid
        ),
        expectation=ProviderResourceExpectation(), configured=False,
    )


RESOURCE_110 = resource("110", "11111111-1111-1111-1111-111111111111")
RESOURCE_200 = resource("200", "22222222-2222-2222-2222-222222222222")


def fingerprint(value: ProviderResource) -> str:
    result = project_managed_resource(value).management_fingerprint
    assert result is not None
    return result


def command(
    request_id: str,
    value: ProviderResource,
) -> ProviderIntentCoordinateMutationCommand:
    return ProviderIntentCoordinateMutationCommand(
        operator_id="kenny", request_id=request_id, provider_id="proxmox",
        resource_type="qemu", resource_id=value.resource_id,
        management_fingerprint=fingerprint(value),
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=ProviderIntentValue.RUNNING, expected_record_version=0,
        acknowledge_monitoring_suppression=False,
    )


def _checkpoint(database: Path) -> None:
    gc.collect()
    with sqlite3.connect(database, isolation_level=None) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
    os.chmod(database, 0o600)


def seed(root: Path) -> str:
    policy = root / "config/policies.yaml"
    policy.write_text(
        "proxmox:\n  guests:\n"
        + "".join(
            f'    "{resource_id}":\n      expected: stopped\n'
            for resource_id in range(101, 108)
        ),
        encoding="utf-8",
    )
    database = root / "provider_intents.db"
    result = import_legacy_policy(policy, database, now=NOW)
    store = ProviderIntentStore.open_existing(database)
    assert store.mutate_coordinate(command(REQUEST_110, RESOURCE_110), now=NOW).outcome == "created"
    assert store.mutate_coordinate(
        command(REQUEST_200, RESOURCE_200), now=NOW + timedelta(seconds=1)
    ).outcome == "created"
    del store
    _checkpoint(database)
    return result.import_id


def _descriptor(resources: tuple[ProviderResource, ...]) -> ProviderManagementDescriptor:
    return ProviderManagementDescriptor(
        provider_id="proxmox", provider_name="Proxmox",
        sections=tuple(
            ProviderManagementSectionDescriptor(
                section=section,
                availability=ProviderManagementSectionAvailability.AVAILABLE,
            )
            for section in ProviderManagementSection
        ),
        resource_types=provider_resource_management_registry.for_provider("proxmox"),
        resources=tuple(project_managed_resource(item) for item in resources),
        provider_intent_activation="activated",
        provider_intent_authority_status="available",
    )


def _table_counts(database: Path) -> dict[str, int]:
    with sqlite3.connect(database) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "provider_intent_records", "provider_intent_requests",
                "provider_intent_audit", "provider_intent_active_coordinates",
                "provider_intent_operations", "provider_intent_operation_audit",
            )
        }


def verify(root: Path, expected_import_id: str) -> None:
    policy = root / "config/policies.yaml"
    database = root / "provider_intents.db"
    settings = ProviderIntentSettings(
        activation=ProviderIntentActivation.ACTIVATED, database=str(database),
        expected_legacy_import_id=expected_import_id,
    )
    store = validate_provider_intent_activation(settings, policy_path=policy)
    assert store is not None
    assert store.get_import_completion(load_legacy_policy_import(policy)) is not None
    snapshot = store.read_snapshot()
    assert len(snapshot.legacy_unbound_records) == 7
    active = {record.resource_id: record for record in snapshot.active_identity_bound_records}
    assert set(active) == {"110", "200"}
    assert all(record.intent_value is ProviderIntentValue.RUNNING for record in active.values())
    assert all(record.record_version == 1 for record in active.values())
    assert active["110"].incarnation_fingerprint == fingerprint(RESOURCE_110)
    assert active["200"].incarnation_fingerprint == fingerprint(RESOURCE_200)
    assert _table_counts(database)["provider_intent_active_coordinates"] == 2

    policy.write_text('proxmox:\n  guests:\n    "110":\n      expected: stopped\n', encoding="utf-8")
    policy_config.POLICY_FILE = policy
    authority = ProxmoxMonitoringIntentAuthority(settings, store)
    collection = ProviderResourceCollection(
        provider_id="proxmox", provider_name="Proxmox", refreshed_at=NOW,
        resources=[RESOURCE_110, RESOURCE_200],
        summary=ProviderResourceSummary(
            total=2, configured=0, needs_review=2, missing=0, ignored=0
        ),
    )
    resolved = authority.resolve_collection(collection)
    assert [item.expectation.value for item in resolved.resources] == ["running", "running"]
    assert not (root / "provider_intents.db-wal").exists()
    assert not (root / "provider_intents.db-shm").exists()


def verify_v3(root: Path, expected_import_id: str) -> None:
    from app.provider_intents.suggestions import (
        project_provider_monitoring_intent_suggestions,
    )

    database = root / "provider_intents.db"
    store = ProviderIntentStore.open_existing(database)
    before = _table_counts(database)
    original = store.mutate_coordinate(command(REQUEST_110, RESOURCE_110), now=NOW + timedelta(days=1))
    replay = store.mutate_coordinate(command(REQUEST_110, RESOURCE_110), now=NOW + timedelta(days=2))
    assert replay == original
    assert _table_counts(database) == before
    try:
        store.mutate_coordinate(
            ProviderIntentCoordinateMutationCommand(
                **{
                    **command(REQUEST_110, RESOURCE_110).model_dump(),
                    "desired_value": ProviderIntentValue.STOPPED,
                }
            ),
            now=NOW + timedelta(days=3),
        )
    except ProviderIntentStoreConflictError:
        pass
    else:
        raise AssertionError("changed content reused an accepted request ID")

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta WHERE singleton=1"
        ).fetchone() == (2,)
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_records WHERE lifecycle='legacy_unbound'"
        ).fetchone() == (7,)
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_operations WHERE operator_id='kenny'"
        ).fetchone() == (2,)
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_operation_audit WHERE operator_id='kenny'"
        ).fetchone() == (2,)
        assert connection.execute(
            "SELECT request_id FROM provider_intent_operations "
            "WHERE operator_id='kenny' ORDER BY request_id"
        ).fetchall() == [(REQUEST_110,), (REQUEST_200,)]
        assert connection.execute(
            "SELECT request_id FROM provider_intent_operation_audit "
            "WHERE operator_id='kenny' ORDER BY request_id"
        ).fetchall() == [(REQUEST_110,), (REQUEST_200,)]
        for request_id in (REQUEST_110, REQUEST_200):
            request_result = connection.execute(
                "SELECT result_json FROM provider_intent_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            operation_result = connection.execute(
                "SELECT result_json FROM provider_intent_operations WHERE request_id=?",
                (request_id,),
            ).fetchone()
            assert request_result is not None
            assert operation_result is not None
            durable_result = json.loads(request_result[0])
            operation_evidence = json.loads(operation_result[0])
            assert durable_result["outcome"] == operation_evidence["outcome"] == "created"
            assert durable_result["record"]["record_version"] == 1
            assert operation_evidence["request_id"] == request_id
            assert operation_evidence["record_version"] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_requests WHERE request_id=?",
            (expected_import_id,),
        ).fetchone() == (1,)

    digest_before = hashlib.sha256(database.read_bytes()).hexdigest()
    assert project_provider_monitoring_intent_suggestions(_descriptor(())) == ()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == digest_before

    replacement = resource("110", "33333333-3333-3333-3333-333333333333")
    proof = root / ".provider-intent-v3-replacement-proof.db"
    shutil.copy2(database, proof)
    try:
        proof_store = ProviderIntentStore.open_existing(proof)
        proof_settings = ProviderIntentSettings(
            activation=ProviderIntentActivation.ACTIVATED, database=str(proof),
            expected_legacy_import_id=expected_import_id,
        )
        authority = ProxmoxMonitoringIntentAuthority(proof_settings, proof_store)
        collection = ProviderResourceCollection(
            provider_id="proxmox", provider_name="Proxmox", refreshed_at=NOW,
            resources=[replacement],
            summary=ProviderResourceSummary(
                total=1, configured=0, needs_review=1, missing=0, ignored=0
            ),
        )
        current = authority.resolve_collection(collection).resources[0]
        assert current.expectation.value is None
        assert current.expectation.reason.value == "incarnation_mismatch"
        assert project_provider_monitoring_intent_suggestions(_descriptor((current,))) == ()
        rebound = proof_store.mutate_coordinate(
            command("provider-intent-mutation-" + "3" * 64, replacement),
            now=NOW + timedelta(days=4),
        )
        assert rebound.outcome == "rebound"
        assert proof_store.read_snapshot().active_identity_bound_records[0].incarnation_fingerprint == fingerprint(replacement)
    finally:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{proof}{suffix}")
            if candidate.exists():
                candidate.unlink()

    try:
        ProviderIntentCoordinateMutationCommand(
            **{
                **command("provider-intent-mutation-" + "4" * 64, RESOURCE_110).model_dump(),
                "resource_type": "lxc",
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("LXC mutation command did not fail closed")

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path("/opt/atlas/services/atlas-core/app/provider_intents/suggestions.py"),
            Path("/opt/atlas/services/atlas-core/app/routes/provider_intent_suggestions.py"),
        )
    )
    for forbidden in (
        "DiscoveryProposal", "intent_hint", "recommendation", ".details",
        "policies.yaml", "mutate_coordinate", "operational_dispatch",
        "execution_candidates", "provider_actions",
    ):
        assert forbidden not in combined


def stale(root: Path) -> None:
    for name in ("provider_intents.db-wal", "provider_intents.db-shm"):
        (root / name).write_bytes(f"stale-{name}".encode())
    (root / "config/policies.yaml").write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: stopped\n', encoding="utf-8"
    )
    (root / "operator_sessions.db").write_bytes(b"stale-session")
    sentinel = root / "providers/activated-sentinel"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("preserve", encoding="utf-8")


def main() -> None:
    action, root = sys.argv[1], Path(sys.argv[2])
    if action == "seed":
        print(json.dumps({"import_id": seed(root)}, sort_keys=True))
    elif action == "verify":
        verify(root, sys.argv[3])
        print("Activated Provider Intent recovery evidence passed")
    elif action == "verify-v3":
        verify_v3(root, sys.argv[3])
        print("Provider Intent recovery evidence v3 passed")
    elif action == "stale":
        stale(root)
    else:
        raise SystemExit("unknown action")


if __name__ == "__main__":
    main()
