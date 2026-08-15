"""Activated Provider Intent fixture and authority proof for recovery gates."""

from __future__ import annotations

import gc
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import policies as policy_config
from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.models.provider_intents import (
    ProviderIntentKind,
    ProviderIntentMutationCommand,
    ProviderIntentValue,
    build_provider_intent_request_digest,
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
from app.provider_intents.store import ProviderIntentStore
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_management import project_managed_resource

NOW = datetime(2026, 8, 15, tzinfo=UTC)
VMGENID = "11111111-1111-1111-1111-111111111111"


def resource() -> ProviderResource:
    return ProviderResource(
        provider_id="proxmox",
        resource_id="110",
        display_name="Recovery QEMU",
        resource_type="qemu",
        current_state="running",
        identity=build_proxmox_qemu_identity(node="node-a", vmid="110", vmgenid=VMGENID),
        expectation=ProviderResourceExpectation(),
        configured=False,
    )


def seed(root: Path) -> str:
    policy = root / "config/policies.yaml"
    database = root / "provider_intents.db"
    result = import_legacy_policy(policy, database, now=NOW)
    fingerprint = project_managed_resource(resource()).management_fingerprint
    assert fingerprint is not None
    request_id = "provider-intent-recovery-gate-active-qemu"
    digest = build_provider_intent_request_digest(
        request_id=request_id,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=fingerprint,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=ProviderIntentValue.RUNNING,
        expected_record_version=0,
    )
    store = ProviderIntentStore(database)
    store.put(
        ProviderIntentMutationCommand(
            request_id=request_id,
            request_digest=digest,
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            incarnation_fingerprint=fingerprint,
            intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
            desired_value=ProviderIntentValue.RUNNING,
            expected_record_version=0,
        ),
        now=NOW,
    )
    del store
    gc.collect()
    with sqlite3.connect(database, isolation_level=None) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
    os.chmod(database, 0o600)
    return result.import_id


def verify(root: Path, expected_import_id: str) -> None:
    policy = root / "config/policies.yaml"
    database = root / "provider_intents.db"
    settings = ProviderIntentSettings(
        activation=ProviderIntentActivation.ACTIVATED,
        database=str(database),
        expected_legacy_import_id=expected_import_id,
    )
    store = validate_provider_intent_activation(settings, policy_path=policy)
    assert store is not None
    expected_import = load_legacy_policy_import(policy)
    assert store.get_import_completion(expected_import) is not None
    snapshot = store.read_snapshot()
    assert len(snapshot.active_identity_bound_records) == 1
    assert snapshot.active_identity_bound_records[0].resource_id == "110"
    assert len(snapshot.legacy_unbound_records) == 1

    policy.write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: stopped\n',
        encoding="utf-8",
    )
    policy_config.POLICY_FILE = policy
    authority = ProxmoxMonitoringIntentAuthority(settings, store)
    collection = ProviderResourceCollection(
        provider_id="proxmox",
        provider_name="Proxmox",
        refreshed_at=NOW,
        resources=[resource()],
        summary=ProviderResourceSummary(
            total=1, configured=0, needs_review=1, missing=0, ignored=0
        ),
    )
    resolved = authority.resolve_collection(collection)
    assert resolved.resources[0].expectation.value == "running"
    assert resolved.resources[0].configured is True
    assert not (root / "provider_intents.db-wal").exists()
    assert not (root / "provider_intents.db-shm").exists()


def stale(root: Path) -> None:
    for name in ("provider_intents.db-wal", "provider_intents.db-shm"):
        (root / name).write_bytes(f"stale-{name}".encode())
    (root / "config/policies.yaml").write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: stopped\n',
        encoding="utf-8",
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
    elif action == "stale":
        stale(root)
    else:
        raise SystemExit("unknown action")


if __name__ == "__main__":
    main()
