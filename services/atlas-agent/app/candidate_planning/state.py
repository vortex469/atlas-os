"""Thread-safe in-memory candidate-planning session state."""

from __future__ import annotations

from threading import RLock

from app.candidate_planning.models import CandidatePlanningSession

CandidatePlanningStateSnapshot = dict[str, CandidatePlanningSession]


class CandidatePlanningStateStore:
    """Store immutable candidate-planning sessions independently from workflows."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, CandidatePlanningSession] = {}

    def export_snapshot(self) -> CandidatePlanningStateSnapshot:
        with self._lock:
            return dict(self._sessions)

    def replace_snapshot(self, snapshot: CandidatePlanningStateSnapshot) -> None:
        with self._lock:
            self._sessions = dict(snapshot)

    def create_session(self, session: CandidatePlanningSession) -> None:
        if not session.identifier.strip():
            raise ValueError("Candidate planning session identifier must not be blank")
        with self._lock:
            if session.identifier in self._sessions:
                raise ValueError(
                    "Candidate planning session identifier already exists: "
                    f"{session.identifier}"
                )
            self._sessions[session.identifier] = session

    def get_session(self, identifier: str) -> CandidatePlanningSession | None:
        with self._lock:
            return self._sessions.get(identifier)

    def find_active_for_candidate(
        self,
        candidate_id: str,
    ) -> tuple[CandidatePlanningSession, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        session
                        for session in self._sessions.values()
                        if session.candidate_id == candidate_id
                    ),
                    key=lambda session: session.identifier,
                )
            )
