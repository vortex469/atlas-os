"""Minimal non-integrated TCP client for the private execution worker."""

from __future__ import annotations

import json
import socket
from typing import Any

from app.execution.worker_contracts import WorkerExecutionRequest


class WorkerTransportError(RuntimeError):
    """The worker could not be reached or returned malformed HTTP."""


class TcpWorkerClient:
    """One-shot HTTP-over-TCP client with no automatic retries."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout_seconds: float = 2.0,
        *,
        authentication_token: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._authentication_token = authentication_token

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def submit(self, request: WorkerExecutionRequest) -> dict[str, Any]:
        return self._request("POST", "/v1/executions", request.to_dict())

    def get_result(self, request_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/executions/{request_id}")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else b""
        authorization = (
            f"Authorization: Bearer {self._authentication_token}\r\n"
            if self._authentication_token is not None
            else ""
        )
        headers = (
            f"{method} {path} HTTP/1.1\r\n"
            "Host: atlas-execution-worker\r\n"
            "Connection: close\r\n"
            f"{authorization}"
            f"Content-Length: {len(body)}\r\n"
            "Content-Type: application/json\r\n\r\n"
        ).encode()
        try:
            with socket.create_connection(
                (self._host, self._port), timeout=self._timeout_seconds
            ) as connection:
                connection.settimeout(self._timeout_seconds)
                connection.sendall(headers + body)
                response = b""
                while True:
                    chunk = connection.recv(65536)
                    if not chunk:
                        break
                    response += chunk
        except OSError as exc:
            raise WorkerTransportError("worker socket unavailable") from exc
        try:
            header_bytes, response_body = response.split(b"\r\n\r\n", 1)
            status_line = header_bytes.splitlines()[0].decode("ascii")
            status = int(status_line.split()[1])
            decoded = json.loads(response_body)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerTransportError("worker returned malformed HTTP") from exc
        if status >= 400:
            raise WorkerTransportError(decoded.get("error", {}).get("code", "worker_error"))
        return decoded
