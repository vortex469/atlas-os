import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.operational_dispatch.models import (
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalVerificationStatus,
)
from app.operational_dispatch.test_support import make_request, make_target
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.providers.proxmox_operational import (
    ProxmoxQemuGracefulRestartHandler,
    ProxmoxQemuVerificationService,
)
from app.services.operational_target_fingerprint import (
    build_operational_target_fingerprint,
)

VMGENID = "11111111-1111-1111-1111-111111111111"
UPID = "UPID:pve1:00000001:00000002:00000003:qmreboot:101:atlas@pve:"


def target(**changes: object):
    base = make_target(resource_id="101")
    identity = build_proxmox_qemu_identity(node="pve1", vmid=101, vmgenid=VMGENID)
    resource = base.resource.model_copy(
        update={
            "identity": identity,
            "metadata": {"node": "pve1", "vmid": 101, "template": False, "lock": None},
            **changes,
        }
    )
    return base.__class__(
        provider=base.provider,
        resource=resource,
        resource_fingerprint=base.resource_fingerprint,
    )


def client(
    *,
    status: str = "running",
    qmpstatus: str = "running",
    template: bool = False,
    lock: str | None = None,
    vmgenid: str = VMGENID,
    reboot_result: object = UPID,
):
    proxmox = MagicMock()
    qemu = proxmox.nodes.return_value.qemu.return_value
    qemu.status.current.get.return_value = {
        "status": status,
        "qmpstatus": qmpstatus,
        "lock": lock,
    }
    qemu.config.get.return_value = {
        "template": int(template),
        "lock": lock,
        "vmgenid": vmgenid,
    }
    qemu.status.reboot.post.return_value = reboot_result
    return proxmox


def run_handler(proxmox, *, resolved=None):
    request = make_request(resource_id="101")
    handler = ProxmoxQemuGracefulRestartHandler(
        MagicMock(), client_factory=lambda _context: proxmox
    )
    result = asyncio.run(handler(request, resolved or target()))
    return request, result


def test_running_qemu_uses_only_graceful_reboot_and_captures_upid() -> None:
    proxmox = client()
    request, result = run_handler(proxmox)
    assert result.status is OperationalDispatchStatus.SUCCEEDED
    assert result.provider_operation_id == UPID
    assert result.request_digest == request.request_digest
    qemu = proxmox.nodes.return_value.qemu.return_value
    qemu.status.reboot.post.assert_called_once_with()
    assert not hasattr(qemu.status, "reset") or not qemu.status.reset.called
    assert not hasattr(qemu.status, "stop") or not qemu.status.stop.called
    assert not hasattr(qemu.status, "start") or not qemu.status.start.called


@pytest.mark.parametrize(
    ("status", "qmpstatus", "template", "lock"),
    (
        ("stopped", "stopped", False, None),
        ("paused", "paused", False, None),
        ("running", "running", True, None),
        ("running", "running", False, "migrate"),
        ("unknown", "unknown", False, None),
    ),
)
def test_unsupported_live_states_fail_before_mutation(
    status: str, qmpstatus: str, template: bool, lock: str | None
) -> None:
    proxmox = client(status=status, qmpstatus=qmpstatus, template=template, lock=lock)
    _request, result = run_handler(proxmox)
    assert result.status is OperationalDispatchStatus.FAILED
    proxmox.nodes.return_value.qemu.return_value.status.reboot.post.assert_not_called()


def test_non_qemu_or_stale_target_fails_before_provider_call() -> None:
    proxmox = client()
    resolved = target(resource_type="lxc")
    _request, result = run_handler(proxmox, resolved=resolved)
    assert result.status is OperationalDispatchStatus.FAILED
    proxmox.nodes.assert_not_called()


def test_replaced_vmgenid_fails_before_mutation() -> None:
    proxmox = client(vmgenid="22222222-2222-2222-2222-222222222222")
    _request, result = run_handler(proxmox)
    assert result.status is OperationalDispatchStatus.FAILED
    proxmox.nodes.return_value.qemu.return_value.status.reboot.post.assert_not_called()


def test_replacement_under_same_vmid_changes_authoritative_fingerprint() -> None:
    original = target()
    replacement_identity = build_proxmox_qemu_identity(
        node="pve1",
        vmid=101,
        vmgenid="22222222-2222-2222-2222-222222222222",
    )
    replacement = original.resource.model_copy(update={"identity": replacement_identity})
    assert build_operational_target_fingerprint(
        original.provider, original.resource
    ) != build_operational_target_fingerprint(original.provider, replacement)


def test_provider_failure_is_sanitized_and_mutation_failure_is_not_retried() -> None:
    preflight = client()
    preflight.nodes.return_value.qemu.return_value.config.get.side_effect = RuntimeError(
        "token=must-not-leak"
    )
    _request, failed = run_handler(preflight)
    assert failed.status is OperationalDispatchStatus.FAILED
    assert "must-not-leak" not in failed.model_dump_json()

    ambiguous = client()
    reboot = ambiguous.nodes.return_value.qemu.return_value.status.reboot.post
    reboot.side_effect = RuntimeError("provider response with token=must-not-leak")
    _request, unknown = run_handler(ambiguous)
    assert unknown.status is OperationalDispatchStatus.OUTCOME_UNKNOWN
    assert "must-not-leak" not in unknown.model_dump_json()
    reboot.assert_called_once_with()


