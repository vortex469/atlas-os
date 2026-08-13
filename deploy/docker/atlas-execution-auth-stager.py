"""Create the persistent Agent-to-worker bearer token without exposing it in env."""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def main() -> None:
    token_path = Path(
        os.environ.get("ATLAS_EXECUTION_AUTH_STAGING_FILE", "/staging/token")
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if not token_path.exists():
        descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        with os.fdopen(descriptor, "w", encoding="ascii") as token_file:
            token_file.write(secrets.token_urlsafe(48))
            token_file.write("\n")
        os.chmod(token_path, 0o400)
        os.chown(token_path, 10001, 10001)
    metadata = token_path.stat()
    if (
        metadata.st_uid != 10001
        or metadata.st_gid != 10001
        or metadata.st_mode & 0o777 != 0o400
    ):
        raise PermissionError("execution authentication token has unsafe ownership or mode")


if __name__ == "__main__":
    main()
