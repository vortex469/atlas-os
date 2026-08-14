"""Dedicated authentication for the Agent-to-Core dispatch boundary."""

from __future__ import annotations

import secrets
from pathlib import Path


class OperationalDispatchAuthenticator:
    """Validate one dedicated bearer credential without retaining request input."""

    def __init__(self, token_file: str | Path) -> None:
        self._token_file = Path(token_file)

    def authenticate(self, authorization: str | None) -> bool:
        if authorization is None or not authorization.startswith("Bearer "):
            return False
        supplied = authorization.removeprefix("Bearer ")
        if not supplied or supplied != supplied.strip():
            return False
        try:
            expected = self._token_file.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return False
        return bool(expected) and secrets.compare_digest(supplied, expected)
