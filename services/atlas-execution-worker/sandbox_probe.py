"""Disposable runtime proof for the confined Codex workspace profile."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    outside_path = Path(sys.argv[1])
    authentication_path = Path(sys.argv[2])
    Path("workspace-proof").write_text("workspace-write-ok\n")
    try:
        outside_path.write_text("escaped\n")
    except OSError:
        pass
    else:
        raise SystemExit("outside-workspace write unexpectedly succeeded")

    token = authentication_path.read_text(encoding="ascii").strip()
    request = urllib.request.Request(
        "http://127.0.0.1:8081/v1/executions/sandbox-probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            request, timeout=3
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        error = json.loads(exc.read())["error"]["code"]
        if error != "untrusted_peer":
            raise SystemExit("worker returned the wrong peer-denial result")
    else:
        raise SystemExit("sandbox reached the worker control plane")


if __name__ == "__main__":
    main()
