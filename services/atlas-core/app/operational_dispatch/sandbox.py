"""Explicit one-shot harness for a future authorized QEMU sandbox exercise."""

from __future__ import annotations

import argparse
import asyncio
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.operational_dispatch.ledger import OperationalDispatchLedger
from app.operational_dispatch.lifecycle import (
    OperationalLifecycleService,
    OperationalVerifierRegistry,
)
from app.operational_dispatch.models import OperationalDispatchRequest
from app.operational_dispatch.registry import (
    OperationalHandlerRegistration,
    OperationalHandlerRegistry,
)
from app.operational_dispatch.service import OperationalDispatchService
from app.providers.loader import load_provider_registry
from app.providers.proxmox import ProxmoxProvider
from app.providers.proxmox_operational import (
    ProxmoxQemuGracefulRestartHandler,
    ProxmoxQemuVerificationService,
)
from app.providers.registry import provider_registry
from app.services.provider_resource_identity import resolve_operational_target

_PRODUCTION_LEDGER = Path("/opt/atlas/data/operational_dispatch.db")


class SandboxAuthorization(BaseModel):
    """Separate expiring operator assertion for one non-critical target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    purpose: str
    node: str
    vmid: str
    request_digest: str
    resource_fingerprint: str
    expires_at: datetime
    maximum_attempts: int

    @field_validator("purpose", "node", "vmid", "request_digest", "resource_fingerprint")
    @classmethod
    def exact_nonblank(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("sandbox authorization values must be exact and nonblank")
        return value

    @model_validator(mode="after")
    def exact_scope(self) -> SandboxAuthorization:
        if self.schema_version != 1:
            raise ValueError("unsupported sandbox authorization schema")
        if self.purpose != "approved-non-critical-qemu-graceful-restart":
            raise ValueError("sandbox target is not approved as non-critical")
        if self.maximum_attempts != 1:
            raise ValueError("sandbox authorization must permit exactly one attempt")
        if self.expires_at <= datetime.now(UTC):
            raise ValueError("sandbox authorization is expired")
        return self


def validate_sandbox_scope(
    request: OperationalDispatchRequest,
    authorization: SandboxAuthorization,
    *,
    node: str,
    vmid: str,
    fingerprint: str,
) -> None:
    if (
        request.execution_intent != "restart-service"
        or request.provider_id != "proxmox"
        or request.resource_type != "qemu"
        or request.provider_action_id != "proxmox-qemu-graceful-restart-v1"
        or request.resource_id != vmid
        or request.request_digest != authorization.request_digest
        or request.target_fingerprint != authorization.resource_fingerprint
        or authorization.node != node
        or authorization.vmid != vmid
        or authorization.resource_fingerprint != fingerprint
    ):
        raise ValueError("sandbox authorization does not bind the exact request target")


def _load_private_model(path: Path, model_type):
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o400 or metadata.st_uid != os.getuid():
        raise PermissionError(
            "sandbox input files must be caller-owned with mode 0400"
        )
    return model_type.model_validate_json(path.read_bytes())


def print_sandbox_evidence(
    ledger: OperationalDispatchLedger,
    request: OperationalDispatchRequest,
) -> None:
    print("durable ledger transitions:")
    for transition in ledger.list_transitions(request.request_id):
        previous = transition.previous_state.value if transition.previous_state else "initial"
        print(
            f"  {transition.sequence}: {previous} -> {transition.state.value} "
            f"at {transition.occurred_at.isoformat()}"
        )
    print("sanitized operational audit events:")
    events = tuple(
        event
        for event in reversed(ledger.list_events(limit=1000))
        if event.request_id == request.request_id
    )
    for event in events:
        print(f"  {event.status.value} at {event.occurred_at.isoformat()}")


def print_sandbox_preflight(
    request: OperationalDispatchRequest,
    *,
    ledger_path: Path,
    node: str,
    vmid: str,
    display_name: str,
    current_state: str | None,
    resource_fingerprint: str,
) -> None:
    print(f"node: {node}")
    print(f"VMID: {vmid}")
    print(f"VM name: {display_name}")
    print(f"current state: {current_state}")
    print(f"resource fingerprint: {resource_fingerprint}")
    print(f"request digest: {request.request_digest}")
    print(f"provider action ID: {request.provider_action_id}")
    print(f"sandbox ledger path: {ledger_path}")
    print(f"expected disruption: {request.disruption_scope}")
    print(f"verification deadline: {request.expires_at.isoformat()}")


async def _run(args: argparse.Namespace) -> int:
    request = _load_private_model(args.request_file, OperationalDispatchRequest)
    authorization = _load_private_model(
        args.authorization_file, SandboxAuthorization
    )
    if args.ledger == _PRODUCTION_LEDGER or args.ledger.exists():
        raise ValueError("sandbox ledger must be a new non-production path")
    load_provider_registry()
    provider = provider_registry.get("proxmox")
    if not isinstance(provider, ProxmoxProvider):
        raise TypeError("Proxmox provider is unavailable")
    target = await resolve_operational_target(
        request.provider_id, request.resource_id, request.resource_type
    )
    node = target.resource.metadata.get("node")
    vmid = str(target.resource.metadata.get("vmid"))
    if not isinstance(node, str):
        raise TypeError("sandbox target node is unavailable")
    validate_sandbox_scope(
        request,
        authorization,
        node=node,
        vmid=vmid,
        fingerprint=target.resource_fingerprint,
    )
    print_sandbox_preflight(
        request,
        ledger_path=args.ledger,
        node=node,
        vmid=vmid,
        display_name=target.resource.display_name,
        current_state=target.resource.current_state,
        resource_fingerprint=target.resource_fingerprint,
    )
    phrase = f"RESTART {node} {vmid} {request.request_digest}"
    if input(f"Type exactly '{phrase}' to continue: ") != phrase:
        raise PermissionError("sandbox confirmation did not match")

    handler = ProxmoxQemuGracefulRestartHandler(provider.atlas_context)
    handlers = OperationalHandlerRegistry(
        (
            OperationalHandlerRegistration(
                "restart-service", "proxmox", "qemu", handler
            ),
        )
    )
    ledger = OperationalDispatchLedger(args.ledger)
    args.ledger.chmod(0o600)
    dispatcher = OperationalDispatchService(
        ledger=ledger,
        registry=handlers,
        execution_intents=frozenset({"restart-service"}),
    )
    verifier_service = ProxmoxQemuVerificationService(provider.atlas_context)
    verifiers = OperationalVerifierRegistry()

    async def verify(approved_request, result, deadline):
        return await verifier_service.verify(
            approved_request, result, deadline=deadline
        )

    verifiers.register(
        execution_intent="restart-service",
        provider_id="proxmox",
        resource_type="qemu",
        verifier=verify,
    )
    lifecycle = OperationalLifecycleService(
        ledger=ledger,
        dispatcher=dispatcher,
        verifiers=verifiers,
    )
    dispatch = await dispatcher.dispatch(request)
    await lifecycle.reconcile(request.request_id)
    final = lifecycle.status(request.request_id)
    print(f"dispatch status: {dispatch.status.value}")
    print(f"provider operation captured: {dispatch.provider_operation_id is not None}")
    print(f"final ledger state: {final.ledger_state if final else 'unknown'}")
    print_sandbox_evidence(ledger, request)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--authorization-file", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
