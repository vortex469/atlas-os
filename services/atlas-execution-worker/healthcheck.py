"""TCP health check for the execution worker container."""

from __future__ import annotations

import json
import socket

HOST = "127.0.0.1"
PORT = 8081


def main() -> None:
    with socket.create_connection((HOST, PORT), timeout=3) as connection:
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