def dispatch_result(request, *, upid: str | None = UPID) -> OperationalDispatchResult:
    now = datetime.now(UTC)
    return OperationalDispatchResult(
        status=OperationalDispatchStatus.SUCCEEDED,
        request_id=request.request_id,
        request_digest=request.request_digest,
        target_fingerprint=request.target_fingerprint,
        provider_operation_id=upid,
        started_at=now,
        completed_at=now,
    )


def test_verification_requires_task_success_and_same_running_identity() -> None:
    request = make_request(resource_id="101")
    proxmox = client()
    proxmox.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "OK",
    }
    verifier = ProxmoxQemuVerificationService(
        MagicMock(),
        client_factory=lambda _context: proxmox,
        resolver=AsyncMock(return_value=target()),
        poll_interval_seconds=0,
    )
    result = asyncio.run(
        verifier.verify(
            request,
            dispatch_result(request),
            deadline=datetime.now(UTC) + timedelta(seconds=5),
        )
    )
    assert result.status is OperationalVerificationStatus.SUCCEEDED


def test_verification_reports_task_failure_and_target_replacement() -> None:
    request = make_request(resource_id="101")
    proxmox = client()
    proxmox.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "ERROR",
    }
    failed = ProxmoxQemuVerificationService(
        MagicMock(),
        client_factory=lambda _context: proxmox,
        resolver=AsyncMock(return_value=target()),
        poll_interval_seconds=0,
    )
    result = asyncio.run(
        failed.verify(
            request,
            dispatch_result(request),
            deadline=datetime.now(UTC) + timedelta(seconds=5),
        )
    )
    assert result.status is OperationalVerificationStatus.VERIFICATION_FAILED

    replaced_target = target()
    replaced_target = replaced_target.__class__(
        provider=replaced_target.provider,
        resource=replaced_target.resource,
        resource_fingerprint="operational-target-fingerprint-v1:replaced",
    )
    replaced = ProxmoxQemuVerificationService(
        MagicMock(),
        client_factory=lambda _context: proxmox,
        resolver=AsyncMock(return_value=replaced_target),
        poll_interval_seconds=0,
    )
    result = asyncio.run(
        replaced.verify(
            request,
            dispatch_result(request),
            deadline=datetime.now(UTC) + timedelta(seconds=5),
        )
    )
    assert result.status is OperationalVerificationStatus.TARGET_REPLACED


@dataclass
class Clock:
    values: list[datetime]

    def __call__(self) -> datetime:
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


def test_verification_timeout_is_unknown_and_never_reboots() -> None:
    request = make_request(resource_id="101")
    result = dispatch_result(request)
    deadline = result.started_at + timedelta(seconds=1)
    proxmox = client()
    proxmox.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "running"
    }
    clock = Clock([result.started_at, deadline, deadline])
    verifier = ProxmoxQemuVerificationService(
        MagicMock(),
        client_factory=lambda _context: proxmox,
        resolver=AsyncMock(return_value=target()),
        poll_interval_seconds=0,
        now=clock,
        sleep=AsyncMock(),
    )
    verified = asyncio.run(verifier.verify(request, result, deadline=deadline))
    assert verified.status is OperationalVerificationStatus.OUTCOME_UNKNOWN
    proxmox.nodes.return_value.qemu.return_value.status.reboot.post.assert_not_called()


def test_successful_task_without_running_guest_fails_at_deadline() -> None:
    request = make_request(resource_id="101")
    result = dispatch_result(request)
    deadline = result.started_at + timedelta(seconds=1)
    proxmox = client()
    proxmox.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "OK",
    }
    verifier = ProxmoxQemuVerificationService(
        MagicMock(),
        client_factory=lambda _context: proxmox,
        resolver=AsyncMock(return_value=target(current_state="stopped")),
        poll_interval_seconds=0,
        now=Clock([result.started_at, deadline, deadline]),
        sleep=AsyncMock(),
    )
    verified = asyncio.run(verifier.verify(request, result, deadline=deadline))
    assert verified.status is OperationalVerificationStatus.VERIFICATION_FAILED


def test_unavailable_task_status_is_unknown_at_deadline() -> None:
    request = make_request(resource_id="101")
    result = dispatch_result(request)
    deadline = result.started_at + timedelta(seconds=1)
    proxmox = client()
    proxmox.nodes.return_value.tasks.return_value.status.get.side_effect = RuntimeError(
        "task unavailable"
    )
    verifier = ProxmoxQemuVerificationService(
        MagicMock(),
        client_factory=lambda _context: proxmox,
        resolver=AsyncMock(return_value=target()),
        poll_interval_seconds=0,
        now=Clock([result.started_at, deadline, deadline]),
        sleep=AsyncMock(),
    )
    verified = asyncio.run(verifier.verify(request, result, deadline=deadline))
    assert verified.status is OperationalVerificationStatus.OUTCOME_UNKNOWN
