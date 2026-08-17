"""Inactive D10 dynamic-source contracts and the first fixed-source adapter."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import ssl
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

DYNAMIC_RELEASE_FACT_SCHEMA = "discovery-dynamic-release-fact-v1"
FRIGATE_ADAPTER_ID = "frigate-github-latest-release-v1"
GITHUB_API_HOST = "api.github.com"
GITHUB_API_PATH = "/repos/blakeblackshear/frigate/releases/latest"
GITHUB_API_VERSION = "2022-11-28"
MAX_RESPONSE_BYTES = 64 * 1024
CONNECT_TIMEOUT_SECONDS = 3.0
TOTAL_TIMEOUT_SECONDS = 10.0
_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_JSON_CONTENT_TYPE_PATTERN = re.compile(
    r'^application/json(?:\s*;\s*charset=(?:utf-8|"utf-8"))?$',
    re.IGNORECASE,
)


class DynamicSourceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class DynamicReleaseFact(DynamicSourceModel):
    schema_version: Literal["discovery-dynamic-release-fact-v1"]
    catalog_item_id: Literal["frigate"]
    fact_kind: Literal["latest_stable_release"]
    version: str = Field(min_length=1, max_length=64, pattern=_VERSION_PATTERN)
    published_at: datetime

    @field_validator("version")
    @classmethod
    def reject_version_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("version must not contain surrounding whitespace")
        return value

    @field_validator("published_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value.astimezone(UTC)


class DynamicSourceProvenance(DynamicSourceModel):
    source_id: Literal["frigate-github-latest-release-v1"]
    source_type: Literal["github_latest_release"]
    origin_class: Literal["public_https_allowlisted"]
    trust_tier: Literal["supplemental"]
    repository: Literal["blakeblackshear/frigate"]
    upstream_release_id: int = Field(ge=1)
    retrieved_at: datetime
    expires_at: datetime
    response_etag: str | None = Field(default=None, min_length=1, max_length=256)
    api_version: Literal["2022-11-28"]

    @field_validator("retrieved_at", "expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provenance timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("response_etag")
    @classmethod
    def validate_etag(cls, value: str | None) -> str | None:
        if value is not None and (value != value.strip() or not value.isprintable()):
            raise ValueError("response_etag must be bounded printable text")
        return value

    @model_validator(mode="after")
    def validate_expiry(self) -> DynamicSourceProvenance:
        if self.expires_at != self.retrieved_at + timedelta(hours=24):
            raise ValueError("expires_at must be exactly 24 hours after retrieved_at")
        return self


class DynamicSourceHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class DynamicSourceFailure(StrEnum):
    DNS_DISALLOWED = "dns_disallowed"
    CONNECTION_FAILED = "connection_failed"
    TIMEOUT = "timeout"
    TLS_FAILED = "tls_failed"
    REDIRECT_REFUSED = "redirect_refused"
    HTTP_ERROR = "http_error"
    RATE_LIMITED = "rate_limited"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_CONTENT_TYPE = "invalid_content_type"
    MALFORMED_JSON = "malformed_json"
    SCHEMA_INVALID = "schema_invalid"
    NO_STABLE_RELEASE = "no_stable_release"


class DynamicSourceResult(DynamicSourceModel):
    health: DynamicSourceHealth
    fact: DynamicReleaseFact | None = None
    provenance: DynamicSourceProvenance | None = None
    failure_reason: DynamicSourceFailure | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> DynamicSourceResult:
        success = self.health is DynamicSourceHealth.HEALTHY
        if success != (self.fact is not None and self.provenance is not None):
            raise ValueError("healthy results require fact and provenance only")
        if success == (self.failure_reason is not None):
            raise ValueError("failed results require exactly one controlled failure")
        unavailable = {
            DynamicSourceFailure.DNS_DISALLOWED,
            DynamicSourceFailure.CONNECTION_FAILED,
            DynamicSourceFailure.TIMEOUT,
            DynamicSourceFailure.TLS_FAILED,
            DynamicSourceFailure.RATE_LIMITED,
        }
        if self.failure_reason is not None:
            expected = (
                DynamicSourceHealth.UNAVAILABLE
                if self.failure_reason in unavailable
                else DynamicSourceHealth.DEGRADED
            )
            if self.health is not expected:
                raise ValueError("health must match the controlled failure category")
        return self


@runtime_checkable
class DynamicSourceAdapter(Protocol):
    """Read-only adapter: the fixed source is selected by its implementation."""

    source_id: str

    async def fetch(self) -> DynamicSourceResult: ...


class _TransportFailure(Exception):
    def __init__(self, reason: DynamicSourceFailure) -> None:
        self.reason = reason
        super().__init__(reason.value)


class FixedHTTPResponse(DynamicSourceModel):
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(max_length=128)
    body: bytes = Field(max_length=MAX_RESPONSE_BYTES)
    etag: str | None = Field(default=None, max_length=256)
    rate_limited: bool = False


class FixedSourceTransport(Protocol):
    async def fetch(self) -> FixedHTTPResponse: ...


Resolver = Callable[[str, int], Awaitable[Sequence[str]]]


def _allowed_global_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    metadata = (
        ipaddress.ip_network("169.254.169.254/32"),
        ipaddress.ip_network("fd00:ec2::254/128"),
    )
    return (
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not any(address in network for network in metadata)
    )


async def _resolve_global_addresses(host: str, port: int) -> Sequence[str]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(dict.fromkeys(record[4][0] for record in records))


class PinnedGitHubTransport:
    """Minimal HTTPS transport that connects only to a prevalidated DNS result."""

    def __init__(self, *, resolver: Resolver = _resolve_global_addresses) -> None:
        self._resolver = resolver

    async def fetch(self) -> FixedHTTPResponse:
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
                return await self._fetch_bounded()
        except _TransportFailure:
            raise
        except TimeoutError as exc:
            raise _TransportFailure(DynamicSourceFailure.TIMEOUT) from exc
        except ssl.SSLError as exc:
            raise _TransportFailure(DynamicSourceFailure.TLS_FAILED) from exc
        except (OSError, asyncio.IncompleteReadError) as exc:
            raise _TransportFailure(DynamicSourceFailure.CONNECTION_FAILED) from exc

    async def _fetch_bounded(self) -> FixedHTTPResponse:
        try:
            addresses = tuple(await self._resolver(GITHUB_API_HOST, 443))
        except (OSError, socket.gaierror) as exc:
            raise _TransportFailure(DynamicSourceFailure.CONNECTION_FAILED) from exc
        if not addresses or any(
            not _allowed_global_address(item) for item in addresses
        ):
            raise _TransportFailure(DynamicSourceFailure.DNS_DISALLOWED)

        context = ssl.create_default_context()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=addresses[0],
                    port=443,
                    ssl=context,
                    server_hostname=GITHUB_API_HOST,
                    limit=16 * 1024,
                ),
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise _TransportFailure(DynamicSourceFailure.TIMEOUT) from exc
        except ssl.SSLError as exc:
            raise _TransportFailure(DynamicSourceFailure.TLS_FAILED) from exc
        except OSError as exc:
            raise _TransportFailure(DynamicSourceFailure.CONNECTION_FAILED) from exc

        try:
            request = (
                f"GET {GITHUB_API_PATH} HTTP/1.1\r\n"
                f"Host: {GITHUB_API_HOST}\r\n"
                "Accept: application/vnd.github+json\r\n"
                f"X-GitHub-Api-Version: {GITHUB_API_VERSION}\r\n"
                "User-Agent: atlas-dynamic-discovery/0.12\r\n"
                "Accept-Encoding: identity\r\n"
                "Connection: close\r\n\r\n"
            )
            writer.write(request.encode("ascii"))
            await writer.drain()
            header_block = await reader.readuntil(b"\r\n\r\n")
            if len(header_block) > 16 * 1024:
                raise _TransportFailure(DynamicSourceFailure.HTTP_ERROR)
            status, headers = self._parse_headers(header_block)
            body = await self._read_body(reader, headers)
            return FixedHTTPResponse(
                status_code=status,
                content_type=headers.get("content-type", ""),
                body=body,
                etag=headers.get("etag"),
                rate_limited=(
                    "retry-after" in headers
                    or headers.get("x-ratelimit-remaining") == "0"
                ),
            )
        finally:
            writer.close()
            await writer.wait_closed()

    @staticmethod
    def _parse_headers(block: bytes) -> tuple[int, dict[str, str]]:
        try:
            lines = block.decode("iso-8859-1").split("\r\n")
            protocol, status_text, _ = lines[0].split(" ", 2)
            if protocol not in {"HTTP/1.0", "HTTP/1.1"}:
                raise ValueError
            status = int(status_text)
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if not line:
                    continue
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
            return status, headers
        except (UnicodeDecodeError, ValueError) as exc:
            raise _TransportFailure(DynamicSourceFailure.HTTP_ERROR) from exc

    @staticmethod
    async def _read_body(
        reader: asyncio.StreamReader, headers: dict[str, str]
    ) -> bytes:
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise _TransportFailure(DynamicSourceFailure.INVALID_CONTENT_TYPE)
        length_text = headers.get("content-length")
        if length_text is not None:
            try:
                length = int(length_text)
            except ValueError as exc:
                raise _TransportFailure(DynamicSourceFailure.HTTP_ERROR) from exc
            if length < 0 or length > MAX_RESPONSE_BYTES:
                raise _TransportFailure(DynamicSourceFailure.RESPONSE_TOO_LARGE)
            return await reader.readexactly(length)
        if headers.get("transfer-encoding", "").lower() == "chunked":
            body = bytearray()
            while True:
                line = await reader.readline()
                try:
                    size = int(line.split(b";", 1)[0].strip(), 16)
                except ValueError as exc:
                    raise _TransportFailure(DynamicSourceFailure.HTTP_ERROR) from exc
                if size == 0:
                    await reader.readuntil(b"\r\n")
                    return bytes(body)
                if len(body) + size > MAX_RESPONSE_BYTES:
                    raise _TransportFailure(DynamicSourceFailure.RESPONSE_TOO_LARGE)
                body.extend(await reader.readexactly(size))
                if await reader.readexactly(2) != b"\r\n":
                    raise _TransportFailure(DynamicSourceFailure.HTTP_ERROR)
        # A close-delimited response cannot prove the bound without consuming a
        # byte beyond it, so fail closed instead of performing an unbounded read.
        raise _TransportFailure(DynamicSourceFailure.HTTP_ERROR)


Clock = Callable[[], datetime]


class FrigateGitHubLatestReleaseAdapter:
    source_id = FRIGATE_ADAPTER_ID

    def __init__(
        self,
        *,
        transport: FixedSourceTransport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._transport = transport or PinnedGitHubTransport()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def fetch(self) -> DynamicSourceResult:
        try:
            response = await self._transport.fetch()
        except _TransportFailure as exc:
            return self._failure(exc.reason)
        except Exception:  # noqa: BLE001 - third-party transports are a trust boundary
            return self._failure(DynamicSourceFailure.CONNECTION_FAILED)

        if 300 <= response.status_code < 400:
            return self._failure(DynamicSourceFailure.REDIRECT_REFUSED)
        if response.status_code in {403, 429} and response.rate_limited:
            return self._failure(DynamicSourceFailure.RATE_LIMITED)
        if not 200 <= response.status_code < 300:
            return self._failure(DynamicSourceFailure.HTTP_ERROR)
        if _JSON_CONTENT_TYPE_PATTERN.fullmatch(response.content_type) is None:
            return self._failure(DynamicSourceFailure.INVALID_CONTENT_TYPE)
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._failure(DynamicSourceFailure.MALFORMED_JSON)
        if not isinstance(payload, dict):
            return self._failure(DynamicSourceFailure.SCHEMA_INVALID)
        if payload.get("draft") is True or payload.get("prerelease") is True:
            return self._failure(DynamicSourceFailure.NO_STABLE_RELEASE)
        if payload.get("draft") is not False or payload.get("prerelease") is not False:
            return self._failure(DynamicSourceFailure.SCHEMA_INVALID)

        try:
            release_id = payload["id"]
            tag = payload["tag_name"]
            published_text = payload["published_at"]
            if type(release_id) is not int or release_id < 1:
                raise ValueError
            if not isinstance(tag, str) or not isinstance(published_text, str):
                raise TypeError
            version = tag.removeprefix("v")
            if tag != tag.strip() or len(tag) > 65:
                raise ValueError
            published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
            retrieved_at = self._clock()
            fact = DynamicReleaseFact(
                schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
                catalog_item_id="frigate",
                fact_kind="latest_stable_release",
                version=version,
                published_at=published_at,
            )
            provenance = DynamicSourceProvenance(
                source_id=FRIGATE_ADAPTER_ID,
                source_type="github_latest_release",
                origin_class="public_https_allowlisted",
                trust_tier="supplemental",
                repository="blakeblackshear/frigate",
                upstream_release_id=release_id,
                retrieved_at=retrieved_at,
                expires_at=retrieved_at + timedelta(hours=24),
                response_etag=response.etag,
                api_version=GITHUB_API_VERSION,
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            return self._failure(DynamicSourceFailure.SCHEMA_INVALID)
        return DynamicSourceResult(
            health=DynamicSourceHealth.HEALTHY,
            fact=fact,
            provenance=provenance,
        )

    @staticmethod
    def _failure(reason: DynamicSourceFailure) -> DynamicSourceResult:
        unavailable = {
            DynamicSourceFailure.DNS_DISALLOWED,
            DynamicSourceFailure.CONNECTION_FAILED,
            DynamicSourceFailure.TIMEOUT,
            DynamicSourceFailure.TLS_FAILED,
            DynamicSourceFailure.RATE_LIMITED,
        }
        return DynamicSourceResult(
            health=(
                DynamicSourceHealth.UNAVAILABLE
                if reason in unavailable
                else DynamicSourceHealth.DEGRADED
            ),
            failure_reason=reason,
        )
