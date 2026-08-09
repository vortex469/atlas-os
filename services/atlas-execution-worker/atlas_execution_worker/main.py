"""Run the execution-disabled worker on a private Unix socket."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from .api import app
from .server import DEFAULT_SOCKET_PATH, cleanup_socket, prepare_socket_path


def main() -> None:
    socket_path = Path(os.environ.get("ATLAS_EXECUTION_WORKER_SOCKET", DEFAULT_SOCKET_PATH))
    prepare_socket_path(socket_path)
    try:
        uvicorn.run(app, uds=str(socket_path), log_level="info")
    finally:
        cleanup_socket(socket_path)


if __name__ == "__main__":
    main()
