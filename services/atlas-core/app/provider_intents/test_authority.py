from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

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
from app.provider_intents.authority import (
    ProviderIntentMutationUnavailableError,
    ProxmoxMonitoringIntentAuthority,
)
from app.provider_intents.legacy_import import import_legacy_policy
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreCorruptionError,
)
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_management import project_managed_resource

NOW = datetime(2026, 8, 15, tzinfo=UTC)
IMPORT_ID = "provider-intent-legacy-policy-import-v1:" + "d" * 64


def _settings(database: Path, *, activated: bool) -> ProviderIntentSettings:
    return ProviderIntentSettings(
        activation=(
            ProviderIntentActivation.ACTIVATED
            if activated
            else ProviderIntentActivation.NOT_ACTIVATED
        ),
        database=str(database),
        expected_legacy_import_id=IMPORT_ID if activated else None,
    )


def _resource(
    resource_id: str,
    *,
    resource_type: str = "qemu",
    vmgenid: str | None = "11111111-1111-1111-1111-111111111111",
    state: str = "running",
) -> ProviderResource:
    identity = (
        build_proxmox_qemu_identity(
            node="node-a", vmid=resource_id, vmgenid=vmgenid
        )
        if resource_type == "qemu" and vmgenid is not None
        else None
    )
    return ProviderResource(
        provider_id="proxmox",
        resource_id=resource_id,
        display_name=f"Resource {resource_id}",
        resource_type=resource_type,
        current_state=state,
        identity=identity,
        expectation=ProviderResourceExpectation(),
        configured=False,
    )


def _collection(*resources: ProviderResource) -> ProviderResourceCollection:
    return ProviderResourceCollection(
        provider_id="proxmox",
        provider_name="Proxmox",
        refreshed_at=NOW,
        resources=list(resources),
        summary=ProviderResourceSummary(
            total=len(resources),
            configured=0,
            needs_review=len(resources),
            missing=0,
            ignored=0,
        ),
    )


def _command(
    request_id: str,
    resource_id: str,
    fingerprint: str,
    value: ProviderIntentValue = ProviderIntentValue.RUNNING,
) -> ProviderIntentMutationCommand:
    digest = build_provider_intent_request_digest(
        request_id=request_id,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id=resource_id,
        incarnation_fingerprint=fingerprint,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=value,
        expected_record_version=0,
    )
    return ProviderIntentMutationCommand(
        request_id=request_id,
        request_digest=digest,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id=resource_id,
        incarnation_fingerprint=fingerprint,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=value,
        expected_record_version=0,
    )


def test_inactive_authority_preserves_yaml_semantics_without_store_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: stopped\n'
        '    "999":\n      expected: running\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(policy_config, "POLICY_FILE", policy)
    authority = ProxmoxMonitoringIntentAuthority(
        _settings(tmp_path / "must-not-open.db", activated=False)
    )

    result = authority.resolve_collection(_collection(_resource("110")))
    by_id = {item.resource_id: item for item in result.resources}

    assert by_id["110"].expectation.value == "stopped"
    assert by_id["110"].configured is True
    assert by_id["999"].missing is True
    assert by_id["999"].expectation.value == "running"
    assert not (tmp_path / "must-not-open.db").exists()


def test_activated_authority_exact_match_replacement_lxc_and_missing(
    tmp_path: Path,
) -> None:
    database = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(database)
    matching = _resource("110")
    matching_fingerprint = project_managed_resource(matching).management_fingerprint
    assert matching_fingerprint is not None
    store.put(_command("matching", "110", matching_fingerprint), now=NOW)
    store.put(
        _command(
            "missing",
            "111",
            "provider-management-fingerprint-v1:" + "b" * 64,
            ProviderIntentValue.STOPPED,
        ),
        now=NOW,
    )
    store.put(
        _command(
            "absent",
            "112",
            "provider-management-fingerprint-v1:" + "c" * 64,
        ),
        now=NOW,
    )
    authority = ProxmoxMonitoringIntentAuthority(
        _settings(database, activated=True), store
    )

    result = authority.resolve_collection(
        _collection(
            matching,
            _resource(
                "111",
                vmgenid="22222222-2222-2222-2222-222222222222",
            ),
            _resource("109", resource_type="lxc", vmgenid=None),
        )
    )
    by_id = {item.resource_id: item for item in result.resources}

    assert by_id["110"].expectation.value == "running"
    assert by_id["110"].expectation.state == "configured"
    assert by_id["111"].expectation.reason.value == "incarnation_mismatch"
    assert by_id["111"].expectation.value is None
    assert by_id["109"].expectation.state == "unsupported"
    assert by_id["112"].missing is True
    assert by_id["112"].expectation.value == "running"
    assert result.intent_authority.value == "provider_intent"


def test_activated_legacy_evidence_is_review_only_and_write_is_rejected(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: running\n',
        encoding="utf-8",
    )
    database = tmp_path / "provider_intents.db"
    import_legacy_policy(policy, database, now=NOW)
    authority = ProxmoxMonitoringIntentAuthority(
        _settings(database, activated=True),
        ProviderIntentStore.open_existing(database),
    )
    before_policy = policy.read_bytes()
    before_database = database.read_bytes()

    resource = authority.resolve_collection(_collection(_resource("110"))).resources[0]
    assert resource.expectation.state == "needs_review"
    assert resource.expectation.value is None
    assert resource.expectation.legacy_review_available is True
    assert resource.expectation.legacy_expectation == "running"
    with pytest.raises(ProviderIntentMutationUnavailableError, match="until P3"):
        authority.update_guest_expectation("110", "stopped")
    assert policy.read_bytes() == before_policy
    assert database.read_bytes() == before_database


def test_activated_runtime_store_failure_degrades_whole_pass(tmp_path: Path) -> None:
    class FailedStore:
        def read_snapshot(self):
            raise ProviderIntentStoreCorruptionError("sensitive sqlite detail")

    authority = ProxmoxMonitoringIntentAuthority(
        _settings(tmp_path / "failed.db", activated=True),
        FailedStore(),  # type: ignore[arg-type]
    )
    result = authority.resolve_collection(
        _collection(_resource("110"), _resource("111"))
    )

    assert result.intent_authority_status == "unavailable"
    assert {item.expectation.state for item in result.resources} == {"unavailable"}
    assert "sensitive" not in result.model_dump_json()

    intelligence = authority.resolve_intelligence(
        (project_managed_resource(_resource("110")),)
    )
    assert intelligence.legacy_expectations == ()
    assert intelligence.provider_intent_resolution is not None
    assert intelligence.provider_intent_resolution.authority_available is False


def test_intelligence_consumer_does_not_select_authority_source() -> None:
    source = (
        Path(__file__).parents[1] / "intelligence" / "providers" / "proxmox.py"
    ).read_text(encoding="utf-8")
    assert ".activation" not in source
    assert "list_guest_expectations" not in source
    assert "resolve_projections" not in source
    assert "resolve_intelligence" in source
