import pytest
from pydantic import ValidationError

from app.models.provider_management import (
    ProviderMonitoringExpectation,
    ProviderResourceManagementSupport,
)
from app.providers.management import (
    ProviderResourceManagementAlreadyRegisteredError,
    ProviderResourceManagementNotRegisteredError,
    ProviderResourceManagementRegistry,
    provider_resource_management_registry,
)


def _qemu_support() -> ProviderResourceManagementSupport:
    return ProviderResourceManagementSupport(
        provider_id="proxmox",
        resource_type="qemu",
        resource_readable=True,
        authoritative_identity_supported=True,
        provider_intent_capability_supported=True,
        supported_expectations=(ProviderMonitoringExpectation.RUNNING,),
    )


def test_registration_is_deterministic() -> None:
    qemu = _qemu_support()
    lxc = ProviderResourceManagementSupport(
        provider_id="proxmox",
        resource_type="lxc",
        resource_readable=True,
        authoritative_identity_supported=False,
        provider_intent_capability_supported=False,
    )

    forward = ProviderResourceManagementRegistry((qemu, lxc))
    reverse = ProviderResourceManagementRegistry((lxc, qemu))

    assert forward.for_provider("proxmox") == reverse.for_provider("proxmox")
    assert tuple(
        item.resource_type for item in forward.for_provider("proxmox")
    ) == ("lxc", "qemu")


def test_duplicate_registration_fails_deterministically() -> None:
    qemu = _qemu_support()
    with pytest.raises(
        ProviderResourceManagementAlreadyRegisteredError,
        match="proxmox/qemu",
    ):
        ProviderResourceManagementRegistry((qemu, qemu))


def test_unknown_provider_resource_registration_fails_closed() -> None:
    with pytest.raises(
        ProviderResourceManagementNotRegisteredError,
        match="proxmox/unknown",
    ):
        provider_resource_management_registry.get("proxmox", "unknown")
    with pytest.raises(ProviderResourceManagementNotRegisteredError):
        provider_resource_management_registry.get("unknown", "qemu")
    assert provider_resource_management_registry.for_provider("unknown") == ()


@pytest.mark.parametrize(
    "values",
    (
        {
            "resource_readable": False,
            "authoritative_identity_supported": True,
            "provider_intent_capability_supported": False,
        },
        {
            "resource_readable": True,
            "authoritative_identity_supported": False,
            "provider_intent_capability_supported": True,
            "supported_expectations": (
                ProviderMonitoringExpectation.RUNNING,
            ),
        },
        {
            "resource_readable": True,
            "authoritative_identity_supported": True,
            "provider_intent_capability_supported": False,
            "supported_expectations": (
                ProviderMonitoringExpectation.RUNNING,
            ),
        },
    ),
)
def test_invalid_registration_combinations_are_rejected(
    values: dict,
) -> None:
    with pytest.raises(ValidationError):
        ProviderResourceManagementSupport(
            provider_id="proxmox",
            resource_type="qemu",
            **values,
        )


def test_provider_intent_mutation_cannot_be_enabled_in_p1b() -> None:
    with pytest.raises(ValidationError):
        ProviderResourceManagementSupport(
            provider_id="proxmox",
            resource_type="qemu",
            resource_readable=True,
            authoritative_identity_supported=True,
            provider_intent_capability_supported=True,
            provider_intent_mutation_available=True,
            supported_expectations=(ProviderMonitoringExpectation.RUNNING,),
        )


def test_supported_expectations_require_canonical_contract_order() -> None:
    with pytest.raises(ValidationError, match="canonical contract order"):
        ProviderResourceManagementSupport(
            provider_id="proxmox",
            resource_type="qemu",
            resource_readable=True,
            authoritative_identity_supported=True,
            provider_intent_capability_supported=True,
            supported_expectations=(
                ProviderMonitoringExpectation.STOPPED,
                ProviderMonitoringExpectation.RUNNING,
            ),
        )
