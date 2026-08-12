"""Durable write-ahead journal for worker patch application."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class PatchJournalError(RuntimeError):
    """The bounded worker patch journal cannot be read or written safely."""


class PatchJournal:
    """Single-file, atomic, worker-owned patch intent journal."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self.path = state_dir / "worker-patch-journal.json"

    def write(self, payload: dict[str, Any]) -> None:
        self._state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        temporary = self.path.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o600)
            temporary.replace(self.path)
            self.path.chmod(0o600)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise PatchJournalError("worker patch journal cannot be written") from exc

    def read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise PatchJournalError("worker patch journal cannot be read") from exc
        if not isinstance(payload, dict):
            raise PatchJournalError("worker patch journal is invalid")
        return payload

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise PatchJournalError("worker patch journal cannot be finalized") from exc
