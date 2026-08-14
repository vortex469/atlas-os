from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from app.operator_auth.models import OperatorCredential, OperatorPrincipal


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class CreatedOperatorSession:
    session_token: str
    csrf_token: str
    principal: OperatorPrincipal
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ResolvedOperatorSession:
    token_digest: str
    principal: OperatorPrincipal
    expires_at: datetime
    csrf_digest: str


class OperatorSessionStore:
    def __init__(self, database_path: str | Path, lifetime_seconds: int) -> None:
        self.database_path = str(database_path)
        self.lifetime_seconds = lifetime_seconds
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS operator_sessions (
                    session_id TEXT PRIMARY KEY,
                    token_digest TEXT NOT NULL UNIQUE,
                    operator_id TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    authenticated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    csrf_digest TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    revoked_at TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 1
                )
            """)

    def create(self, credential: OperatorCredential, now: datetime | None = None) -> CreatedOperatorSession:
        authenticated_at = now or datetime.now(UTC)
        expires_at = authenticated_at + timedelta(seconds=self.lifetime_seconds)
        session_token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        principal = OperatorPrincipal(
            operator_id=credential.operator_id,
            authenticated_at=authenticated_at,
            permissions=tuple(sorted(credential.permissions)),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO operator_sessions VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, 1)",
                (
                    secrets.token_hex(16), _digest(session_token), credential.operator_id,
                    "\n".join(principal.permissions), authenticated_at.isoformat(),
                    expires_at.isoformat(), _digest(csrf_token),
                ),
            )
        return CreatedOperatorSession(session_token, csrf_token, principal, expires_at)

    def resolve(self, token: str | None, now: datetime | None = None) -> ResolvedOperatorSession | None:
        if not token:
            return None
        token_digest = _digest(token)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM operator_sessions WHERE token_digest=?", (token_digest,)
            ).fetchone()
        if row is None or row["revoked"]:
            return None
        if not secrets.compare_digest(row["token_digest"], token_digest):
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at <= (now or datetime.now(UTC)):
            return None
        return ResolvedOperatorSession(
            token_digest=token_digest,
            principal=OperatorPrincipal(
                operator_id=row["operator_id"],
                authenticated_at=datetime.fromisoformat(row["authenticated_at"]),
                permissions=tuple(filter(None, row["permissions"].split("\n"))),
            ),
            expires_at=expires_at,
            csrf_digest=row["csrf_digest"],
        )

    def rotate_csrf(self, session: ResolvedOperatorSession) -> str:
        csrf_token = secrets.token_urlsafe(32)
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE operator_sessions SET csrf_digest=? WHERE token_digest=? AND revoked=0",
                (_digest(csrf_token), session.token_digest),
            )
        return csrf_token

    def verify_csrf(self, session: ResolvedOperatorSession, supplied: str | None) -> bool:
        if not supplied:
            return False
        return secrets.compare_digest(session.csrf_digest, _digest(supplied))

    def revoke(self, session: ResolvedOperatorSession, now: datetime | None = None) -> None:
        revoked_at = (now or datetime.now(UTC)).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE operator_sessions SET revoked=1, revoked_at=? WHERE token_digest=?",
                (revoked_at, session.token_digest),
            )
