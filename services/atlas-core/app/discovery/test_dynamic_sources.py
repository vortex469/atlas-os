from __future__ import annotations

import asyncio
import json
import ssl
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.discovery.dynamic_sources import (
    DYNAMIC_RELEASE_FACT_SCHEMA,
    GITHUB_API_HOST,
    GITHUB_API_PATH,
    GITHUB_API_VERSION,
    MAX_RESPONSE_BYTES,
    DynamicReleaseFact,
    DynamicSourceAdapter,
    DynamicSourceFailure,
    DynamicSourceHealth,
    DynamicSourceProvenance,
    DynamicSourceResult,
    FixedHTTPResponse,
    FrigateGitHubLatestReleaseAdapter,
    PinnedGitHubTransport,
    _allowed_global_address,
    _TransportFailure,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


class FakeTransport:
    def __init__(
        self, response: FixedHTTPResponse | None = None, error: Exception | None = None
    ):
        self.response = response
        self.error = error

    async def fetch(self) -> FixedHTTPResponse:
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def response(payload: object, **updates: object) -> FixedHTTPResponse:
    values = {
        "status_code": 200,
        "content_type": "application/json; charset=utf-8",
        "body": json.dumps(payload).encode(),
        "etag": '"bounded"',
    }
    values.update(updates)
    return FixedHTTPResponse(**values)


def adapter(result: FixedHTTPResponse | None = None, error: Exception | None = None):
    return FrigateGitHubLatestReleaseAdapter(
        transport=FakeTransport(result, error), clock=lambda: NOW
    )


def fetch(item: FrigateGitHubLatestReleaseAdapter):
    return asyncio.run(item.fetch())


def valid_payload() -> dict[str, object]:
    return {
        "id": 123456,
        "tag_name": "v0.16.1",
        "published_at": "2026-08-16T14:30:00-04:00",
        "draft": False,
        "prerelease": False,
        "body": "must not survive",
        "assets": [{"browser_download_url": "must not survive"}],
    }


def test_strict_models_are_closed_bounded_and_require_aware_timestamps():
    fact = DynamicReleaseFact(
        schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
        catalog_item_id="frigate",
        fact_kind="latest_stable_release",
        version="0.16.1",
        published_at=NOW,
    )
    assert fact.published_at.tzinfo is UTC
    with pytest.raises(ValidationError):
        fact.model_copy(update={"unknown": True}).model_validate(
            {**fact.model_dump(), "unknown": True}
        )
    for version in (
        "",
        " 0.16.1",
        "0.16.1 ",
        "0.16",
        "0.16.1.2",
        "V0.16.1",
        "vv0.16.1",
        "v0.16.1",
        "1.two.3",
        "1.2.3-beta",
        "1.2.3+build",
        "1.2.3\n",
        "1" * 65,
    ):
        with pytest.raises(ValidationError):
            DynamicReleaseFact(
                schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
                catalog_item_id="frigate",
                fact_kind="latest_stable_release",
                version=version,
                published_at=NOW,
            )
    with pytest.raises(ValidationError):
        DynamicReleaseFact(
            schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
            catalog_item_id="frigate",
            fact_kind="latest_stable_release",
            version="0.16.1",
            published_at=NOW.replace(tzinfo=None),
        )


def test_provenance_is_closed_and_expiry_is_exact():
    values = {
        "source_id": "frigate-github-latest-release-v1",
        "source_type": "github_latest_release",
        "origin_class": "public_https_allowlisted",
        "trust_tier": "supplemental",
        "repository": "blakeblackshear/frigate",
        "upstream_release_id": 42,
        "retrieved_at": NOW,
        "expires_at": NOW + timedelta(hours=24),
        "response_etag": '"etag"',
        "api_version": "2022-11-28",
    }
    DynamicSourceProvenance(**values)
    for update in (
        {"expires_at": NOW},
        {"retrieved_at": NOW.replace(tzinfo=None)},
        {"x": 1},
    ):
        with pytest.raises(ValidationError):
            DynamicSourceProvenance(**(values | update))

    for etag in ("bad\r\ntag", "bad\x00tag", " x ", "x" * 257):
        with pytest.raises(ValidationError):
            DynamicSourceProvenance(**(values | {"response_etag": etag}))


def test_result_model_enforces_failure_health_categories():
    with pytest.raises(ValidationError):
        DynamicSourceResult(
            health=DynamicSourceHealth.DEGRADED,
            failure_reason=DynamicSourceFailure.TIMEOUT,
        )
    with pytest.raises(ValidationError):
        DynamicSourceResult(
            health=DynamicSourceHealth.UNAVAILABLE,
            failure_reason=DynamicSourceFailure.SCHEMA_INVALID,
        )


def test_success_normalizes_only_accepted_fields_and_is_deterministic():
    first = fetch(adapter(response(valid_payload())))
    second = fetch(adapter(response(valid_payload())))
    assert first == second
    assert isinstance(adapter(response(valid_payload())), DynamicSourceAdapter)
    assert first.health is DynamicSourceHealth.HEALTHY
    assert first.fact is not None and first.provenance is not None
    assert first.fact.version == "0.16.1"
    assert first.fact.published_at == datetime(2026, 8, 16, 18, 30, tzinfo=UTC)
    assert first.provenance.expires_at == NOW + timedelta(hours=24)
    serialized = json.dumps(first.model_dump(mode="json"))
    for forbidden in ("must not survive", "assets", "body", "download"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            FixedHTTPResponse(status_code=302, content_type="text/plain", body=b""),
            DynamicSourceFailure.REDIRECT_REFUSED,
        ),
        (
            FixedHTTPResponse(
                status_code=403,
                content_type="application/json",
                body=b"{}",
                rate_limited=True,
            ),
            DynamicSourceFailure.RATE_LIMITED,
        ),
        (
            FixedHTTPResponse(
                status_code=429,
                content_type="application/json",
                body=b"{}",
                rate_limited=True,
            ),
            DynamicSourceFailure.RATE_LIMITED,
        ),
        (
            FixedHTTPResponse(
                status_code=500, content_type="application/json", body=b"{}"
            ),
            DynamicSourceFailure.HTTP_ERROR,
        ),
        (
            FixedHTTPResponse(status_code=200, content_type="text/html", body=b"{}"),
            DynamicSourceFailure.INVALID_CONTENT_TYPE,
        ),
        (
            FixedHTTPResponse(
                status_code=200, content_type="application/json", body=b"{"
            ),
            DynamicSourceFailure.MALFORMED_JSON,
        ),
        (response([]), DynamicSourceFailure.SCHEMA_INVALID),
        (
            response(
                {
                    "id": "bad",
                    "tag_name": "1.2.3",
                    "published_at": "2026-01-01T00:00:00Z",
                }
            ),
            DynamicSourceFailure.SCHEMA_INVALID,
        ),
        (
            response(valid_payload() | {"draft": True}),
            DynamicSourceFailure.NO_STABLE_RELEASE,
        ),
        (
            response(valid_payload() | {"prerelease": True}),
            DynamicSourceFailure.NO_STABLE_RELEASE,
        ),
    ],
)
def test_controlled_response_failures(
    result: FixedHTTPResponse, expected: DynamicSourceFailure
):
    outcome = fetch(adapter(result))
    assert outcome.failure_reason is expected
    assert outcome.fact is None and outcome.provenance is None


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_every_redirect_is_refused_without_location_processing(status: int):
    outcome = fetch(
        adapter(FixedHTTPResponse(status_code=status, content_type="", body=b""))
    )
    assert outcome.failure_reason is DynamicSourceFailure.REDIRECT_REFUSED


