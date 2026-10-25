"""Bounded one-shot HTTP client for the private execution worker."""
from __future__ import annotations

import json
import math
import re
import socket
import time
from typing import Any

from app.execution.worker_contracts import WorkerExecutionRequest
from app.execution.worker_json import decode_worker_json

MAX_RESPONSE_HEADER_BYTES = 16_384
# Three bounded text fields can each expand sixfold under JSON escaping.
MAX_RESPONSE_BODY_BYTES = 24 * 1024 * 1024


class WorkerTransportError(RuntimeError):
    """The worker could not be reached or returned malformed HTTP."""


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WorkerTransportError('worker request deadline exceeded')
    return remaining


def _response_headers(raw: bytes | bytearray) -> tuple[int, int]:
    lines = bytes(raw).split(b'\r\n')
    match = re.fullmatch(rb'HTTP/1\.[01] ([2-5][0-9]{2})(?: [\x20-\x7e]*)?', lines[0])
    if match is None:
        raise WorkerTransportError('worker returned malformed HTTP')
    headers: dict[bytes, bytes] = {}
    for line in lines[1:]:
        name, separator, value = line.partition(b':')
        if not separator or not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise WorkerTransportError('worker returned malformed HTTP')
        name = name.lower()
        if name in headers or any(byte < 32 and byte != 9 or byte >= 127 for byte in value):
            raise WorkerTransportError('worker returned ambiguous HTTP headers')
        headers[name] = value.strip(b' \t')
    length = headers.get(b'content-length', b'')
    if b'transfer-encoding' in headers or not re.fullmatch(rb'[0-9]{1,10}', length):
        raise WorkerTransportError('worker returned unsupported HTTP framing')
    size = int(length)
    if size > MAX_RESPONSE_BODY_BYTES:
        raise WorkerTransportError('worker response body exceeds bound')
    return int(match[1]), size


class TcpWorkerClient:
    """One request, one total I/O deadline, bounded framing, no retries."""

    def __init__(
        self, host: str, port: int, timeout_seconds: float = 2.0, *,
        authentication_token: str | None = None,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError('worker timeout must be finite and positive')
        if authentication_token is not None and (not authentication_token or any(not 33 <= ord(char) <= 126 for char in authentication_token)):
            raise ValueError('worker authentication token must be one ASCII credential')
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._authentication_token = authentication_token

    def health(self) -> dict[str, Any]:
        return self._request('GET', '/health')

    def submit(self, request: WorkerExecutionRequest) -> dict[str, Any]:
        return self._request('POST', '/v1/executions', request.to_dict())

    def get_result(self, request_id: str) -> dict[str, Any]:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', request_id):
            raise WorkerTransportError('invalid worker request identity')
        return self._request('GET', f'/v1/executions/{request_id}')

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, separators=(',', ':')).encode() if payload is not None else b''
        authorization = (
            f'Authorization: Bearer {self._authentication_token}\r\n'
            if self._authentication_token is not None else ''
        )
        headers = (
            f'{method} {path} HTTP/1.1\r\n'
            'Host: atlas-execution-worker\r\n'
            'Connection: close\r\n'
            f'{authorization}'
            f'Content-Length: {len(body)}\r\n'
            'Content-Type: application/json\r\n\r\n'
        ).encode()
        deadline = time.monotonic() + self._timeout_seconds
        try:
            with socket.create_connection((self._host, self._port), timeout=_remaining(deadline)) as connection:
                connection.settimeout(_remaining(deadline))
                connection.sendall(headers + body)
                response = bytearray()
                header_end = -1
                expected = None
                while True:
                    connection.settimeout(_remaining(deadline))
                    chunk = connection.recv(65536)
                    if not chunk:
                        raise WorkerTransportError('worker returned incomplete HTTP response')
                    _remaining(deadline)
                    response.extend(chunk)
                    if header_end < 0:
                        header_end = response.find(b'\r\n\r\n')
                        if header_end < 0 and len(response) > MAX_RESPONSE_HEADER_BYTES:
                            raise WorkerTransportError('worker response headers exceed bound')
                        if header_end >= 0:
                            if header_end + 4 > MAX_RESPONSE_HEADER_BYTES:
                                raise WorkerTransportError('worker response headers exceed bound')
                            status, expected = _response_headers(response[:header_end])
                    if header_end >= 0:
                        received = len(response) - header_end - 4
                        if received > expected:
                            raise WorkerTransportError('worker response length mismatch')
                        if received == expected:
                            break
        except OSError as exc:
            raise WorkerTransportError('worker socket unavailable') from exc
        try:
            decoded = decode_worker_json(response[header_end + 4:])
            if not isinstance(decoded, dict):
                raise TypeError('worker response must be an object')
        except (TypeError, ValueError, UnicodeDecodeError, RecursionError) as exc:
            raise WorkerTransportError('worker returned malformed JSON') from exc
        _remaining(deadline)
        if status >= 300:
            error = decoded.get('error')
            code = error.get('code') if isinstance(error, dict) else None
            if not isinstance(code, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
                code = 'worker_error'
            raise WorkerTransportError(code)
        return decoded
