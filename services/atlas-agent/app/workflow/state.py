"""Thread-safe in-memory Atlas Agent workflow state."""

from threading import RLock

from app.review.models import ReviewReport
from app.verification.models import VerificationReport
from app.workflow.models import SprintStatus


class WorkflowStateStore:
    """Store the latest immutable workflow artifacts in memory."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sprint: SprintStatus | None = None
        self._verification: VerificationReport | None = None
        self._review: ReviewReport | None = None

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
