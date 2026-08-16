from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.models.resources import (
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceSummary,
)
from app.provider_intents.target_resolver import (
    ProviderIntentTargetFailureReason,
    ProviderIntentTargetResolutionError,
    resolve_provider_intent_mutation_target,
)
from app.providers import ProviderNotFoundError
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_management import project_managed_resource


def resource(
    *,
    resource_type: str = "qemu",
    resource_id: str = "110",
    vmgenid: str = "11111111-1111-1111-1111-111111111111",
    missing: bool = False,
    identity: bool = True,
) -> ProviderResource:
    return ProviderResource(
        provider_id="proxmox",
        resource_id=resource_id,
        resource_type=resource_type,
        display_name=f"Resource {resource_id}",
        current_state="missing" if missing else "running",
        identity=(
            build_proxmox_qemu_identity(
                node="node-a", vmid=resource_id, vmgenid=vmgenid
            )
            if identity and resource_type == "qemu"
            else None
        ),
        expectation=ProviderResourceExpectation(),
        configured=False,
        missing=missing,
    )


def collection(resources: list[ProviderResource]) -> ProviderResourceCollection:
    return ProviderResourceCollection(
        provider_id="proxmox",
        provider_name="Proxmox",
        refreshed_at=datetime(2026, 8, 15, tzinfo=UTC),
        resources=resources,
        summary=ProviderResourceSummary(
            total=len(resources),
            configured=0,
            needs_review=len(resources),
            missing=sum(item.missing for item in resources),
            ignored=0,
        ),
    )


class ReadOnlyProbeProvider:
    def __init__(
        self,
        resources: list[ProviderResource],
        *,
        read_error: bool = False,
    ) -> None:
        self.resources = resources
        self.read_error = read_error
        self.list_calls = 0
        self.refresh_calls = 0
        self.update_calls = 0

    async def list_resources(self):
        self.list_calls += 1
        if self.read_error:
            raise RuntimeError("native provider secret")
        return collection(self.resources)

    async def refresh_resources(self):
        self.refresh_calls += 1
        raise AssertionError("refresh must not be called")

    async def update_resource_expectation(self, resource_id, expectation):
        self.update_calls += 1
        raise AssertionError("update must not be called")

    def expectation_options(self, resource_type):
        return []

    def normalize_expectation(self, resource_type, expectation):
        return expectation

    def expectation_label(self, resource_type, expectation):
        return str(expectation)


async def resolve(monkeypatch: pytest.MonkeyPatch, provider, **updates):
    import app.provider_intents.target_resolver as resolver

    monkeypatch.setattr(resolver, "get_provider", lambda provider_id: provider)
    current = resource()
    values = {
        "provider_id": "proxmox",
        "resource_type": "qemu",
        "resource_id": "110",
        "expected_management_fingerprint": (
            project_managed_resource(current).management_fingerprint
        ),
    }
    values.update(updates)
    return await resolve_provider_intent_mutation_target(**values)


def test_exact_qemu_is_verified_without_refresh_or_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = resource()
    provider = ReadOnlyProbeProvider([current])
    target = asyncio.run(resolve(monkeypatch, provider))
    assert target.management_fingerprint == project_managed_resource(
        current
    ).management_fingerprint
    assert provider.list_calls == 1
    assert provider.refresh_calls == provider.update_calls == 0
    assert set(target.model_dump()) == {
        "provider_id", "resource_type", "resource_id", "management_fingerprint"
    }


@pytest.mark.parametrize(
    ("resources", "updates", "reason"),
    (
        ([resource()], {"expected_management_fingerprint": "provider-management-fingerprint-v1:" + "f" * 64}, ProviderIntentTargetFailureReason.FINGERPRINT_MISMATCH),
        ([resource(identity=False)], {}, ProviderIntentTargetFailureReason.IDENTITY_UNAVAILABLE),
        ([resource(missing=True)], {}, ProviderIntentTargetFailureReason.RESOURCE_MISSING),
        ([], {}, ProviderIntentTargetFailureReason.COORDINATE_NOT_FOUND),
        ([resource(), resource()], {}, ProviderIntentTargetFailureReason.COORDINATE_AMBIGUOUS),
        ([resource(resource_type="lxc")], {"resource_type": "lxc"}, ProviderIntentTargetFailureReason.UNSUPPORTED_RESOURCE_TYPE),
    ),
)
def test_target_failures_are_closed(
    monkeypatch: pytest.MonkeyPatch,
    resources,
    updates,
    reason,
) -> None:
    provider = ReadOnlyProbeProvider(resources)
    with pytest.raises(ProviderIntentTargetResolutionError) as captured:
        asyncio.run(resolve(monkeypatch, provider, **updates))
    assert captured.value.reason is reason
    assert provider.refresh_calls == provider.update_calls == 0


def test_unknown_provider_and_read_failure_do_not_leak_native_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.provider_intents.target_resolver as resolver

    def missing(provider_id):
        raise ProviderNotFoundError(provider_id)

    monkeypatch.setattr(resolver, "get_provider", missing)
    with pytest.raises(ProviderIntentTargetResolutionError) as captured:
        asyncio.run(
            resolve_provider_intent_mutation_target(
                provider_id="missing",
                resource_type="qemu",
                resource_id="110",
                expected_management_fingerprint=(
                    "provider-management-fingerprint-v1:" + "a" * 64
                ),
            )
        )
    assert captured.value.reason is ProviderIntentTargetFailureReason.PROVIDER_NOT_FOUND

    provider = ReadOnlyProbeProvider([resource()], read_error=True)
    with pytest.raises(ProviderIntentTargetResolutionError) as captured:
        asyncio.run(resolve(monkeypatch, provider))
    assert captured.value.reason is ProviderIntentTargetFailureReason.PROVIDER_READ_UNAVAILABLE
    assert "native provider secret" not in str(captured.value)