@pytest.mark.parametrize(
    "content_type",
    [
        "text/json",
        "text/html",
        "application/problem+json",
        "",
        "application/json; broken",
        "application/json; charset",
        "application/json;charset=latin-1",
        "application/json, text/html",
    ],
)
def test_invalid_or_malformed_content_types_are_rejected(content_type: str):
    outcome = fetch(adapter(response(valid_payload(), content_type=content_type)))
    assert outcome.failure_reason is DynamicSourceFailure.INVALID_CONTENT_TYPE


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        "application/json; charset=utf-8",
        'APPLICATION/JSON; CHARSET="utf-8"',
    ],
)
def test_accepted_json_content_types(content_type: str):
    assert fetch(adapter(response(valid_payload(), content_type=content_type))).fact


@pytest.mark.parametrize(
    "update",
    [
        {"id": 0},
        {"id": True},
        {"draft": None},
        {"prerelease": None},
        {"published_at": "not-a-time"},
        {"tag_name": ""},
    ],
)
def test_required_stable_release_fields_fail_closed(update: dict[str, object]):
    outcome = fetch(adapter(response(valid_payload() | update)))
    assert outcome.failure_reason is DynamicSourceFailure.SCHEMA_INVALID


@pytest.mark.parametrize(
    "reason", list(DynamicSourceFailure)[:4] + [DynamicSourceFailure.RESPONSE_TOO_LARGE]
)
def test_transport_failures_are_bounded(reason: DynamicSourceFailure):
    outcome = fetch(adapter(error=_TransportFailure(reason)))
    assert outcome.failure_reason is reason
    assert "exception" not in outcome.model_dump_json().lower()


