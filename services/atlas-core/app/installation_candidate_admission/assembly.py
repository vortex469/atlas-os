"""Read-only assembly of ephemeral Installation Candidate Admission v1."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
)
from app.installation_candidate_admission.evaluation import (
    evaluate_installation_candidate_admission,
)
from app.installation_capability.assessment import (
    InstallationCapabilityAssessmentV1,
)
from app.installation_plan.assembly import (
    InstallationPlanItemNotFound,
    InstallationPlanReadDependency,
)
from app.installation_plan.contract import InstallationPlan
from app.installation_targets.contract import InstallationDestinationSelectionV1
from app.installation_targets.store import (
    InstallationDestinationSelectionStore,
    SelectionNotFoundError,
)


class InstallationCandidateAdmissionReadError(RuntimeError):
    """Sanitized failure at a future transport mapping boundary."""


class InstallationCandidateAdmissionInputMissing(
    InstallationCandidateAdmissionReadError
):
    pass


class InstallationCandidateAdmissionInputUnavailable(
    InstallationCandidateAdmissionReadError
):
    pass


class CapabilityAssessmentAssembler(Protocol):
    async def assemble(
        self,
        *,
        plan: InstallationPlan,
        selection: InstallationDestinationSelectionV1,
    ) -> InstallationCapabilityAssessmentV1: ...


class InstallationCandidateAdmissionReadDependency:
    """Assemble one bounded result without persisting or extending validity."""

    def __init__(
        self,
        *,
        plans: InstallationPlanReadDependency,
        selections: InstallationDestinationSelectionStore,
        capabilities: CapabilityAssessmentAssembler,
        clock: Callable[[], datetime],
    ) -> None:
        self._plans = plans
        self._selections = selections
        self._capabilities = capabilities
        self._clock = clock

    async def assemble(
        self,
        *,
        item_id: str,
        selection_id: str,
        principal_id: str,
    ) -> InstallationCandidateAdmissionV1:
        """Read exact caller-owned inputs and apply the pure admission evaluator."""
        try:
            plan = self._plans.assemble(item_id)
            # Store.get is deliberately used instead of the lifecycle service:
            # assembly is observational and must not persist an expiry transition.
            selection = self._selections.get(selection_id, principal_id).record
            if (
                selection.selection_id != selection_id
                or selection.selected_by != principal_id
            ):
                raise SelectionNotFoundError("selection ownership mismatch")
            assessment = await self._capabilities.assemble(
                plan=plan, selection=selection
            )
            evaluated_at = self._clock()
            if (
                type(evaluated_at) is not datetime
                or evaluated_at.tzinfo is None
                or evaluated_at.utcoffset() != timedelta(0)
                or evaluated_at.microsecond
            ):
                raise ValueError("whole-second UTC admission time required")
            result = evaluate_installation_candidate_admission(
                plan=plan,
                selection=selection,
                current_destination=assessment.current_destination,
                capability_assessment=assessment,
                evaluated_at=evaluated_at,
            )
            if result is None:
                raise ValueError("complete closed inputs required")
            return result
        except (InstallationPlanItemNotFound, SelectionNotFoundError):
            raise InstallationCandidateAdmissionInputMissing(
                "installation candidate admission input was not found"
            ) from None
        except InstallationCandidateAdmissionReadError:
            raise
        except Exception:  # noqa: BLE001 - redact every dependency failure
            raise InstallationCandidateAdmissionInputUnavailable(
                "installation candidate admission input is unavailable"
            ) from None
