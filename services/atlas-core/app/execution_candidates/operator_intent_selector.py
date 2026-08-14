"""Sanitized, read-only selector for supported operator-intent resources."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from app.execution_candidates.models import ExecutionCandidateModel
from app.execution_candidates.operator_intents import validate_restart_target
from app.models.resources import ProviderResource, ProviderResourceCollection
from app.providers import ProviderNotFoundError
from app.services.provider_resources import (
    OperationalTargetIdentityUnavailableError,
    OperationalTargetResolutionError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    ResolvedOperationalTarget,
    list_provider_resources,
    resolve_operational_target,
)


class OperatorIntentResourceReason(StrEnum):
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    UNSUPPORTED_RESOURCE_TYPE = "unsupported_resource_type"
    STOPPED = "stopped"
    TEMPLATE = "template"
    LOCKED = "locked"
    MIGRATING = "migrating"
    UNAVAILABLE_STATE = "unavailable_state"


class OperatorIntentResource(ExecutionCandidateModel):
    provider_id: str
    resource_id: str
    resource_type: str
    display_name: str
    node: str
    current_state: str
    authoritative_identity_present: bool
    template: bool
    locked: bool
    migrating: bool
    operational_target_fingerprint: str | None = Field(
        default=None,
        pattern=r"^operational-target-fingerprint-v1:[a-f0-9]{64}$",
    )
    requestable: bool
    reason: OperatorIntentResourceReason | None = None


class OperatorIntentResourceCollection(ExecutionCandidateModel):
    execution_intent: str = "restart-service"
    provider_id: str = "proxmox"
    resource_type: str = "qemu"
    generated_at: datetime
    resources: tuple[OperatorIntentResource, ...]


class OperatorIntentResourceCollectionError(RuntimeError):
    """The authoritative selector cannot safely provide a current projection."""


ResourceCollector = Callable[[str], Awaitable[ProviderResourceCollection]]
TargetResolver = Callable[[str, str, str], Awaitable[ResolvedOperationalTarget]]


def _flags(resource: ProviderResource) -> tuple[bool, bool, bool]:
    metadata = resource.metadata
    template = bool(metadata.get("template"))
    lock = metadata.get("lock")
    locked = lock not in {None, ""}
    migrating = bool(metadata.get("migrating")) or lock == "migrate"
    return template, locked, migrating


def _sanitized(
    resource: ProviderResource,
    *,
    identity_present: bool,
    fingerprint: str | None,
    requestable: bool,
    reason: OperatorIntentResourceReason | None,
) -> OperatorIntentResource:
    template, locked, migrating = _flags(resource)
    return OperatorIntentResource(
        provider_id="proxmox",
        resource_id=resource.resource_id,
        resource_type=resource.resource_type,
        display_name=resource.display_name,
        node=str(resource.metadata.get("node") or "unknown"),
        current_state=resource.current_state,
        authoritative_identity_present=identity_present,
        template=template,
        locked=locked,
        migrating=migrating,
        operational_target_fingerprint=fingerprint,
        requestable=requestable,
        reason=reason,
    )


def _ineligible_reason(target: ResolvedOperationalTarget) -> OperatorIntentResourceReason | None:
    resource = target.resource
    template, locked, migrating = _flags(resource)
    if resource.identity is None:
        return OperatorIntentResourceReason.IDENTITY_UNAVAILABLE
    if resource.current_state != "running":
        return (
            OperatorIntentResourceReason.STOPPED
            if resource.current_state == "stopped"
            else OperatorIntentResourceReason.UNAVAILABLE_STATE
        )
    if template:
        return OperatorIntentResourceReason.TEMPLATE
    if migrating:
        return OperatorIntentResourceReason.MIGRATING
    if locked:
        return OperatorIntentResourceReason.LOCKED
    qmp = resource.metadata.get("qmp")
    if qmp is not None and qmp != "running":
        return OperatorIntentResourceReason.UNAVAILABLE_STATE
    return None


async def collect_operator_intent_resources(
    *,
    collector: ResourceCollector = list_provider_resources,
    resolver: TargetResolver = resolve_operational_target,
    now: datetime | None = None,
) -> OperatorIntentResourceCollection:
    try:
        collection = await collector("proxmox")
    except (ProviderNotFoundError, ProviderResourceOperationError, ProviderResourcesNotSupportedError) as error:
        raise OperatorIntentResourceCollectionError(
            "Authoritative operator-intent resources are temporarily unavailable."
        ) from error

    unique = {resource.resource_id: resource for resource in collection.resources}
    projected: list[OperatorIntentResource] = []
    for resource in unique.values():
        if resource.resource_type != "qemu":
            projected.append(
                _sanitized(
                    resource,
                    identity_present=False,
                    fingerprint=None,
                    requestable=False,
                    reason=OperatorIntentResourceReason.UNSUPPORTED_RESOURCE_TYPE,
                )
            )
            continue
        try:
            target = await resolver("proxmox", resource.resource_id, "qemu")
        except OperationalTargetIdentityUnavailableError:
            projected.append(
                _sanitized(
                    resource,
                    identity_present=False,
                    fingerprint=None,
                    requestable=False,
                    reason=OperatorIntentResourceReason.IDENTITY_UNAVAILABLE,
                )
            )
            continue
        except OperationalTargetResolutionError:
            projected.append(
                _sanitized(
                    resource,
                    identity_present=False,
                    fingerprint=None,
                    requestable=False,
                    reason=OperatorIntentResourceReason.UNAVAILABLE_STATE,
                )
            )
            continue
        except (ProviderNotFoundError, ProviderResourceOperationError, ProviderResourcesNotSupportedError) as error:
            raise OperatorIntentResourceCollectionError(
                "Authoritative operator-intent resources are temporarily unavailable."
            ) from error

        reason = _ineligible_reason(target)
        requestable = reason is None
        if requestable:
            try:
                validate_restart_target(target)
            except ValueError:
                requestable = False
                reason = OperatorIntentResourceReason.UNAVAILABLE_STATE
        projected.append(
            _sanitized(
                target.resource,
                identity_present=target.resource.identity is not None,
                fingerprint=target.resource_fingerprint,
                requestable=requestable,
                reason=reason,
            )
        )

    projected.sort(
        key=lambda item: (
            item.node,
            0 if item.resource_id.isdigit() else 1,
            int(item.resource_id) if item.resource_id.isdigit() else item.resource_id,
        )
    )
    return OperatorIntentResourceCollection(
        generated_at=(now or datetime.now(UTC)).astimezone(UTC),
        resources=tuple(projected),
    )
