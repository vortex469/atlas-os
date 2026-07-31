"""Thread-safe in-memory Atlas Agent workflow state."""

from dataclasses import replace
from threading import RLock

from app.review.models import ReviewReport
from app.verification.models import VerificationReport
from app.workflow.models import (
    SprintStatus,
    WorkflowSession,
    WorkflowSessionState,
)


class WorkflowStateStore:
    """Store the latest immutable workflow artifacts in memory."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sprint: SprintStatus | None = None
        self._verification: VerificationReport | None = None
        self._review: ReviewReport | None = None
        self._sessions: dict[str, WorkflowSession] = {}

    def create_session(self, session: WorkflowSession) -> None:
        """Store a uniquely identified immutable workflow session."""

        if not session.identifier.strip():
            raise ValueError("Workflow session identifier must not be blank")

        with self._lock:
            if session.identifier in self._sessions:
                raise ValueError(
                    "Workflow session identifier already exists: "
                    f"{session.identifier}"
                )

            self._sessions[session.identifier] = session

    def get_session(self, identifier: str) -> WorkflowSession | None:
        """Return a workflow session by identifier when it exists."""

        with self._lock:
            return self._sessions.get(identifier)

    def delete_session(self, identifier: str) -> bool:
        """Delete a workflow session and report whether it existed."""

        with self._lock:
            return self._sessions.pop(identifier, None) is not None

    def transition_session(
        self,
        identifier: str,
        expected_state: WorkflowSessionState,
        new_state: WorkflowSessionState,
        **artifacts: object,
    ) -> bool:
        """Atomically replace state and artifacts when current state matches."""

        with self._lock:
            session = self._sessions.get(identifier)

            if session is None or session.state is not expected_state:
                return False

            self._sessions[identifier] = replace(
                session,
                state=new_state,
                **artifacts,
            )
            return True

    def publish_sprint(self, status: SprintStatus) -> None:
        """Publish the current sprint status."""

        with self._lock:
            self._sprint = status

    def publish_verification(self, report: VerificationReport) -> None:
        """Publish the latest verification report."""

        with self._lock:
            self._verification = report

    def publish_review(self, report: ReviewReport) -> None:
        """Publish the latest review report."""

        with self._lock:
            self._review = report

    def get_sprint(self) -> SprintStatus | None:
        """Return the current sprint status."""

        with self._lock:
            return self._sprint

    def get_verification(self) -> VerificationReport | None:
        """Return the latest verification report."""

        with self._lock:
            return self._verification

    def get_review(self) -> ReviewReport | None:
        """Return the latest review report."""

        with self._lock:
            return self._review