@pytest.mark.parametrize(
    "detail",
    [
        "https://example.invalid/private?token=secret",
        "/opt/atlas/private/file",
        "Authorization: Bearer credential",
        '{"raw": "response fragment"}',
    ],
)
def test_unknown_transport_exception_does_not_leak(detail: str):
    outcome = fetch(adapter(error=RuntimeError(detail)))
    assert outcome.failure_reason is DynamicSourceFailure.CONNECTION_FAILED
    assert detail not in outcome.model_dump_json()


@pytest.mark.parametrize("status", [403, 429])
def test_rate_status_without_evidence_is_generic_http_error(status: int):
    outcome = fetch(
        adapter(
            FixedHTTPResponse(
                status_code=status,
                content_type="application/json",
                body=b"{}",
                rate_limited=False,
            )
        )
    )
    assert outcome.failure_reason is DynamicSourceFailure.HTTP_ERROR


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "127.0.0.1",
        "169.254.1.1",
        "192.0.2.1",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "2001:db8::1",
        "ff02::1",
        "::",
        "169.254.169.254",
        "fd00:ec2::254",
    ],
)
def test_non_global_destinations_are_rejected(address: str):
    assert not _allowed_global_address(address)


def test_global_destinations_are_allowed():
    assert _allowed_global_address("8.8.8.8")
    assert _allowed_global_address("2606:4700:4700::1111")


class FakeWriter:
    def __init__(self) -> None:
        self.request = b""

    def write(self, data: bytes) -> None:
        self.request += data

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


class FakeReader:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def readuntil(self, separator: bytes) -> bytes:
        end = self.data.index(separator) + len(separator)
        result, self.data = self.data[:end], self.data[end:]
        return result

    async def readexactly(self, size: int) -> bytes:
        result, self.data = self.data[:size], self.data[size:]
        return result

    async def readline(self) -> bytes:
        return await self.readuntil(b"\n")


def test_response_body_exact_limit_is_accepted_and_limit_plus_one_is_preflighted():
    exact = FakeReader(b"x" * MAX_RESPONSE_BYTES)
    body = asyncio.run(
        PinnedGitHubTransport._read_body(
            exact, {"content-length": str(MAX_RESPONSE_BYTES)}
        )
    )
    assert len(body) == MAX_RESPONSE_BYTES

    oversized = FakeReader(b"must remain unread")
    with pytest.raises(_TransportFailure) as caught:
        asyncio.run(
            PinnedGitHubTransport._read_body(
                oversized, {"content-length": str(MAX_RESPONSE_BYTES + 1)}
            )
        )
    assert caught.value.reason is DynamicSourceFailure.RESPONSE_TOO_LARGE
    assert oversized.data == b"must remain unread"


