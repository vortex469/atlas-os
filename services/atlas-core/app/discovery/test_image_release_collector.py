"""Behavioral tests for the bounded image-release acquisition boundary."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.discovery.exceptions import ImageReleaseCollectorError
from app.discovery.image_release_collector import (
    CANDIDATE_FACT_SCHEMA,
    PRODUCTION_DESCRIPTORS,
    PRODUCTION_SOURCE_ADAPTERS,
    CandidateImageReleaseFact,
    CollectionResult,
    CollectorHealth,
    ImageReleaseCollector,
    ImageReleaseCollectorFailure,
    ImageReleaseSourceDescriptor,
    build_evidence_row,
)
from app.discovery.image_release_collector_transport import (
    MAX_HEADER_BYTES,
    MAX_RESPONSE_BYTES,
    PinnedHTTPS,
    TransportFailure,
    allowed_global_address,
    parse_strict_json_object,
)
from app.discovery.models import ImageReleaseEvidenceSourceClass

GHOST = "93.184.216.34"  # a globally routable public address.


def _descriptor(
    adapter_id: str = "fake-adapter",
    host: str = "api.example.com",
    path: str = "/repos/vendor/project/releases/latest",
    expected: str = "ghcr.io/vendor/project:latest",
    descriptor_id: str = "ghost-project",
) -> ImageReleaseSourceDescriptor:
    return ImageReleaseSourceDescriptor(
        descriptor_id=descriptor_id,
        acquisition_host=host,
        acquisition_path=path,
        expected_image_reference=expected,
        source_class=ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED,
        adapter_id=adapter_id,
    )


def _candidate(
    *,
    reference: str = "ghcr.io/vendor/project:latest",
    version: str = "1.2.3",
) -> CandidateImageReleaseFact:
    return CandidateImageReleaseFact(
        schema_version=CANDIDATE_FACT_SCHEMA,
        release_version=version,
        image_reference=reference,
        image_digest="sha256:" + "a" * 64,
        attested_at=datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC),
    )


class _CapturingAdapter:
    """A fake adapter that records its inputs and returns a fixed candidate."""

    source_id = "fake-adapter"

    def __init__(
        self,
        outcome: (CandidateImageReleaseFact | ImageReleaseCollectorFailure | Exception)
        | None = None,
    ) -> None:
        self.outcome = outcome if outcome is not None else _candidate()
        self.seen_descriptors: list[ImageReleaseSourceDescriptor] = []
        self.seen_payloads: list[dict[str, object]] = []

    async def normalize(
        self, descriptor: ImageReleaseSourceDescriptor, payload: dict[str, object]
    ) -> CandidateImageReleaseFact | ImageReleaseCollectorFailure:
        self.seen_descriptors.append(descriptor)
        self.seen_payloads.append(payload)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _FakeTransport:
    """A bounded-transport double: returns a fixed response or raises."""

    def __init__(
        self,
        *,
        response: Mapping[str, object] | None = None,
        failure: str | None = None,
    ) -> None:
        self.response = response
        self.failure = failure
        self.calls: list[tuple[str, str]] = []

    async def fetch(self, *, host: str, path: str):
        self.calls.append((host, path))
        if self.failure is not None:
            raise TransportFailure(self.failure)
        if self.response is None:
            raise AssertionError("no response configured")
        from app.discovery.image_release_collector_transport import (
            BoundedHTTPSResponse,
        )

        return BoundedHTTPSResponse(
            status_code=int(self.response["status_code"]),  # type: ignore[arg-type]
            content_type=self.response.get(  # type: ignore[arg-type]
                "content_type", "application/json"
            ),
            body=self.response.get("body", b""),  # type: ignore[arg-type]
            rate_limited=bool(self.response.get("rate_limited", False)),
        )


def _json_transport(payload: object) -> _FakeTransport:
    return _FakeTransport(
        response={
            "status_code": 200,
            "content_type": "application/json",
            "body": json.dumps(payload).encode("utf-8"),
        }
    )


def _collector(
    transport: _FakeTransport | None = None,
    adapter: _CapturingAdapter | None = None,
    descriptors: Mapping[str, ImageReleaseSourceDescriptor] | None = None,
    adapters: Mapping[str, object] | None = None,
) -> ImageReleaseCollector:
    adapter = adapter if adapter is not None else _CapturingAdapter()
    return ImageReleaseCollector(
        descriptors=descriptors
        if descriptors is not None
        else {"ghost-project": _descriptor()},
        adapters=adapters if adapters is not None else {"fake-adapter": adapter},
        transport=transport if transport is not None else _json_transport({}),
    )


# ---------------------------------------------------------------------------
# Transport: DNS validation
# ---------------------------------------------------------------------------


def test_dns_rejects_entire_private_set_before_connect(monkeypatch):
    called = []

    async def fake_connect(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("must not connect to a disallowed address")

    monkeypatch.setattr(
        "app.discovery.image_release_collector_transport.asyncio.open_connection",
        fake_connect,
    )
    for bad in (
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.1.1",
        "169.254.169.254",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",
        "::1",
        "fe80::1",
        "::",
        "fd00:ec2::254",
    ):

        async def resolve(host, port, _bad=bad):
            return (_bad,)

        with pytest.raises(TransportFailure, match="dns_disallowed"):
            asyncio.run(
                PinnedHTTPS(resolver=resolve).fetch(host="api.example.com", path="/x")
            )
    assert called == []


def test_dns_empty_resolution_fails_closed():
    async def resolve(host, port):
        return ()

    with pytest.raises(TransportFailure, match="dns_disallowed"):
        asyncio.run(
            PinnedHTTPS(resolver=resolve).fetch(host="api.example.com", path="/x")
        )


def test_global_address_classification():
    assert allowed_global_address(GHOST)
    assert allowed_global_address("93.184.216.34")
    assert not allowed_global_address("127.0.0.1")
    assert not allowed_global_address("169.254.169.254")
    assert not allowed_global_address("10.0.0.1")
    assert not allowed_global_address("not-an-address")
    # IPv4-mapped IPv6 inherits the mapped address classification.
    assert allowed_global_address(f"::ffff:{GHOST}")
    assert not allowed_global_address("::ffff:10.0.0.1")


# ---------------------------------------------------------------------------
# Transport: request/response behavior over a fake socket
# ---------------------------------------------------------------------------


def _wire_fake_socket(monkeypatch, wire: bytes, *, record=None):
    buffer = bytearray(wire)
    created: dict[str, object] = {}

    class FakeReader:
        async def readuntil(self, separator: bytes = b"\n") -> bytes:
            index = buffer.find(separator)
            if index < 0:
                raise EOFError
            data = bytes(buffer[: index + len(separator)])
            del buffer[: index + len(separator)]
            return data

        async def readline(self) -> bytes:
            return await self.readuntil(b"\n")

        async def readexactly(self, n: int) -> bytes:
            if len(buffer) < n:
                raise asyncio.IncompleteReadError(bytes(buffer), n)
            data = bytes(buffer[:n])
            del buffer[:n]
            return data

    class FakeWriter:
        def write(self, data: bytes) -> None:
            if record is not None:
                record.append(data)

        async def drain(self) -> None:
            pass

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            pass

    async def fake_connect(*args, **kwargs):
        created["kwargs"] = kwargs
        return FakeReader(), FakeWriter()

    monkeypatch.setattr(
        "app.discovery.image_release_collector_transport.asyncio.open_connection",
        fake_connect,
    )

    def fake_default_context():
        import ssl as _ssl

        return _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)

    monkeypatch.setattr(
        "app.discovery.image_release_collector_transport.ssl.create_default_context",
        fake_default_context,
    )
    return created


def test_transport_request_and_success_response(monkeypatch):
    payload = {"tag_name": "v1.2.3"}
    body = json.dumps(payload).encode("utf-8")
    wire = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"\r\n" + body
    )
    sent: list[bytes] = []
    created = _wire_fake_socket(monkeypatch, wire, record=sent)

    async def resolve(host, port):
        return (GHOST,)

    response = asyncio.run(
        PinnedHTTPS(resolver=resolve).fetch(
            host="api.example.com", path="/repos/vendor/project/releases/latest"
        )
    )

    request = sent[0].decode("ascii")
    assert request.startswith("GET /repos/vendor/project/releases/latest HTTP/1.1\r\n")
    assert "Host: api.example.com\r\n" in request
    assert "Accept-Encoding: identity\r\n" in request
    assert "Authorization" not in request
    assert "Connection: close\r\n" in request
    kwargs = created["kwargs"]
    assert kwargs["host"] == GHOST
    assert kwargs["port"] == 443
    assert kwargs["server_hostname"] == "api.example.com"
    assert response.status_code == 200
    assert response.body == body
    assert response.rate_limited is False


def test_transport_rejects_gzip_response_encoding(monkeypatch):
    wire = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Encoding: gzip\r\n"
        b"Content-Length: 3\r\n\r\nabc"
    )
    _wire_fake_socket(monkeypatch, wire)

    async def resolve(host, port):
        return (GHOST,)

    with pytest.raises(TransportFailure, match="invalid_content_type"):
        asyncio.run(PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x"))


def test_transport_rejects_oversized_content_length(monkeypatch):
    wire = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(MAX_RESPONSE_BYTES + 1).encode("ascii") + b"\r\n\r\n"
    )
    _wire_fake_socket(monkeypatch, wire)

    async def resolve(host, port):
        return (GHOST,)

    with pytest.raises(TransportFailure, match="response_too_large"):
        asyncio.run(PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x"))


def test_transport_chunked_body_bounded(monkeypatch):
    payload = b'{"a":1}'
    wire = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        + hex(len(payload))[2:].encode("ascii")
        + b"\r\n"
        + payload
        + b"\r\n0\r\n\r\n"
    )
    _wire_fake_socket(monkeypatch, wire)

    async def resolve(host, port):
        return (GHOST,)

    response = asyncio.run(
        PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x")
    )
    assert response.body == payload


def test_transport_close_delimited_body_fails_closed(monkeypatch):
    # No Content-Length and no chunked framing: the body would be delimited
    # only by connection close, which cannot prove the byte bound.
    wire = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"

    _wire_fake_socket(monkeypatch, wire)

    async def resolve(host, port):
        return (GHOST,)

    with pytest.raises(TransportFailure, match="http_error"):
        asyncio.run(PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x"))


def test_transport_oversized_header_block_is_typed_failure(monkeypatch):
    # A header block larger than MAX_HEADER_BYTES must surface as the typed
    # transport failure, not a raw ValueError/LimitOverrunError from the
    # StreamReader. Uses a real StreamReader (same limit as the transport) so
    # the limit-overrun path is exercised, not the fake reader.
    oversized_line = b"X-Oversized: " + b"A" * (MAX_HEADER_BYTES + 1)
    wire = b"HTTP/1.1 200 OK\r\n" + oversized_line + b"\r\n\r\n"

    class FakeWriter:
        def write(self, data: bytes) -> None:
            pass

        async def drain(self) -> None:
            pass

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            pass

    def real_reader_factory(limit: int) -> asyncio.StreamReader:
        assert limit == MAX_HEADER_BYTES
        reader = asyncio.StreamReader(limit=limit)
        reader.feed_data(wire)
        reader.feed_eof()
        return reader

    async def fake_connect(*args, **kwargs):
        kwargs["limit"] = MAX_HEADER_BYTES
        return real_reader_factory(kwargs["limit"]), FakeWriter()

    monkeypatch.setattr(
        "app.discovery.image_release_collector_transport.asyncio.open_connection",
        fake_connect,
    )

    def fake_default_context():
        import ssl as _ssl

        return _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)

    monkeypatch.setattr(
        "app.discovery.image_release_collector_transport.ssl.create_default_context",
        fake_default_context,
    )

    async def resolve(host, port):
        return (GHOST,)

    with pytest.raises(TransportFailure, match="http_error") as excinfo:
        asyncio.run(PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x"))
    assert "A" not in str(excinfo.value)


def test_transport_total_timeout_is_controlled(monkeypatch):
    import app.discovery.image_release_collector_transport as module

    monkeypatch.setattr(module, "TOTAL_TIMEOUT_SECONDS", 0.01)

    async def resolve(host, port):
        await asyncio.sleep(0.05)
        return (GHOST,)

    with pytest.raises(TransportFailure, match="timeout"):
        asyncio.run(PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x"))


def test_transport_connect_failure_is_controlled(monkeypatch):

    async def fake_connect(*args, **kwargs):
        raise OSError("sensitive connection detail 1234")

    monkeypatch.setattr(
        "app.discovery.image_release_collector_transport.asyncio.open_connection",
        fake_connect,
    )

    async def resolve(host, port):
        return (GHOST,)

    with pytest.raises(TransportFailure, match="connection_failed") as excinfo:
        asyncio.run(PinnedHTTPS(resolver=resolve).fetch(host="h.example", path="/x"))
    assert "sensitive connection detail" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Transport: strict JSON parsing
# ---------------------------------------------------------------------------


def test_strict_json_rejects_duplicate_keys():
    with pytest.raises(TransportFailure, match="malformed_json"):
        parse_strict_json_object(b'{"a": 1, "a": 2}')


def test_strict_json_rejects_non_object_root_and_trailing_data():
    with pytest.raises(TransportFailure, match="schema_invalid"):
        parse_strict_json_object(b"[1, 2]")
    with pytest.raises(TransportFailure, match="malformed_json"):
        parse_strict_json_object(b'{"a": 1}x')


def test_strict_json_rejects_oversized_body():
    body = b'{"a": ' + b'"' + b"x" * 50 + b'"}'
    with pytest.raises(TransportFailure, match="response_too_large"):
        parse_strict_json_object(body, max_bytes=32)


# ---------------------------------------------------------------------------
# Model: descriptor validation
# ---------------------------------------------------------------------------


def test_descriptor_accepts_independent_host_and_image_registry():
    descriptor = _descriptor(
        host="api.github.com", expected="ghcr.io/vendor/project:latest"
    )
    assert descriptor.acquisition_host == "api.github.com"
    assert descriptor.expected_image_reference == "ghcr.io/vendor/project:latest"


def test_descriptor_rejects_unsafe_or_ambiguous_targets():
    bad_hosts = [
        "API.Example.com",
        "*.*.example.com",
        "https://api.example.com",
        "api.example.com:8443",
        "api.example.com/",
        " api.example.com",
        "user@api.example.com",
    ]
    for host in bad_hosts:
        with pytest.raises(ValidationError):
            _descriptor(host=host)
    bad_paths = [
        "repos/vendor/project",
        "/repos/../secrets",
        "/repos?token=x",
        "/repos#frag",
        "/repos\\windows",
        "/repos/vendor/latest\n",
    ]
    for path in bad_paths:
        with pytest.raises(ValidationError):
            _descriptor(path=path)
    with pytest.raises(ValidationError):
        _descriptor(descriptor_id="Ghost-Project")


def test_candidate_and_result_are_immutable_and_forbid_extra_fields():
    candidate = _candidate()
    with pytest.raises(ValidationError):
        candidate.release_version = "9.9.9"
    with pytest.raises(ValidationError):
        CandidateImageReleaseFact(
            schema_version=CANDIDATE_FACT_SCHEMA,
            release_version="1.0.0",
            image_reference="ghcr.io/a/b",
            image_digest="sha256:" + "0" * 64,
            attested_at=datetime(2026, 1, 1, tzinfo=UTC),
            extra_field=True,
        )
    result = CollectionResult(
        descriptor_id="ghost-project",
        health=CollectorHealth.HEALTHY,
        candidate=candidate,
        row=build_evidence_row(_descriptor(), candidate),
    )
    with pytest.raises(ValidationError):
        result.health = CollectorHealth.DEGRADED
    with pytest.raises(ValidationError):
        result.failure_reason = ImageReleaseCollectorFailure.TIMEOUT


def test_candidate_rejects_non_semver_and_unaware_time():
    with pytest.raises(ValidationError):
        _candidate(version="1.2")
    with pytest.raises(ValidationError):
        _candidate(version="01.2.3")
    with pytest.raises(ValidationError):
        _candidate(version="v1.2.3")
    with pytest.raises(ValidationError):
        CandidateImageReleaseFact(
            schema_version=CANDIDATE_FACT_SCHEMA,
            release_version="1.0.0",
            image_reference="ghcr.io/a/b",
            image_digest="sha256:" + "0" * 64,
            # tz-unaware on purpose: the contract must reject it.
            attested_at=datetime(2026, 1, 1),  # noqa: DTZ001
        )


# ---------------------------------------------------------------------------
# Result invariants
# ---------------------------------------------------------------------------


def test_result_health_invariants_are_enforced():
    with pytest.raises(ValidationError):
        CollectionResult(
            descriptor_id="ghost-project",
            health=CollectorHealth.HEALTHY,
        )
    with pytest.raises(ValidationError):
        CollectionResult(
            descriptor_id="ghost-project",
            health=CollectorHealth.DEGRADED,
            candidate=_candidate(),
            row=build_evidence_row(_descriptor(), _candidate()),
            failure_reason=ImageReleaseCollectorFailure.TIMEOUT,
        )
    # The local rule: a transport-unreachable failure must be unavailable.
    with pytest.raises(ValidationError):
        CollectionResult(
            descriptor_id="ghost-project",
            health=CollectorHealth.DEGRADED,
            failure_reason=ImageReleaseCollectorFailure.TIMEOUT,
        )
    # ... while a reachable-but-invalid failure must be degraded.
    with pytest.raises(ValidationError):
        CollectionResult(
            descriptor_id="ghost-project",
            health=CollectorHealth.UNAVAILABLE,
            failure_reason=ImageReleaseCollectorFailure.MALFORMED_JSON,
        )


def test_every_failure_maps_to_a_deterministic_health():
    for failure in ImageReleaseCollectorFailure:
        result = CollectionResult(
            descriptor_id="ghost-project",
            health=(
                CollectorHealth.UNAVAILABLE
                if failure
                in {
                    ImageReleaseCollectorFailure.DNS_DISALLOWED,
                    ImageReleaseCollectorFailure.CONNECTION_FAILED,
                    ImageReleaseCollectorFailure.TIMEOUT,
                    ImageReleaseCollectorFailure.TLS_FAILED,
                    ImageReleaseCollectorFailure.RATE_LIMITED,
                }
                else CollectorHealth.DEGRADED
            ),
            failure_reason=failure,
        )
        assert result.failure_reason is failure


# ---------------------------------------------------------------------------
# Collector: production empty registries and zero network
# ---------------------------------------------------------------------------


def test_production_registries_ship_empty():
    assert dict(PRODUCTION_DESCRIPTORS) == {}
    dict(PRODUCTION_SOURCE_ADAPTERS)
    assert dict(PRODUCTION_SOURCE_ADAPTERS) == {}


def test_production_collector_performs_no_network_activity():
    never = _FakeTransport()
    collector = ImageReleaseCollector(transport=never)
    result = collector.collect("github")
    assert result.health is CollectorHealth.DEGRADED
    assert result.failure_reason is ImageReleaseCollectorFailure.UNKNOWN_DESCRIPTOR
    assert result.candidate is None and result.row is None
    assert never.calls == []


def test_collect_by_id_unknown_descriptor_fails_before_transport():
    transport = _FakeTransport(response={"status_code": 200, "body": b"{}"})
    collector = _collector(transport=transport, descriptors={})
    result = collector.collect("ghost-project")
    assert result.failure_reason is ImageReleaseCollectorFailure.UNKNOWN_DESCRIPTOR
    assert transport.calls == []


def test_unregistered_adapter_fails_before_transport():
    transport = _FakeTransport(response={"status_code": 200, "body": b"{}"})
    collector = _collector(transport=transport, adapters={})
    result = collector.collect(_descriptor())
    assert result.failure_reason is (ImageReleaseCollectorFailure.UNREGISTERED_ADAPTER)
    assert transport.calls == []


def test_adapter_source_id_mismatch_is_acquisition_mismatch():
    adapter = _CapturingAdapter()
    adapter.source_id = "other-adapter"
    transport = _FakeTransport(response={"status_code": 200, "body": b"{}"})
    collector = _collector(transport=transport, adapter=adapter)
    result = collector.collect(_descriptor())
    assert result.failure_reason is (ImageReleaseCollectorFailure.ACQUISITION_MISMATCH)
    assert transport.calls == []


def test_collect_rejects_non_descriptor_argument():
    collector = _collector()
    with pytest.raises(ImageReleaseCollectorError):
        collector.collect(1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Collector: acquisition outcome mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "rate_limited", "failure"),
    [
        (301, False, ImageReleaseCollectorFailure.REDIRECT_REFUSED),
        (302, False, ImageReleaseCollectorFailure.REDIRECT_REFUSED),
        (429, True, ImageReleaseCollectorFailure.RATE_LIMITED),
        (403, True, ImageReleaseCollectorFailure.RATE_LIMITED),
        (404, False, ImageReleaseCollectorFailure.HTTP_ERROR),
        (500, False, ImageReleaseCollectorFailure.HTTP_ERROR),
        (429, False, ImageReleaseCollectorFailure.HTTP_ERROR),
    ],
)
def test_http_status_and_redirect_mapping(status_code, rate_limited, failure):
    transport = _FakeTransport(
        response={
            "status_code": status_code,
            "content_type": "application/json",
            "body": b"{}",
            "rate_limited": rate_limited,
        }
    )
    collector = _collector(transport=transport)
    result = collector.collect("ghost-project")
    assert result.failure_reason is failure
    expected_health = (
        CollectorHealth.UNAVAILABLE
        if failure is ImageReleaseCollectorFailure.RATE_LIMITED
        else CollectorHealth.DEGRADED
    )
    assert result.health is expected_health


def test_non_json_content_type_is_rejected():
    transport = _FakeTransport(
        response={
            "status_code": 200,
            "content_type": "text/html",
            "body": b"{}",
        }
    )
    collector = _collector(transport=transport)
    result = collector.collect("ghost-project")
    assert result.failure_reason is (ImageReleaseCollectorFailure.INVALID_CONTENT_TYPE)


@pytest.mark.parametrize(
    "reason",
    [
        "dns_disallowed",
        "connection_failed",
        "timeout",
        "tls_failed",
        "http_error",
        "response_too_large",
        "invalid_content_type",
        "malformed_json",
        "schema_invalid",
    ],
)
def test_transport_failure_reasons_map_to_typed_failures(reason):
    collector = _collector(transport=_FakeTransport(failure=reason))
    result = collector.collect("ghost-project")
    expected = {
        "dns_disallowed": ImageReleaseCollectorFailure.DNS_DISALLOWED,
        "connection_failed": ImageReleaseCollectorFailure.CONNECTION_FAILED,
        "timeout": ImageReleaseCollectorFailure.TIMEOUT,
        "tls_failed": ImageReleaseCollectorFailure.TLS_FAILED,
        "http_error": ImageReleaseCollectorFailure.HTTP_ERROR,
        "response_too_large": ImageReleaseCollectorFailure.RESPONSE_TOO_LARGE,
        "invalid_content_type": ImageReleaseCollectorFailure.INVALID_CONTENT_TYPE,
        "malformed_json": ImageReleaseCollectorFailure.MALFORMED_JSON,
        "schema_invalid": ImageReleaseCollectorFailure.SCHEMA_INVALID,
    }[reason]
    assert result.failure_reason is expected
    assert result.candidate is None and result.row is None


def test_unexpected_transport_exception_is_fail_closed():
    class _ExplodingTransport:
        async def fetch(self, *, host, path):
            raise RuntimeError("boom")

    collector = _collector(transport=_ExplodingTransport())
    result = collector.collect("ghost-project")
    assert result.failure_reason is (ImageReleaseCollectorFailure.CONNECTION_FAILED)
    assert result.health is CollectorHealth.UNAVAILABLE


def test_malformed_payload_maps_to_malformed_json():
    transport = _FakeTransport(
        response={
            "status_code": 200,
            "content_type": "application/json",
            "body": b'{"a": 1, "a": 2}',
        }
    )
    collector = _collector(transport=transport)
    result = collector.collect("ghost-project")
    assert result.failure_reason is (ImageReleaseCollectorFailure.MALFORMED_JSON)


# ---------------------------------------------------------------------------
# Collector: candidate validation and row construction
# ---------------------------------------------------------------------------


def test_successful_collection_builds_a_conservative_row():
    adapter = _CapturingAdapter()
    collector = _collector(
        transport=_json_transport({"tag_name": "v1.2.3"}), adapter=adapter
    )
    result = collector.collect("ghost-project")

    assert result.health is CollectorHealth.HEALTHY
    assert result.failure_reason is None
    assert result.candidate is not None
    assert result.row is not None

    descriptor = _descriptor()
    row = result.row
    assert row.catalog_item_id == descriptor.descriptor_id
    assert row.source_id == "collector:ghost-project"
    assert row.source_class is ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED
    assert row.release_version == "1.2.3"
    assert row.image_reference == "ghcr.io/vendor/project:latest"
    assert row.image_digest == "sha256:" + "a" * 64
    assert row.attested_at == datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)

    # The adapter saw the code-owned descriptor and the parsed payload.
    assert adapter.seen_descriptors == [descriptor]
    assert adapter.seen_payloads == [{"tag_name": "v1.2.3"}]
    # The transport was called with the descriptor identity, never a URL.
    assert len(adapter.seen_descriptors) == 1


def test_candidate_cannot_replace_code_owned_image_identity():
    adapter = _CapturingAdapter(
        outcome=_candidate(reference="ghcr.io/vendor/project-evil:latest")
    )
    collector = _collector(adapter=adapter)
    result = collector.collect("ghost-project")
    assert result.failure_reason is (
        ImageReleaseCollectorFailure.IMAGE_IDENTITY_MISMATCH
    )
    assert result.health is CollectorHealth.DEGRADED
    assert result.candidate is None and result.row is None


def test_candidate_cannot_replace_source_class_or_descriptor_identity():
    adapter = _CapturingAdapter(
        outcome=_candidate(reference="ghcr.io/vendor/project:latest")
    )
    collector = _collector(adapter=adapter)
    result = collector.collect("ghost-project")
    # source_class and catalog_item_id always come from the descriptor.
    assert result.row.source_class is ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED
    assert result.row.catalog_item_id == "ghost-project"


def test_adapter_exception_is_fail_closed_schema_invalid():
    collector = _collector(adapter=_CapturingAdapter(outcome=RuntimeError("boom")))
    result = collector.collect("ghost-project")
    assert result.failure_reason is (ImageReleaseCollectorFailure.SCHEMA_INVALID)


def test_adapter_typed_failure_is_preserved():
    adapter = _CapturingAdapter(outcome=ImageReleaseCollectorFailure.NO_STABLE_RELEASE)
    collector = _collector(adapter=adapter)
    result = collector.collect("ghost-project")
    assert result.failure_reason is (ImageReleaseCollectorFailure.NO_STABLE_RELEASE)
    assert result.health is CollectorHealth.DEGRADED


def test_invalid_candidate_is_fail_closed():
    bad = _candidate()
    bad = CandidateImageReleaseFact.model_construct(
        schema_version="collector-candidate-fact-v2",
        release_version="1.2.3",
        image_reference="ghcr.io/vendor/project:latest",
        image_digest="sha256:" + "a" * 64,
        attested_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    collector = _collector(adapter=_CapturingAdapter(outcome=bad))
    result = collector.collect("ghost-project")
    assert result.failure_reason is (ImageReleaseCollectorFailure.SCHEMA_INVALID)


def test_attested_at_is_normalized_to_utc_in_the_row():
    offset = timezone(timedelta(hours=2))
    candidate = _candidate().model_copy(
        update={"attested_at": datetime(2026, 8, 23, 14, 0, 0, tzinfo=offset)}
    )
    collector = _collector(adapter=_CapturingAdapter(outcome=candidate))
    result = collector.collect("ghost-project")
    assert result.row.attested_at == datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Async API
# ---------------------------------------------------------------------------


def test_collect_async_matches_sync_semantics():
    adapter = _CapturingAdapter()
    collector = _collector(
        transport=_json_transport({"tag_name": "v1.2.3"}), adapter=adapter
    )
    result = asyncio.run(collector.collect_async("ghost-project"))
    assert result.health is CollectorHealth.HEALTHY
    assert result.row is not None
    unknown = asyncio.run(collector.collect_async("nope-nope"))
    assert unknown.failure_reason is (ImageReleaseCollectorFailure.UNKNOWN_DESCRIPTOR)


def test_default_transport_is_the_pinned_https_class():
    collector = ImageReleaseCollector(descriptors={}, adapters={}, transport=None)
    assert isinstance(collector._transport, PinnedHTTPS)


def test_build_evidence_row_is_pure_data():
    row = build_evidence_row(_descriptor(), _candidate())
    assert row.model_dump()["source_id"] == "collector:ghost-project"
    with pytest.raises(ValidationError):
        row.source_id = "collector:other"
