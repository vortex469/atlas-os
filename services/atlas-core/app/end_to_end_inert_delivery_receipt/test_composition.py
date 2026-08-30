from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.end_to_end_inert_delivery_receipt.composition import (
    EndToEndInertDeliveryComposition,
)
from app.end_to_end_inert_delivery_receipt.store import InertDeliveryReceiptStore
from app.end_to_end_inert_delivery_receipt.test_contract import RECEIPT_ID
from app.end_to_end_inert_delivery_receipt.test_service_store import (
    CORRELATION_ID,
    IDEMPOTENCY_KEY,
    _prior_receipt,
    _setup,
)
from app.live_delivery_send_boundary.test_service import _service as live_service
from app.live_delivery_send_boundary.transport import (
    LiveDeliveryHttpResponse,
    LiveDeliveryTransportUncertain,
    ResolvedBearerCredential,
)
from app.operator_controlled_delivery_enablement.test_contract import OPERATOR


@dataclass
class Resolver:
    secret: bytes = b"transient-test-secret"
    calls: int = 0

    def resolve_once(self, reference):
        self.calls += 1
        assert reference.credential_source == "mode-0400-file"
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


@dataclass
class PriorWriter:
    copy: object
    calls: int = 0
    results: list[object] = field(default_factory=list)

    def record_admitted(
        self,
        *,
        operator_id,
        request,
        agent_result,
        completed_at,
        correlation_id,
    ):
        self.calls += 1
        self.results.append(agent_result)
        assert operator_id == OPERATOR
        assert completed_at < request.expires_at
        assert correlation_id == CORRELATION_ID
        return _prior_receipt(request, self.copy)


def _composition(tmp_path: Path, *, enabled=True, response=None):
    request, copy, *_ = _setup(tmp_path / "fixture")
    send_service, _, _ = live_service(tmp_path / "v31", enabled=enabled)
    resolver = Resolver()
    transport = Transport(
        response
        if response is not None
        else LiveDeliveryHttpResponse(200, copy.result.model_dump_json().encode())
    )
    writer = PriorWriter(copy)
    composition = EndToEndInertDeliveryComposition(
        configuration=send_service.configuration,
        authenticity=copy.authenticity,
        credential_resolver=resolver,
        transport=transport,
        prior_receipt_writer=writer,
        store=InertDeliveryReceiptStore(tmp_path / "v33.sqlite3"),
        clock=lambda: datetime(2026, 8, 27, 12, 0, 16, tzinfo=UTC),
        receipt_id_factory=lambda: RECEIPT_ID,
    )
    return request, composition, resolver, transport, writer


def _compose(composition, request):
    return composition.compose_once(
        request,
        authenticated_operator_id=OPERATOR,
        idempotency_key=IDEMPOTENCY_KEY,
        correlation_id=CORRELATION_ID,
    )


def test_one_shot_composition_uses_exact_injected_https_boundary(tmp_path: Path):
    request, composition, resolver, transport, writer = _composition(tmp_path)

    result = _compose(composition, request)

    assert result.disposition == "verified_inert_receipt"
    assert result.receipt is not None
    assert resolver.calls == writer.calls == 1
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["endpoint"].scheme == "https"
    assert call["endpoint"].path == "/api/v1/internal/installation-intake"
    assert call["connect_timeout_ms"] == 1000
    assert call["response_timeout_ms"] == 5000
    assert call["maximum_response_bytes"] == 32768
    assert call["headers"]["Authorization"] == "Bearer transient-test-secret"
    assert call["headers"]["Idempotency-Key"] == IDEMPOTENCY_KEY
    rendered = result.model_dump_json()
    assert "transient-test-secret" not in rendered
    assert not result.execution_authorized
    assert not result.installation_allowed
    assert not result.worker_allowed
    assert not result.workflow_allowed
    assert not result.mutation_allowed


def test_exact_duplicate_has_zero_credential_network_or_writer_replay(tmp_path: Path):
    request, composition, resolver, transport, writer = _composition(tmp_path)
    first = _compose(composition, request)
    second = _compose(composition, request)

    assert first.receipt == second.receipt
    assert second.disposition == "exact_duplicate"
    assert resolver.calls == writer.calls == len(transport.calls) == 1


