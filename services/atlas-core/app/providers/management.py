"""Static provider/resource management support registration."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.provider_management import (
    ProviderMonitoringExpectation,
    ProviderResourceManagementSupport,
)


class ProviderResourceManagementAlreadyRegisteredError(ValueError):
    """Raised when one provider/resource support key is registered twice."""


class ProviderResourceManagementNotRegisteredError(KeyError):
    """Raised when no static management support contract exists."""


class ProviderResourceManagementRegistry:
    """Immutable-after-construction lookup for management semantics only."""

    def __init__(
        self,
        registrations: Iterable[ProviderResourceManagementSupport] = (),
    ) -> None:
        registered: dict[
            tuple[str, str], ProviderResourceManagementSupport
        ] = {}
        for registration in registrations:
            key = (registration.provider_id, registration.resource_type)
            if key in registered:
                raise ProviderResourceManagementAlreadyRegisteredError(
                    "Provider resource management support is already registered "
                    f"for '{registration.provider_id}/{registration.resource_type}'."
                )
            registered[key] = registration
        self._registrations = registered

    def get(
        self,
        provider_id: str,
        resource_type: str,
    ) -> ProviderResourceManagementSupport:
        try:
            return self._registrations[(provider_id, resource_type)]
        except KeyError as error:
            raise ProviderResourceManagementNotRegisteredError(
                "Provider resource management support is not registered for "
                f"'{provider_id}/{resource_type}'."
            ) from error

    def for_provider(
        self,
        provider_id: str,
    ) -> tuple[ProviderResourceManagementSupport, ...]:
        return tuple(
            sorted(
                (
                    registration
                    for registration in self._registrations.values()
                    if registration.provider_id == provider_id
                ),
                key=lambda registration: registration.resource_type,
            )
        )

    def __len__(self) -> int:
        return len(self._registrations)


provider_resource_management_registry = ProviderResourceManagementRegistry(
    (
        ProviderResourceManagementSupport(
            provider_id="proxmox",
            resource_type="lxc",
            resource_readable=True,
            authoritative_identity_supported=False,
            provider_intent_capability_supported=False,
        ),
        ProviderResourceManagementSupport(
            provider_id="proxmox",
            resource_type="qemu",
            resource_readable=True,
            authoritative_identity_supported=True,
            provider_intent_capability_supported=True,
            supported_expectations=(
                ProviderMonitoringExpectation.RUNNING,
                ProviderMonitoringExpectation.STOPPED,
                ProviderMonitoringExpectation.IGNORED,
            ),
        ),
    )
)
