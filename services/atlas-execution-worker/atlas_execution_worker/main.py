"""Run the execution-disabled worker on a private Unix socket."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from .api import app
from .server import DEFAULT_SOCKET_PATH, bind_socket, cleanup_socket


def main() -> None:
    socket_path = Path(os.environ.get("ATLAS_EXECUTION_WORKER_SOCKET", DEFAULT_SOCKET_PATH))
    server_socket = bind_socket(socket_path)
    try:
        uvicorn.run(app, fd=server_socket.fileno(), log_level="info")
    finally:
        server_socket.close()
        cleanup_socket(socket_path)


if __name__ == "__main__":
    main()