def test_default_off_stale_and_owner_checks_precede_credentials(tmp_path: Path):
    request, composition, resolver, transport, writer = _composition(
        tmp_path / "disabled", enabled=False
    )
    disabled = _compose(composition, request)
    assert disabled.error is not None and disabled.error.error_code == "not_current"
    assert not resolver.calls and not transport.calls and not writer.calls

    request, composition, resolver, transport, writer = _composition(
        tmp_path / "owner"
    )
    foreign = composition.compose_once(
        request,
        authenticated_operator_id="operator-b",
        idempotency_key=IDEMPOTENCY_KEY,
        correlation_id=CORRELATION_ID,
    )
    assert foreign.error is not None
    assert foreign.error.error_code == "ownership_mismatch"
    assert not resolver.calls and not transport.calls and not writer.calls


def test_uncertain_or_invalid_post_send_outcome_is_terminal_ambiguous(tmp_path: Path):
    cases = (
        LiveDeliveryTransportUncertain("timeout with secret"),
        LiveDeliveryHttpResponse(503, b"provider secret"),
        LiveDeliveryHttpResponse(200, b'{"bad":"secret"}'),
        LiveDeliveryHttpResponse(200, b"x" * 32769),
    )
    for index, response in enumerate(cases):
        request, composition, resolver, transport, writer = _composition(
            tmp_path / str(index), response=response
        )
        result = _compose(composition, request)
        assert result.disposition == "ambiguous"
        assert result.error is not None and result.error.error_code == "ambiguous"
        assert resolver.calls == 1 and len(transport.calls) == 1
        assert writer.calls == 0
        assert "secret" not in result.model_dump_json()
        replay = _compose(composition, request)
        assert replay.error is not None and replay.error.error_code == "unavailable"
        assert len(transport.calls) == 1


def test_closed_agent_rejection_never_creates_receipt(tmp_path: Path):
    _, copy, *_ = _setup(tmp_path / "rejection-copy")
    rejection = copy.result.model_construct(
        send_attempt_id=copy.result.send_attempt_id,
        intake_request_id=copy.result.intake_request_id,
        outcome="rejected",
        admission=None,
        acknowledgement=None,
        reason_code="unavailable",
    )
    request, composition, resolver, transport, writer = _composition(
        tmp_path / "rejection",
        response=LiveDeliveryHttpResponse(200, rejection.model_dump_json().encode()),
    )
    result = _compose(composition, request)
    assert result.error is not None and result.error.error_code == "agent_rejected"
    assert result.receipt is None
    assert resolver.calls == len(transport.calls) == 1
    assert writer.calls == 0


def test_v033_has_no_core_route_openapi_command_or_effect_consumer():
    core = Path(__file__).parents[1]
    package_root = Path(__file__).parent
    package_name = "end_to_end_inert_delivery_receipt"
    route_sources = [
        path
        for path in (core / "routes").glob("*.py")
        if not path.name.startswith("test_")
    ]
    main_sources = [core / "main.py", core / "config" / "settings.py"]
    for path in [*route_sources, *main_sources]:
        if path.exists():
            text = path.read_text()
            assert package_name not in text
            assert "end-to-end-inert-delivery-receipt" not in text

    for path in core.rglob("*.py"):
        if (
            path.name.startswith("test_")
            or package_root in path.parents
            or "__pycache__" in path.parts
        ):
            continue
        assert package_name not in path.read_text()

    repository = Path(__file__).parents[4]
    mission_control = repository / "services" / "mission-control" / "src"
    if mission_control.exists():
        for path in mission_control.rglob("*"):
            if path.is_file():
                text = path.read_text(errors="ignore")
                assert package_name not in text
                assert "end-to-end-inert-delivery-receipt" not in text

    composition = Path(__file__).with_name("composition.py")
    tree = ast.parse(composition.read_text())
    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imports.intersection(
        {"docker", "subprocess", "provider", "repository", "worker", "workflow"}
    )
    public_methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_methods == {"compose_once", "record_admitted", "resolve"}