def test_chunked_limit_plus_one_and_compression_fail_closed():
    chunked = FakeReader(f"{MAX_RESPONSE_BYTES + 1:x}\r\n".encode())
    with pytest.raises(_TransportFailure) as caught:
        asyncio.run(
            PinnedGitHubTransport._read_body(chunked, {"transfer-encoding": "chunked"})
        )
    assert caught.value.reason is DynamicSourceFailure.RESPONSE_TOO_LARGE

    with pytest.raises(_TransportFailure) as caught:
        asyncio.run(
            PinnedGitHubTransport._read_body(
                FakeReader(b""), {"content-encoding": "gzip"}
            )
        )
    assert caught.value.reason is DynamicSourceFailure.INVALID_CONTENT_TYPE


def test_close_delimited_body_fails_closed_without_reading():
    reader = FakeReader(b"must remain unread")
    with pytest.raises(_TransportFailure) as caught:
        asyncio.run(PinnedGitHubTransport._read_body(reader, {}))
    assert caught.value.reason is DynamicSourceFailure.HTTP_ERROR
    assert reader.data == b"must remain unread"


def test_transport_connects_to_prevalidated_address_and_fixed_request(monkeypatch):
    body = json.dumps(valid_payload()).encode()
    reader = FakeReader(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )
    writer = FakeWriter()
    connected: dict[str, object] = {}

    async def open_connection(**kwargs):
        connected.update(kwargs)
        return reader, writer

    async def resolver(host: str, port: int):
        assert (host, port) == (GITHUB_API_HOST, 443)
        return ("8.8.8.8", "2606:4700:4700::1111")

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    result = asyncio.run(PinnedGitHubTransport(resolver=resolver).fetch())
    assert result.status_code == 200
    assert connected["host"] == "8.8.8.8"
    assert connected["server_hostname"] == GITHUB_API_HOST
    request = writer.request.decode("ascii")
    assert request.startswith(f"GET {GITHUB_API_PATH} HTTP/1.1\r\n")
    assert f"Host: {GITHUB_API_HOST}\r\n" in request
    assert f"X-GitHub-Api-Version: {GITHUB_API_VERSION}\r\n" in request
    assert "Accept: application/vnd.github+json\r\n" in request
    assert "Authorization:" not in request


def test_transport_rejects_entire_dns_set_before_connect(monkeypatch):
    called = False

    async def open_connection(**kwargs):
        nonlocal called
        called = True
        raise AssertionError

    async def resolver(host: str, port: int):
        return ("8.8.8.8", "127.0.0.1")

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    with pytest.raises(_TransportFailure) as caught:
        asyncio.run(PinnedGitHubTransport(resolver=resolver).fetch())
    assert caught.value.reason is DynamicSourceFailure.DNS_DISALLOWED
    assert not called


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (TimeoutError("sensitive timeout detail"), DynamicSourceFailure.TIMEOUT),
        (ssl.SSLError("sensitive TLS detail"), DynamicSourceFailure.TLS_FAILED),
    ],
)
def test_connect_timeout_and_tls_failures_are_controlled(monkeypatch, error, reason):
    async def open_connection(**kwargs):
        raise error

    async def resolver(host: str, port: int):
        return ("8.8.8.8",)

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    with pytest.raises(_TransportFailure) as caught:
        asyncio.run(PinnedGitHubTransport(resolver=resolver).fetch())
    assert caught.value.reason is reason
    assert "sensitive" not in caught.value.reason.value


@pytest.mark.parametrize(
    "address",
    ["::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254"],
)
def test_ipv4_mapped_ipv6_non_global_destinations_are_rejected(address: str):
    assert not _allowed_global_address(address)
