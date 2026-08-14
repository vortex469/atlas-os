from datetime import UTC, datetime, timedelta

import pytest

from app.operational_dispatch.sandbox import (
    SandboxAuthorization,
    validate_sandbox_scope,
)
from app.operational_dispatch.test_support import make_request


def authorization(request, **changes) -> SandboxAuthorization:
    values = {
        "purpose": "approved-non-critical-qemu-graceful-restart",
        "node": "pve1",
        "vmid": request.resource_id,
        "request_digest": request.request_digest,
        "resource_fingerprint": request.target_fingerprint,
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "maximum_attempts": 1,
    }
    values.update(changes)
    return SandboxAuthorization.model_validate(values)


def test_sandbox_scope_binds_exact_target_and_single_attempt() -> None:
    request = make_request(resource_id="101")
    approval = authorization(request)
    validate_sandbox_scope(
        request,
        approval,
        node="pve1",
        vmid="101",
        fingerprint=request.target_fingerprint,
    )
    with pytest.raises(ValueError, match="exact request target"):
        validate_sandbox_scope(
            request,
            approval,
            node="pve2",
            vmid="101",
            fingerprint=request.target_fingerprint,
        )
    with pytest.raises(ValueError, match="exactly one attempt"):
        authorization(request, maximum_attempts=2)


def test_sandbox_rejects_unapproved_or_expired_noncritical_assertion() -> None:
    request = make_request(resource_id="101")
    with pytest.raises(ValueError, match="not approved as non-critical"):
        authorization(request, purpose="generic-restart")
    with pytest.raises(ValueError, match="expired"):
        authorization(request, expires_at=datetime.now(UTC) - timedelta(seconds=1))
