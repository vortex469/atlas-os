"""Collector-local bounded HTTPS transport for image-release acquisition.

v0.14 P1b-collector first slice. This transport is a narrow, collector-owned
copy of the reviewed pinned-transport security behavior (it does not reuse or
refactor ``PinnedGitHubTransport``):

- HTTPS only, TCP port 443 only;
- the target host and request path are supplied per call from a code-owned
  :class:`~app.discovery.image_release_collector.ImageReleaseSourceDescriptor`
  (never from a remote payload and never from a caller-supplied URL string);
- DNS is resolved through an injected resolver and every resolved address is
  validated before any connection is attempted: private, loopback, link-local,
  multicast, reserved, unspecified, and cloud-metadata addresses are rejected,
  and an empty resolution set fails closed;
- TLS uses the platform default context with hostname verification;
- connect and total timeouts are bounded;
- response headers and body are byte-bounded (chunked and close-delimited
  bodies fail closed unless the bound can be proven);
- only ``Accept-Encoding: identity`` is sent and any other response
  ``Content-Encoding`` is rejected;
- redirects are never followed: 3xx statuses are surfaced for the caller to
  refuse deterministically;
- no credentials: no ``Authorization`` header is ever sent, no challenge
  handling exists, and no environment-variable credential reads occur;
- no response-body content is disclosed in any exception message.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import ssl
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

MAX_RESPONSE_BYTES = 64 * 1024
MAX_HEADER_BYTES = 16 * 1024
CONNECT_TIMEOUT_SECONDS = 3.0
TOTAL_TIMEOUT_SECONDS = 10.0

CLOUD_METADATA_NETWORKS = (
    ipaddress.ip_network("169.254.169.254/32"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)


class TransportFailure(Exception):
    """Collector-internal bounded transport failure (no response content)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class BoundedHTTPSResponse(BaseModel):
    """One bounded, untrusted HTTPS response for a descriptor target."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(default="", max_length=128)
    body: bytes = Field(default=b"", max_length=MAX_RESPONSE_BYTES)
    rate_limited: bool = False


Resolver = Callable[[str, int], Awaitable[Sequence[str]]]


def allowed_global_address(value: str) -> bool:
    """Return True only for a globally routable destination address.

    Rejects private, loopback, link-local, multicast, reserved, unspecified,
    and cloud-metadata endpoints. IPv4-mapped IPv6 addresses inherit the
    classification of their mapped address.
    """

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    # An IPv4-mapped IPv6 address must inherit the classification of the
    # IPv4 address it maps to (the stdlib ``is_global`` flag does not do
    # this consistently across CPython versions).
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return (
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not any(address in network for network in CLOUD_METADATA_NETWORKS)
    )


async def _resolve_addresses(host: str, port: int) -> Sequence[str]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(dict.fromkeys(record[4][0] for record in records))


class ImageReleaseSourceTransport(Protocol):
    """Bounded transport boundary the collector dispatches through."""

    async def fetch(self, *, host: str, path: str) -> BoundedHTTPSResponse: ...


class PinnedHTTPS:
    """Bounded HTTPS GET for code-owned host/path acquisition targets.

    ``resolver`` is injectable for tests. Construction performs no I/O.
    """

    def __init__(
        self,
        *,
        resolver: Resolver = _resolve_addresses,
    ) -> None:
        self._resolver = resolver

    async def fetch(self, *, host: str, path: str) -> BoundedHTTPSResponse:
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
                return await self._fetch_bounded(host=host, path=path)
        except TransportFailure:
            raise
        except TimeoutError as exc:
            raise TransportFailure("timeout") from exc
        except ssl.SSLError as exc:
            raise TransportFailure("tls_failed") from exc
        except (OSError, asyncio.IncompleteReadError) as exc:
            raise TransportFailure("connection_failed") from exc

    async def _fetch_bounded(self, *, host: str, path: str) -> BoundedHTTPSResponse:
        try:
            addresses = tuple(await self._resolver(host, 443))
        except (OSError, socket.gaierror) as exc:
            raise TransportFailure("connection_failed") from exc
        if not addresses or any(not allowed_global_address(item) for item in addresses):
            raise TransportFailure("dns_disallowed")

        context = ssl.create_default_context()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=addresses[0],
                    port=443,
                    ssl=context,
                    server_hostname=host,
                    limit=MAX_HEADER_BYTES,
                ),
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise TransportFailure("timeout") from exc
        except ssl.SSLError as exc:
            raise TransportFailure("tls_failed") from exc
        except OSError as exc:
            raise TransportFailure("connection_failed") from exc

        try:
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "Accept: application/json\r\n"
                "User-Agent: atlas-image-release-collector/0.14\r\n"
                "Accept-Encoding: identity\r\n"
                "Connection: close\r\n\r\n"
            )
            writer.write(request.encode("ascii"))
            await writer.drain()
            try:
                # ``readuntil`` raises LimitOverrunError if the header
                # block exceeds the StreamReader limit (``MAX_HEADER_BYTES``)
                # before any data is returned. ``asyncio.LimitOverrunError``
                # is caught explicitly because it is not a ``ValueError``
                # subclass in every CPython release; no explicit length
                # check is needed afterwards.
                header_block = await reader.readuntil(b"\r\n\r\n")
            except (ValueError, asyncio.LimitOverrunError) as exc:
                raise TransportFailure("http_error") from exc
            status, headers = self._parse_headers(header_block)
            body = await self._read_body(reader, headers)
            return BoundedHTTPSResponse(
                status_code=status,
                content_type=headers.get("content-type", ""),
                body=body,
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
            if not 100 <= status <= 599:
                raise ValueError
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if not line:
                    continue
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
            return status, headers
        except (UnicodeDecodeError, ValueError) as exc:
            raise TransportFailure("http_error") from exc

    @staticmethod
    async def _read_body(
        reader: asyncio.StreamReader, headers: dict[str, str]
    ) -> bytes:
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise TransportFailure("invalid_content_type")
        length_text = headers.get("content-length")
        if length_text is not None:
            try:
                length = int(length_text)
            except ValueError as exc:
                raise TransportFailure("http_error") from exc
            if length < 0 or length > MAX_RESPONSE_BYTES:
                raise TransportFailure("response_too_large")
            return await reader.readexactly(length)
        if headers.get("transfer-encoding", "").lower() == "chunked":
            body = bytearray()
            while True:
                line = await reader.readline()
                try:
                    size = int(line.split(b";", 1)[0].strip(), 16)
                except ValueError as exc:
                    raise TransportFailure("http_error") from exc
                if size == 0:
                    await reader.readuntil(b"\r\n")
                    return bytes(body)
                if len(body) + size > MAX_RESPONSE_BYTES:
                    raise TransportFailure("response_too_large")
                body.extend(await reader.readexactly(size))
                if await reader.readexactly(2) != b"\r\n":
                    raise TransportFailure("http_error")
        # A close-delimited response cannot prove the bound without consuming
        # a byte beyond it, so fail closed instead of an unbounded read.
        raise TransportFailure("http_error")


def parse_strict_json_object(
    body: bytes, *, max_bytes: int = MAX_RESPONSE_BYTES
) -> dict[str, object]:
    """Parse one strict, byte-bounded, object-rooted JSON document.

    Rejects duplicate keys, non-object roots, trailing data, and bodies over
    the byte bound. Deterministic and fail-closed: any violation raises
    :class:`TransportFailure` with a stable reason and no payload content.
    """

    if len(body) > max_bytes:
        raise TransportFailure("response_too_large")

    def _reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        decoded = body.decode("utf-8")
        payload = json.loads(decoded, object_pairs_hook=_reject_duplicate)
    except (UnicodeDecodeError, ValueError) as exc:
        raise TransportFailure("malformed_json") from exc
    if not isinstance(payload, dict):
        raise TransportFailure("schema_invalid")
    return payload
