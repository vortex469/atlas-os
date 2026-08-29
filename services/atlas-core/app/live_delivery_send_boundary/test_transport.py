from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from app.dormant_agent_intake_delivery_wiring.test_contract import admitted_validation
from app.live_delivery_send_boundary.test_contract import _create
from app.live_delivery_send_boundary.test_service import _service
from app.live_delivery_send_boundary.transport import (
    LiveDeliveryHttpResponse,
    LiveDeliverySendCoordinator,
    LiveDeliveryTransportUncertain,
    ResolvedBearerCredential,
)
from app.operator_controlled_delivery_enablement.test_contract import OPERATOR


@dataclass
class Resolver:
    secret: bytes = b"super-secret-token"
    calls: int = 0

    def resolve_once(self, reference):
        self.calls += 1
        assert reference.credential_file == "/run/secrets/atlas-agent-intake-token"
        return ResolvedBearerCredential(self.secret)


@dataclass
class Transport:
    response: LiveDeliveryHttpResponse | Exception
    calls: list[dict] = field(default_factory=list)

    def transmit_once(self, **values):
        self.calls.append(values)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _coordinator(tmp_path: Path, response, *, enabled: bool = True, database=None):
    service, reader, evidence = _service(
        tmp_path, enabled=enabled, database=database
    )
    resolver = Resolver()
    transport = Transport(response)
    coordinator = LiveDeliverySendCoordinator(
        reservation_service=service,
        store=service._store,
        credential_resolver=resolver,
        transport=transport,
        clock=service._clock,
    )
    return coordinator, resolver, transport, evidence, reader


def _admitted_body(tmp_path: Path) -> bytes:
    _, validation = admitted_validation(tmp_path)
    assert validation.agent_result is not None
    return validation.agent_result.model_dump_json().encode()


def _send(coordinator, evidence, *, key="send-once"):
    return coordinator.send_once(
        _create(evidence), authenticated_operator_id=OPERATOR,
        idempotency_key=key, correlation_id="send-transport-1",
    )


def test_valid_injected_https_send_persists_closed_agent_evidence(tmp_path: Path) -> None:
    coordinator, resolver, transport, evidence, _ = _coordinator(
        tmp_path, LiveDeliveryHttpResponse(200, _admitted_body(tmp_path))
    )
    result = _send(coordinator, evidence)
    assert result.disposition == "admitted_evidence_only"
    assert result.receipt and result.receipt.evidence_admitted
    assert result.agent_result and result.acknowledgement
    assert result.audit_evidence.lifecycle == "admitted_evidence_only"
    assert resolver.calls == 1 and len(transport.calls) == 1
    call = transport.calls[0]
    assert call["endpoint"].scheme == "https"
    assert call["endpoint"].path == "/api/v1/internal/installation-intake"
    assert call["connect_timeout_ms"] == 1000
    assert call["response_timeout_ms"] == 5000
    assert call["maximum_response_bytes"] == 32768
    assert call["headers"]["Authorization"] == "Bearer super-secret-token"
    persisted = coordinator._store.get(
        operator_id=OPERATOR, send_attempt_id=result.attempt.send_attempt_id
    )
    assert persisted.agent_result == result.agent_result
    assert persisted.acknowledgement == result.acknowledgement
    assert "super-secret-token" not in str(persisted)


def test_default_disabled_and_stale_evidence_never_resolve_or_send(tmp_path: Path) -> None:
    coordinator, resolver, transport, evidence, reader = _coordinator(
        tmp_path / "disabled", LiveDeliveryHttpResponse(200, b"{}"), enabled=False
    )
    assert _send(coordinator, evidence).error.error_code == "not_current"
    assert not resolver.calls and not transport.calls and not reader.calls
    service, reader, evidence = _service(
        tmp_path / "stale", at="2026-08-27T12:00:42Z"
    )
    resolver, transport = Resolver(), Transport(LiveDeliveryHttpResponse(200, b"{}"))
    coordinator = LiveDeliverySendCoordinator(
        reservation_service=service, store=service._store,
        credential_resolver=resolver, transport=transport, clock=service._clock,
    )
    assert _send(coordinator, evidence).error.error_code == "expired"
    assert not resolver.calls and not transport.calls


def test_timeout_malformed_5xx_and_oversize_are_terminal_ambiguous(tmp_path: Path) -> None:
    cases = (
        LiveDeliveryTransportUncertain("timeout secret"),
        LiveDeliveryHttpResponse(200, b'{"bad":"secret"}'),
        LiveDeliveryHttpResponse(503, b"provider secret"),
        LiveDeliveryHttpResponse(200, b"x" * 32769),
    )
    for index, response in enumerate(cases):
        root = tmp_path / str(index)
        coordinator, resolver, transport, evidence, _ = _coordinator(root, response)
        result = _send(coordinator, evidence)
        assert result.disposition == "ambiguous"
        assert result.error and result.error.error_code == "ambiguous"
        assert result.receipt.lifecycle == "ambiguous"
        assert resolver.calls == 1 and len(transport.calls) == 1
        assert "secret" not in result.model_dump_json()


def test_bad_status_is_rejected_and_exact_retry_performs_zero_io(tmp_path: Path) -> None:
    database = tmp_path / "restart.sqlite3"
    coordinator, resolver, transport, evidence, _ = _coordinator(
        tmp_path, LiveDeliveryHttpResponse(401, b'{"credential":"secret"}'),
        database=database,
    )
    first = _send(coordinator, evidence)
    assert first.disposition == "rejected"
    assert first.error and first.error.error_code == "agent_rejected"
    assert resolver.calls == 1 and len(transport.calls) == 1
    restarted, resolver2, transport2, evidence2, _ = _coordinator(
        tmp_path, LiveDeliveryHttpResponse(200, _admitted_body(tmp_path)),
        database=database,
    )
    replay = _send(restarted, evidence2)
    assert replay.disposition == "exact_replay"
    assert replay.receipt == first.receipt
    assert not resolver2.calls and not transport2.calls


def test_bad_credential_is_redacted_permanently_without_transport(tmp_path: Path) -> None:
    coordinator, resolver, transport, evidence, _ = _coordinator(
        tmp_path, LiveDeliveryHttpResponse(200, _admitted_body(tmp_path))
    )
    resolver.secret = b"secret\nheader"
    first = _send(coordinator, evidence)
    assert first.disposition == "ambiguous"
    assert not transport.calls
    assert "header" not in first.model_dump_json()
    second = _send(coordinator, evidence)
    assert second.disposition == "exact_replay"
    assert resolver.calls == 1 and not transport.calls


def test_transport_module_has_no_runtime_mutation_or_concrete_client_imports() -> None:
    path = Path(__file__).with_name("transport.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports.isdisjoint({
        "aiohttp", "docker", "httpx", "podman", "requests", "socket",
        "subprocess", "urllib",
    })
    source = path.read_text(encoding="utf-8")
    assert all(word not in source for word in (
        "execute_container(", "start_workflow(", "provider_mutation(",
        "repository_mutation(", "guest_mutation(",
    ))
