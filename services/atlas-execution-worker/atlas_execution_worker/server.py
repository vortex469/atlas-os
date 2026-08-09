"""Unix-domain-socket server lifecycle for the worker skeleton."""

from __future__ import annotations

import os
import socket
from pathlib import Path

DEFAULT_SOCKET_PATH = Path("/run/atlas-execution-worker/worker.sock")
SOCKET_MODE = 0o660


def prepare_socket_path(socket_path: Path) -> None:
    """Create a private parent and remove only a stale Unix socket."""

    socket_path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    if socket_path.exists():
        if not socket_path.is_socket():
            raise RuntimeError("configured worker socket path is not a socket")
        socket_path.unlink()


def bind_socket(socket_path: Path) -> socket.socket:
    """Bind a Unix socket with restrictive filesystem permissions."""

    prepare_socket_path(socket_path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(socket_path))
        os.chmod(socket_path, SOCKET_MODE)
        server.listen()
    except Exception:
        server.close()
        socket_path.unlink(missing_ok=True)
        raise
    return server


def cleanup_socket(socket_path: Path) -> None:
    """Remove the socket only when it is a socket file."""

    if socket_path.exists() and socket_path.is_socket():
        socket_path.unlink()
