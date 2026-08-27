"""Disabled-by-default typed Proxmox QEMU operational contracts."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.clients.proxmox_client import get_proxmox_client
from app.context import AtlasContext
from app.operational_dispatch.models import (
    OperationalDispatchRequest,
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.providers import ProviderNotFoundError
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_resource_identity import (
    OperationalTargetResolutionError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    ResolvedOperationalTarget,
    resolve_operational_target,
)

PROXMOX_QEMU_ACTION_ID = "proxmox-qemu-graceful-restart-v1"
_SUPPORTED_STATUS = "running"

ClientFactory = Callable[[AtlasContext], Any]
TargetResolver = Callable[[str, str, str], Awaitable[ResolvedOperationalTarget]]
Now = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


class ProxmoxQemuGracefulRestartHandler:
    """Issue exactly one graceful QEMU reboot after provider-native revalidation."""

    def __init__(
        self,
        atlas_context: AtlasContext,
        *,
        client_factory: ClientFactory = get_proxmox_client,
    ) -> None:
        self._atlas_context = atlas_context
        self._client_factory = client_factory

    async def __call__(
        self,
        request: OperationalDispatchRequest,
        target: ResolvedOperationalTarget,
    ) -> OperationalDispatchResult:
        started_at = datetime.now(UTC)
        if not _exact_contract(request, target):
            return _failed(request, started_at, "Operational QEMU contract is invalid.")
        node = target.resource.metadata.get("node")
        vmid = target.resource.metadata.get("vmid")
        if not isinstance(node, str) or not node or str(vmid) != request.resource_id:
            return _failed(request, started_at, "Operational QEMU identity is invalid.")
        try:
            client = self._client_factory(self._atlas_context)
            status_endpoint = client.nodes(node).qemu(vmid).status
            live_status = await asyncio.to_thread(status_endpoint.current.get)
            config = await asyncio.to_thread(
                client.nodes(node).qemu(vmid).config.get
            )
        except Exception:  # noqa: BLE001 - provider details must be sanitized
            return _failed(request, started_at, "Operational QEMU pre-state is unavailable.")
        if not _supported_live_state(live_status, config):
            return _failed(request, started_at, "Operational QEMU pre-state is unsupported.")
        try:
            live_identity = build_proxmox_qemu_identity(
                node=node,
                vmid=vmid,
                vmgenid=str(config.get("vmgenid", "")),
            )
        except ValueError:
            return _failed(request, started_at, "Operational QEMU identity is unavailable.")
        if target.resource.identity != live_identity:
            return _failed(request, started_at, "Operational QEMU target was replaced.")

        try:
            provider_result = await asyncio.to_thread(status_endpoint.reboot.post)
        except Exception:  # noqa: BLE001 - mutation may have crossed provider boundary
            return _unknown(request, started_at)
        upid = _validated_upid(provider_result)
        if upid is None:
            return _unknown(request, started_at)
        return OperationalDispatchResult(
            status=OperationalDispatchStatus.SUCCEEDED,
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            provider_operation_id=upid,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            sanitized_message="Graceful QEMU restart was accepted for verification.",
        )


class ProxmoxQemuVerificationService:
    """Bounded read-only verification of one returned QEMU reboot UPID."""

    def __init__(
        self,
        atlas_context: AtlasContext,
        *,
        client_factory: ClientFactory = get_proxmox_client,
        resolver: TargetResolver = resolve_operational_target,
        poll_interval_seconds: float = 1.0,
        now: Now = lambda: datetime.now(UTC),
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        if poll_interval_seconds < 0:
            raise ValueError("verification poll interval cannot be negative")
        self._atlas_context = atlas_context
        self._client_factory = client_factory
        self._resolver = resolver
        self._poll_interval_seconds = poll_interval_seconds
        self._now = now
        self._sleep = sleep

    async def verify(
        self,
        request: OperationalDispatchRequest,
        dispatch_result: OperationalDispatchResult,
        *,
        deadline: datetime,
    ) -> OperationalVerificationResult:
        started_at = dispatch_result.started_at
        if deadline <= started_at:
            raise ValueError("verification deadline must follow dispatch start")
        upid = _validated_upid(dispatch_result.provider_operation_id)
        if upid is None:
            return self._result(
                request,
                started_at,
                deadline,
                OperationalVerificationStatus.OUTCOME_UNKNOWN,
            )
        node = _upid_node(upid)
        client = self._client_factory(self._atlas_context)
        task_endpoint = client.nodes(node).tasks(upid).status
        last_target: ResolvedOperationalTarget | None = None
        task_succeeded = False
        while self._now() < deadline:
            target_status, target = await self._observe_target(request)
            if target_status is OperationalVerificationStatus.TARGET_REPLACED:
                return self._result(
                    request,
                    started_at,
                    deadline,
                    target_status,
                    target,
                )
            if target is not None:
                last_target = target
            try:
                task = await asyncio.to_thread(task_endpoint.get)
            except Exception:  # noqa: BLE001 - retry read-only observation until deadline
                task = None
            if isinstance(task, dict) and task.get("status") == "stopped":
                if task.get("exitstatus") != "OK":
                    return self._result(
                        request,
                        started_at,
                        deadline,
                        OperationalVerificationStatus.VERIFICATION_FAILED,
                        last_target,
                    )
                task_succeeded = True
            if (
                task_succeeded
                and last_target is not None
                and last_target.resource.current_state == "running"
            ):
                return self._result(
                    request,
                    started_at,
                    deadline,
                    OperationalVerificationStatus.SUCCEEDED,
                    last_target,
                )
            await self._sleep(self._poll_interval_seconds)

        status = (
            OperationalVerificationStatus.VERIFICATION_FAILED
            if task_succeeded
            else OperationalVerificationStatus.OUTCOME_UNKNOWN
        )
        return self._result(request, started_at, deadline, status, last_target)

    async def _observe_target(
        self, request: OperationalDispatchRequest
    ) -> tuple[OperationalVerificationStatus | None, ResolvedOperationalTarget | None]:
        try:
            target = await self._resolver(
                request.provider_id, request.resource_id, request.resource_type
            )
        except (
            OperationalTargetResolutionError,
            ProviderNotFoundError,
            ProviderResourcesNotSupportedError,
        ):
            return OperationalVerificationStatus.TARGET_REPLACED, None
        except ProviderResourceOperationError:
            return None, None
        if target.resource_fingerprint != request.target_fingerprint:
            return OperationalVerificationStatus.TARGET_REPLACED, target
        return None, target

    def _result(
        self,
        request: OperationalDispatchRequest,
        started_at: datetime,
        deadline: datetime,
        status: OperationalVerificationStatus,
        target: ResolvedOperationalTarget | None = None,
    ) -> OperationalVerificationResult:
        return OperationalVerificationResult(
            status=status,
            request_id=request.request_id,
            observed_target_fingerprint=(
                target.resource_fingerprint if target is not None else None
            ),
            observed_state=(
                target.resource.current_state if target is not None else None
            ),
            health_status=(
                target.resource.current_state if target is not None else None
            ),
            started_at=started_at,
            completed_at=self._now(),
            deadline=deadline,
        )


def _exact_contract(
    request: OperationalDispatchRequest, target: ResolvedOperationalTarget
) -> bool:
    return (
        request.execution_intent == "restart-service"
        and request.provider_id == "proxmox"
        and request.resource_type == "qemu"
        and request.provider_action_id == PROXMOX_QEMU_ACTION_ID
        and request.expected_pre_state == _SUPPORTED_STATUS
        and request.verification.pre_state == _SUPPORTED_STATUS
        and target.provider.id == "proxmox"
        and target.resource.provider_id == "proxmox"
        and target.resource.resource_type == "qemu"
        and target.resource.resource_id == request.resource_id
        and target.resource.current_state == _SUPPORTED_STATUS
        and target.resource_fingerprint == request.target_fingerprint
        and not bool(target.resource.metadata.get("template"))
        and not target.resource.metadata.get("lock")
    )


def _supported_live_state(status: Any, config: Any) -> bool:
    return (
        isinstance(status, dict)
        and isinstance(config, dict)
        and status.get("status") == _SUPPORTED_STATUS
        and status.get("qmpstatus", _SUPPORTED_STATUS) == _SUPPORTED_STATUS
        and not bool(config.get("template"))
        and not config.get("lock")
        and not status.get("lock")
        and bool(config.get("vmgenid"))
    )


def _validated_upid(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("UPID:"):
        return None
    if len(value) > 512 or value != value.strip() or any(char.isspace() for char in value):
        return None
    parts = value.split(":")
    return value if len(parts) >= 9 and parts[1] else None


def _upid_node(upid: str) -> str:
    return upid.split(":", 2)[1]


def _failed(
    request: OperationalDispatchRequest, started_at: datetime, message: str
) -> OperationalDispatchResult:
    return OperationalDispatchResult(
        status=OperationalDispatchStatus.FAILED,
        request_id=request.request_id,
        request_digest=request.request_digest,
        target_fingerprint=request.target_fingerprint,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        sanitized_message=message,
    )


def _unknown(
    request: OperationalDispatchRequest, started_at: datetime
) -> OperationalDispatchResult:
    return OperationalDispatchResult(
        status=OperationalDispatchStatus.OUTCOME_UNKNOWN,
        request_id=request.request_id,
        request_digest=request.request_digest,
        target_fingerprint=request.target_fingerprint,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        sanitized_message="Graceful QEMU restart outcome is unknown.",
    )
