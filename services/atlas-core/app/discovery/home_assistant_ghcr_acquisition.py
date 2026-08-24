"""Bounded acquisition of the Home Assistant 2026.8.3 GHCR attestation.

This private proof boundary acquires bytes only.  It deliberately performs no
Sigstore verification, trust classification, evidence construction, or
collector registration.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import ssl
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

_REGISTRY_HOST = "ghcr.io"
_TOKEN_HOST = "ghcr.io"
_REPOSITORY = "home-assistant/home-assistant"
_RELEASE = "2026.8.3"
_IMAGE_REFERENCE = "ghcr.io/home-assistant/home-assistant"
_EXPECTED_DIGEST = (
    "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"
)
_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
_ARTIFACT_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
_MANIFEST_PATH = f"/v2/{_REPOSITORY}/manifests/{_RELEASE}"
_REFERRERS_PATH = f"/v2/{_REPOSITORY}/referrers/{_EXPECTED_DIGEST}"
_TOKEN_PATH = (
    "/token?service=ghcr.io&scope=repository%3Ahome-assistant%2Fhome-assistant%3Apull"
)
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_HEADER_BYTES = 16 * 1024
_MAX_INDEX_BYTES = 2 * 1024 * 1024
_MAX_OBJECT_BYTES = 4 * 1024 * 1024
_MAX_TOTAL_BYTES = 12 * 1024 * 1024
_MAX_DESCRIPTORS = 16
_MAX_TOKEN_BYTES = 4096
_MAX_BUNDLE_STRING_BYTES = 4 * 1024 * 1024
_MAX_BUNDLE_ENTRIES = 16
_MAX_TLOG_HASHES = 64
_EXPECTED_PAYLOAD_TYPE = "application/vnd.in-toto+json"
_CONNECT_TIMEOUT = 3.0
_TOTAL_TIMEOUT = 15.0
_HTTP_TOKEN_RE = re.compile(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+\Z")


class _FailureReason(StrEnum):
    CHALLENGE_INVALID = "challenge_invalid"
    TOKEN_RESPONSE_INVALID = "token_response_invalid"
    AUTHENTICATION_FAILED = "authentication_failed"
    INDEX_REQUIRED = "index_required"
    DIGEST_MISMATCH = "digest_mismatch"
    REFERRERS_INVALID = "referrers_invalid"
    SIGNATURE_MATERIAL_MISSING = "signature_material_missing"
    DESCRIPTOR_INVALID = "descriptor_invalid"
    RESPONSE_TOO_LARGE = "response_too_large"
    TAG_MUTATED = "tag_mutated"
    REDIRECT_REFUSED = "redirect_refused"
    DNS_DISALLOWED = "dns_disallowed"
    UNSUPPORTED_ENCODING = "unsupported_encoding"
    TIMEOUT = "timeout"
    HTTP_INVALID = "http_invalid"
    CONNECTION_FAILED = "connection_failed"


class _HomeAssistantGHCRAcquisitionError(Exception):
    """Typed local failure which never includes remote content or credentials."""

    def __init__(self, reason: _FailureReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


class _Transport(Protocol):
    async def get(
        self,
        *,
        host: str,
        path: str,
        accept: str,
        authorization: str | None = None,
        max_body_bytes: int,
        timeout: float = _TOTAL_TIMEOUT,
    ) -> _Response: ...


@dataclass(frozen=True, slots=True)
class _HomeAssistantGHCRAcquisition:
    release_version: str
    image_reference: str
    index_digest: str
    index_media_type: str
    index_bytes: bytes
    sigstore_bundles: tuple[bytes, ...]


@dataclass(slots=True)
class _AcquisitionBudget:
    deadline: float
    received: int = 0


Resolver = Callable[[str, int], Awaitable[Sequence[str]]]


async def _resolve(host: str, port: int) -> Sequence[str]:
    records = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )
    return tuple(dict.fromkeys(record[4][0] for record in records))


def _global_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    address = getattr(address, "ipv4_mapped", None) or address
    metadata = (
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("fd00:ec2::254"),
    )
    return (
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and address not in metadata
    )


class _PinnedGHCRTransport:
    """HTTPS-only fixed-target transport; construction performs no I/O."""

    def __init__(self, *, resolver: Resolver = _resolve) -> None:
        self._resolver = resolver

    async def get(
        self,
        *,
        host: str,
        path: str,
        accept: str,
        authorization: str | None = None,
        max_body_bytes: int,
        timeout: float = _TOTAL_TIMEOUT,
    ) -> _Response:
        if host != _REGISTRY_HOST or not path.startswith("/"):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.HTTP_INVALID)
        if authorization is not None and host != _REGISTRY_HOST:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.HTTP_INVALID)
        try:
            async with asyncio.timeout(timeout):
                return await self._get(
                    host, path, accept, authorization, max_body_bytes, timeout
                )
        except _HomeAssistantGHCRAcquisitionError:
            raise
        except TimeoutError:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.TIMEOUT) from None
        except (OSError, ssl.SSLError, asyncio.IncompleteReadError):
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.CONNECTION_FAILED
            ) from None

    async def _get(
        self,
        host: str,
        path: str,
        accept: str,
        authorization: str | None,
        max_body_bytes: int,
        timeout: float,
    ) -> _Response:
        addresses = tuple(await self._resolver(host, 443))
        if not addresses or any(not _global_address(item) for item in addresses):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DNS_DISALLOWED)
        context = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host=addresses[0],
                port=443,
                ssl=context,
                server_hostname=host,
                limit=_MAX_HEADER_BYTES,
            ),
            timeout=min(_CONNECT_TIMEOUT, timeout),
        )
        try:
            fields = [
                f"GET {path} HTTP/1.1",
                f"Host: {host}",
                f"Accept: {accept}",
                "User-Agent: atlas-ha-ghcr-acquisition/0.14",
                "Accept-Encoding: identity",
                "Connection: close",
            ]
            if authorization is not None:
                fields.append(f"Authorization: {authorization}")
            writer.write(("\r\n".join(fields) + "\r\n\r\n").encode("ascii"))
            await writer.drain()
            try:
                block = await reader.readuntil(b"\r\n\r\n")
            except (ValueError, asyncio.LimitOverrunError):
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.HTTP_INVALID
                ) from None
            if len(block) > _MAX_HEADER_BYTES:
                raise _HomeAssistantGHCRAcquisitionError(_FailureReason.HTTP_INVALID)
            status, headers = _parse_http_headers(block)
            if 300 <= status < 400:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.REDIRECT_REFUSED
                )
            body = await _read_body(reader, headers, max_body_bytes)
            return _Response(status=status, headers=headers, body=body)
        finally:
            writer.close()
            await writer.wait_closed()


def _parse_http_headers(block: bytes) -> tuple[int, dict[str, str]]:
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
            raw_name, value = line.encode("iso-8859-1").split(b":", 1)
            if _HTTP_TOKEN_RE.fullmatch(raw_name) is None:
                raise ValueError
            key = raw_name.decode("ascii").lower()
            if key in headers:
                raise ValueError
            if value.startswith(b" "):
                value = value[1:]
            headers[key] = value.decode("iso-8859-1")
        return status, headers
    except (UnicodeDecodeError, ValueError):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.HTTP_INVALID) from None


async def _read_body(
    reader: asyncio.StreamReader, headers: Mapping[str, str], limit: int
) -> bytes:
    if headers.get("content-encoding", "identity").lower() != "identity":
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.UNSUPPORTED_ENCODING)
    length = headers.get("content-length")
    if length is None or "transfer-encoding" in headers:
        # Fixed GHCR material must have an unambiguous, pre-bounded length.
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.HTTP_INVALID)
    if not length or not length.isascii() or not length.isdecimal():
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.HTTP_INVALID)
    size = int(length)
    if size > limit:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.RESPONSE_TOO_LARGE)
    return await reader.readexactly(size)


def _strict_object(body: bytes, reason: _FailureReason) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise _HomeAssistantGHCRAcquisitionError(reason) from None
    if not isinstance(value, dict):
        raise _HomeAssistantGHCRAcquisitionError(reason)
    return value


def _media_type(headers: Mapping[str, str]) -> str:
    raw = headers.get("content-type", "")
    parts = [part.strip() for part in raw.split(";")]
    if not parts or any(not part for part in parts):
        return ""
    # Parameters are harmless only when syntactically name=value.
    if any("=" not in parameter for parameter in parts[1:]):
        return ""
    return parts[0].lower()


def _challenge(value: str) -> None:
    if not value.startswith("Bearer "):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)
    rest = value[7:]
    position = 0
    parameters: dict[str, str] = {}
    while position < len(rest):
        match = re.match(r"[a-z]+", rest[position:])
        if match is None:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)
        name = match.group(0)
        position += len(name)
        if name in parameters or rest[position : position + 2] != '="':
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)
        position += 2
        end = rest.find('"', position)
        if end < 0 or "\\" in rest[position:end]:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)
        parameters[name] = rest[position:end]
        position = end + 1
        if position == len(rest):
            break
        if rest[position] != ",":
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)
        position += 1
        while position < len(rest) and rest[position] in " \t":
            position += 1
        if position == len(rest):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)
    if parameters != {
        "realm": "https://ghcr.io/token",
        "service": "ghcr.io",
        "scope": f"repository:{_REPOSITORY}:pull",
    }:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.CHALLENGE_INVALID)


def _descriptor(value: object) -> tuple[str, int, str, str | None]:
    if not isinstance(value, dict) or not set(value) <= {
        "mediaType",
        "digest",
        "size",
        "artifactType",
        "annotations",
    }:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    media = value.get("mediaType")
    digest = value.get("digest")
    size = value.get("size")
    artifact = value.get("artifactType")
    if (
        not isinstance(media, str)
        or not isinstance(digest, str)
        or _DIGEST_RE.fullmatch(digest) is None
        or not isinstance(size, int)
        or isinstance(size, bool)
        or not 0 <= size <= _MAX_OBJECT_BYTES
        or (artifact is not None and not isinstance(artifact, str))
    ):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    return digest, size, media, artifact


def _check_bytes(body: bytes, digest: str, size: int) -> None:
    if len(body) != size or f"sha256:{hashlib.sha256(body).hexdigest()}" != digest:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DIGEST_MISMATCH)


def _bundle_shape(body: bytes) -> None:
    value = _strict_object(body, _FailureReason.DESCRIPTOR_INVALID)
    if (
        set(value) != {"mediaType", "dsseEnvelope", "verificationMaterial"}
        or value.get("mediaType") != _BUNDLE_MEDIA_TYPE
    ):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    dsse = value.get("dsseEnvelope")
    verification = value.get("verificationMaterial")
    if not isinstance(dsse, dict) or set(dsse) != {
        "payload",
        "payloadType",
        "signatures",
    }:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    payload = dsse["payload"]
    signatures = dsse["signatures"]
    if (
        not isinstance(payload, str)
        or not payload
        or len(payload) > _MAX_BUNDLE_STRING_BYTES
        or dsse["payloadType"] != _EXPECTED_PAYLOAD_TYPE
        or not isinstance(signatures, list)
        or not 1 <= len(signatures) <= _MAX_BUNDLE_ENTRIES
    ):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    for signature in signatures:
        if (
            not isinstance(signature, dict)
            or set(signature) != {"sig"}
            or not isinstance(signature["sig"], str)
            or not signature["sig"]
            or len(signature["sig"]) > _MAX_BUNDLE_STRING_BYTES
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    if not isinstance(verification, dict) or set(verification) != {
        "certificate",
        "tlogEntries",
        "timestampVerificationData",
    }:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    certificate = verification.get("certificate")
    if (
        not isinstance(certificate, dict)
        or set(certificate) != {"rawBytes"}
        or not isinstance(certificate["rawBytes"], str)
        or not certificate["rawBytes"]
        or len(certificate["rawBytes"]) > _MAX_BUNDLE_STRING_BYTES
    ):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    entries = verification.get("tlogEntries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= _MAX_BUNDLE_ENTRIES:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "logIndex",
            "logId",
            "kindVersion",
            "integratedTime",
            "inclusionPromise",
            "inclusionProof",
            "canonicalizedBody",
        }:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
        log_id = entry.get("logId")
        kind = entry.get("kindVersion")
        if (
            not isinstance(entry["logIndex"], str)
            or not entry["logIndex"].isascii()
            or not entry["logIndex"].isdecimal()
            or len(entry["logIndex"]) > 20
            or not isinstance(entry["integratedTime"], str)
            or not entry["integratedTime"].isascii()
            or not entry["integratedTime"].isdecimal()
            or len(entry["integratedTime"]) > 20
            or not isinstance(log_id, dict)
            or set(log_id) != {"keyId"}
            or not isinstance(log_id.get("keyId"), str)
            or not log_id["keyId"]
            or len(log_id["keyId"]) > _MAX_BUNDLE_STRING_BYTES
            or not isinstance(kind, dict)
            or set(kind) != {"kind", "version"}
            or not all(
                isinstance(kind.get(key), str)
                and kind[key]
                and len(kind[key]) <= _MAX_BUNDLE_STRING_BYTES
                for key in ("kind", "version")
            )
            or not isinstance(entry["canonicalizedBody"], str)
            or not entry["canonicalizedBody"]
            or len(entry["canonicalizedBody"]) > _MAX_BUNDLE_STRING_BYTES
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)

        promise = entry["inclusionPromise"]
        if (
            not isinstance(promise, dict)
            or set(promise) != {"signedEntryTimestamp"}
            or not isinstance(promise["signedEntryTimestamp"], str)
            or not promise["signedEntryTimestamp"]
            or len(promise["signedEntryTimestamp"]) > _MAX_BUNDLE_STRING_BYTES
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)

        proof = entry["inclusionProof"]
        if (
            not isinstance(proof, dict)
            or set(proof)
            != {"logIndex", "treeSize", "rootHash", "hashes", "checkpoint"}
            or any(
                not isinstance(proof[key], str)
                or not proof[key].isascii()
                or not proof[key].isdecimal()
                or len(proof[key]) > 20
                for key in ("logIndex", "treeSize")
            )
            or not isinstance(proof["rootHash"], str)
            or not proof["rootHash"]
            or len(proof["rootHash"]) > _MAX_BUNDLE_STRING_BYTES
            or not isinstance(proof["hashes"], list)
            or len(proof["hashes"]) > _MAX_TLOG_HASHES
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
        for item in proof["hashes"]:
            if (
                not isinstance(item, str)
                or not item
                or len(item) > _MAX_BUNDLE_STRING_BYTES
            ):
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
        checkpoint = proof["checkpoint"]
        if (
            not isinstance(checkpoint, dict)
            or set(checkpoint) != {"envelope"}
            or not isinstance(checkpoint["envelope"], str)
            or not checkpoint["envelope"]
            or len(checkpoint["envelope"]) > _MAX_BUNDLE_STRING_BYTES
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)

    timestamps = verification["timestampVerificationData"]
    if not isinstance(timestamps, dict) or set(timestamps) != {"rfc3161Timestamps"}:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    timestamp_values = timestamps["rfc3161Timestamps"]
    if (
        not isinstance(timestamp_values, list)
        or len(timestamp_values) > _MAX_BUNDLE_ENTRIES
    ):
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)
    for item in timestamp_values:
        if (
            not isinstance(item, dict)
            or set(item) != {"signedTimestamp"}
            or not isinstance(item["signedTimestamp"], str)
            or not item["signedTimestamp"]
            or len(item["signedTimestamp"]) > _MAX_BUNDLE_STRING_BYTES
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DESCRIPTOR_INVALID)


class _HomeAssistantGHCRAcquirer:
    """Explicit, single-release acquisition API. Construction is inert."""

    def __init__(self, *, transport: _Transport | None = None) -> None:
        self._transport = transport or _PinnedGHCRTransport()

    async def acquire(self) -> _HomeAssistantGHCRAcquisition:
        loop = asyncio.get_running_loop()
        budget = _AcquisitionBudget(loop.time() + _TOTAL_TIMEOUT)
        try:
            async with asyncio.timeout_at(budget.deadline):
                return await self._acquire(budget)
        except _HomeAssistantGHCRAcquisitionError:
            raise
        except TimeoutError:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.TIMEOUT) from None

    async def _acquire(
        self, budget: _AcquisitionBudget
    ) -> _HomeAssistantGHCRAcquisition:
        initial = await self._request_index(budget, None)
        _check_object_bound(initial.body, _MAX_INDEX_BYTES)
        if initial.status != 401:
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.AUTHENTICATION_FAILED
            )
        _challenge(initial.headers.get("www-authenticate", ""))
        token_response = await self._request(
            budget,
            host=_TOKEN_HOST,
            path=_TOKEN_PATH,
            accept="application/json",
            object_limit=16 * 1024,
        )
        _check_object_bound(token_response.body, 16 * 1024)
        if 300 <= token_response.status < 400:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.REDIRECT_REFUSED)
        if (
            token_response.status != 200
            or _media_type(token_response.headers) != "application/json"
        ):
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.TOKEN_RESPONSE_INVALID
            )
        token_json = _strict_object(
            token_response.body, _FailureReason.TOKEN_RESPONSE_INVALID
        )
        fields = [
            (key, token_json.get(key))
            for key in ("token", "access_token")
            if key in token_json
        ]
        if len(fields) != 1 or not isinstance(fields[0][1], str):
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.TOKEN_RESPONSE_INVALID
            )
        token = fields[0][1]
        if (
            not token
            or len(token) > _MAX_TOKEN_BYTES
            or re.fullmatch(r"[A-Za-z0-9._~+/=-]+", token) is None
        ):
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.TOKEN_RESPONSE_INVALID
            )
        authorization = f"Bearer {token}"
        index = await self._request_index(budget, authorization)
        _check_object_bound(index.body, _MAX_INDEX_BYTES)
        index_media = self._validate_index(index)
        referrers = await self._request(
            budget,
            host=_REGISTRY_HOST,
            path=_REFERRERS_PATH,
            accept=_INDEX_MEDIA_TYPE,
            authorization=authorization,
            object_limit=_MAX_INDEX_BYTES,
        )
        _check_object_bound(referrers.body, _MAX_INDEX_BYTES)
        if (
            referrers.status != 200
            or _media_type(referrers.headers) != _INDEX_MEDIA_TYPE
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.REFERRERS_INVALID)
        refs = _strict_object(referrers.body, _FailureReason.REFERRERS_INVALID)
        if refs.get("schemaVersion") != 2 or not isinstance(
            refs.get("manifests"), list
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.REFERRERS_INVALID)
        manifests = refs["manifests"]
        if len(manifests) > _MAX_DESCRIPTORS:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.RESPONSE_TOO_LARGE)
        selected: dict[str, tuple[int, str]] = {}
        for item in manifests:
            digest, size, media, artifact = _descriptor(item)
            if artifact != _BUNDLE_MEDIA_TYPE:
                continue
            current = (size, media)
            if digest in selected:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            selected[digest] = current
        if not selected:
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.SIGNATURE_MATERIAL_MISSING
            )
        bundles: list[tuple[str, bytes]] = []
        for manifest_digest in sorted(selected):
            size, media = selected[manifest_digest]
            if media != _ARTIFACT_MEDIA_TYPE:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            manifest = await self._request(
                budget,
                host=_REGISTRY_HOST,
                path=f"/v2/{_REPOSITORY}/manifests/{manifest_digest}",
                accept=_ARTIFACT_MEDIA_TYPE,
                authorization=authorization,
                object_limit=_MAX_OBJECT_BYTES,
            )
            _check_object_bound(manifest.body, _MAX_OBJECT_BYTES)
            if manifest.status != 200 or _media_type(manifest.headers) != media:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            _check_bytes(manifest.body, manifest_digest, size)
            document = _strict_object(manifest.body, _FailureReason.DESCRIPTOR_INVALID)
            if (
                document.get("schemaVersion") != 2
                or document.get("mediaType") != _ARTIFACT_MEDIA_TYPE
                or set(document)
                - {
                    "schemaVersion",
                    "mediaType",
                    "artifactType",
                    "config",
                    "subject",
                    "layers",
                    "annotations",
                }
            ):
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            subject = document.get("subject")
            subject_digest, subject_size, subject_media, _ = _descriptor(subject)
            if subject_digest != _EXPECTED_DIGEST or subject_media != _INDEX_MEDIA_TYPE:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.REFERRERS_INVALID
                )
            if subject_size != len(index.body):
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            if document.get("artifactType") != _BUNDLE_MEDIA_TYPE:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            config = document.get("config")
            if config is not None:
                _descriptor(config)
            layers = document.get("layers")
            if not isinstance(layers, list) or len(layers) != 1:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            blob_digest, blob_size, blob_media, _ = _descriptor(layers[0])
            if blob_media != _BUNDLE_MEDIA_TYPE:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            blob = await self._request(
                budget,
                host=_REGISTRY_HOST,
                path=f"/v2/{_REPOSITORY}/blobs/{blob_digest}",
                accept=_BUNDLE_MEDIA_TYPE,
                authorization=authorization,
                object_limit=_MAX_OBJECT_BYTES,
            )
            _check_object_bound(blob.body, _MAX_OBJECT_BYTES)
            if blob.status != 200 or _media_type(blob.headers) != _BUNDLE_MEDIA_TYPE:
                raise _HomeAssistantGHCRAcquisitionError(
                    _FailureReason.DESCRIPTOR_INVALID
                )
            _check_bytes(blob.body, blob_digest, blob_size)
            _bundle_shape(blob.body)
            bundles.append((blob_digest, blob.body))
        final = await self._request_index(budget, authorization)
        _check_object_bound(final.body, _MAX_INDEX_BYTES)
        try:
            final_media = self._validate_index(final)
        except _HomeAssistantGHCRAcquisitionError as exc:
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.TAG_MUTATED
            ) from exc
        if final_media != index_media or final.body != index.body:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.TAG_MUTATED)
        return _HomeAssistantGHCRAcquisition(
            release_version=_RELEASE,
            image_reference=_IMAGE_REFERENCE,
            index_digest=_EXPECTED_DIGEST,
            index_media_type=index_media,
            index_bytes=index.body,
            sigstore_bundles=tuple(body for _, body in sorted(bundles)),
        )

    async def _request(
        self,
        budget: _AcquisitionBudget,
        *,
        host: str,
        path: str,
        accept: str,
        object_limit: int,
        authorization: str | None = None,
    ) -> _Response:
        remaining_time = budget.deadline - asyncio.get_running_loop().time()
        if remaining_time <= 0:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.TIMEOUT)
        remaining_bytes = _MAX_TOTAL_BYTES - budget.received
        if remaining_bytes < 0:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.RESPONSE_TOO_LARGE)
        limit = min(object_limit, remaining_bytes)
        response = await self._transport.get(
            host=host,
            path=path,
            accept=accept,
            authorization=authorization,
            max_body_bytes=limit,
            timeout=remaining_time,
        )
        if len(response.body) > limit:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.RESPONSE_TOO_LARGE)
        budget.received += len(response.body)
        return response

    async def _request_index(
        self, budget: _AcquisitionBudget, authorization: str | None
    ) -> _Response:
        response = await self._request(
            budget,
            host=_REGISTRY_HOST,
            path=_MANIFEST_PATH,
            accept=_INDEX_MEDIA_TYPE,
            authorization=authorization,
            object_limit=_MAX_INDEX_BYTES,
        )
        if 300 <= response.status < 400:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.REDIRECT_REFUSED)
        return response

    @staticmethod
    def _validate_index(response: _Response) -> str:
        if response.status == 401:
            raise _HomeAssistantGHCRAcquisitionError(
                _FailureReason.AUTHENTICATION_FAILED
            )
        if response.status != 200:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.INDEX_REQUIRED)
        media = _media_type(response.headers)
        if media != _INDEX_MEDIA_TYPE:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.INDEX_REQUIRED)
        digest = response.headers.get("docker-content-digest", "")
        if _DIGEST_RE.fullmatch(digest) is None:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DIGEST_MISMATCH)
        actual = f"sha256:{hashlib.sha256(response.body).hexdigest()}"
        if digest != actual or digest != _EXPECTED_DIGEST:
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.DIGEST_MISMATCH)
        document = _strict_object(response.body, _FailureReason.INDEX_REQUIRED)
        manifests = document.get("manifests")
        if (
            document.get("schemaVersion") != 2
            or document.get("mediaType") != _INDEX_MEDIA_TYPE
            or not isinstance(manifests, list)
            or not manifests
            or len(manifests) > _MAX_DESCRIPTORS
        ):
            raise _HomeAssistantGHCRAcquisitionError(_FailureReason.INDEX_REQUIRED)
        for item in manifests:
            _descriptor(item)
        return media


def _check_object_bound(body: bytes, limit: int) -> None:
    if len(body) > limit:
        raise _HomeAssistantGHCRAcquisitionError(_FailureReason.RESPONSE_TOO_LARGE)
