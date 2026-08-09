"""Socket-only health check for the execution worker container."""

from __future__ import annotations

import json
import socket
from pathlib import Path

SOCKET_PATH = Path("/run/atlas-execution-worker/worker.sock")


def main() -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect(str(SOCKET_PATH))
        connection.sendall(
            b"GET /health HTTP/1.1\r\nHost: worker\r\nConnection: close\r\n\r\n"
        )
        response = b""
        while chunk := connection.recv(4096):
            response += chunk
    body = response.split(b"\r\n\r\n", 1)[1]
    health = json.loads(body)
    if health.get("status") != "healthy" or health.get("execution_enabled") is not False:
        raise SystemExit("worker health contract failed")


if __name__ == "__main__":
    main()
