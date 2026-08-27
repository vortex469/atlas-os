"""Read-only exact Proxmox QEMU destination resolution."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable

from app.installation_targets.contract import ProspectiveInstallationDestinationV1
from app.installation_targets.fingerprint import (
    build_destination_fingerprint,
    build_enumeration_token,
)
from app.services.operational_target_fingerprint import (
    OperationalTargetIdentityUnavailableError,
    build_operational_target_fingerprint,
)
from app.services.provider_resource_identity import (
    ResolvedOperationalTarget,
    get_provider,
    list_provider_resource_identities,
    resolve_operational_target,
)


class DestinationResolutionError(RuntimeError):
    """Sanitized fail-closed resolution failure."""


class DestinationNotSelectableError(DestinationResolutionError):
    pass


TargetResolver = Callable[[str, str, str], Awaitable[ResolvedOperationalTarget]]


def project_destination(
    target: ResolvedOperationalTarget,
) -> ProspectiveInstallationDestinationV1:
    resource = target.resource
    if (
        target.provider.id != "proxmox"
        or resource.provider_id != "proxmox"
        or resource.resource_type != "qemu"
    ):
        raise DestinationNotSelectableError("unsupported destination tuple")
    if resource.identity is None or resource.missing:
        raise DestinationNotSelectableError("destination identity unavailable")
    if resource.current_state not in {"running", "stopped"}:
        raise DestinationNotSelectableError("destination state is not selectable")
    metadata = resource.metadata
    if "template" not in metadata or type(metadata["template"]) is not bool:
        raise DestinationNotSelectableError("destination template state is unavailable")
    if metadata["template"]:
        raise DestinationNotSelectableError("templates are not selectable")
    if "lock" not in metadata or not isinstance(metadata["lock"], (str, type(None))):
        raise DestinationNotSelectableError("destination lock state is unavailable")
    if metadata["lock"] not in {None, ""}:
        raise DestinationNotSelectableError("locked guests are not selectable")
    if type(metadata.get("migrating")) is not bool:
        raise DestinationNotSelectableError(
            "destination migration state is unavailable"
        )
    if metadata["migrating"]:
        raise DestinationNotSelectableError("migrating guests are not selectable")
    fingerprint = build_destination_fingerprint(
        resource_id=resource.resource_id,
        operational_fingerprint=target.resource_fingerprint,
    )
    return ProspectiveInstallationDestinationV1(
        resource_id=resource.resource_id,
        destination_fingerprint=fingerprint,
        enumeration_token=build_enumeration_token(
            resource_id=resource.resource_id, destination_fingerprint=fingerprint
        ),
    )


async def resolve_destination(
    resource_id: str, *, resolver: TargetResolver = resolve_operational_target
) -> ProspectiveInstallationDestinationV1:
    try:
        return project_destination(await resolver("proxmox", resource_id, "qemu"))
    except DestinationResolutionError:
        raise
    except Exception as error:
        raise DestinationResolutionError("destination is unavailable") from error


async def resolve_destination_identity(
    resource_id: str, *, resolver: TargetResolver = resolve_operational_target
) -> str:
    """Resolve identity without treating a later eligibility change as rebinding."""
    try:
        target = await resolver("proxmox", resource_id, "qemu")
        resource = target.resource
        if (
            target.provider.id != "proxmox"
            or resource.provider_id != "proxmox"
            or resource.resource_type != "qemu"
            or resource.identity is None
            or resource.missing
        ):
            raise DestinationResolutionError("destination identity unavailable")
        return build_destination_fingerprint(
            resource_id=resource.resource_id,
            operational_fingerprint=target.resource_fingerprint,
        )
    except DestinationResolutionError:
        raise
    except Exception as error:
        raise DestinationResolutionError("destination identity unavailable") from error


async def enumerate_destinations() -> tuple[ProspectiveInstallationDestinationV1, ...]:
    """Enumerate only selectable guests from the existing provider read path."""
    try:
        provider = get_provider("proxmox")
        collection = await list_provider_resource_identities("proxmox")
        if collection.provider_id != "proxmox":
            raise DestinationResolutionError("provider resource state is inconsistent")
        qemus = [
            resource
            for resource in collection.resources
            if resource.resource_type == "qemu"
        ]
        duplicates = {
            resource_id
            for resource_id, count in Counter(
                resource.resource_id for resource in qemus
            ).items()
            if count > 1
        }
        if duplicates:
            raise DestinationResolutionError("destination identity is ambiguous")
        destinations = []
        for resource in qemus:
            try:
                fingerprint = build_operational_target_fingerprint(
                    provider.metadata, resource
                )
                destinations.append(
                    project_destination(
                        ResolvedOperationalTarget(
                            provider=provider.metadata.model_copy(deep=True),
                            resource=resource.model_copy(deep=True),
                            resource_fingerprint=fingerprint,
                        )
                    )
                )
            except (
                DestinationNotSelectableError,
                OperationalTargetIdentityUnavailableError,
            ):
                continue
        return tuple(sorted(destinations, key=lambda item: int(item.resource_id)))
    except DestinationResolutionError:
        raise
    except Exception as error:
        raise DestinationResolutionError("destinations are unavailable") from error
