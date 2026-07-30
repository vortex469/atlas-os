"""Model-assisted analysis of deterministic implementation plans."""

from app.model_providers.models import ModelResponse
from app.model_service.service import ModelService
from app.planning.models import ImplementationPlan


class PlanningAdvisor:
    """Request model analysis without changing deterministic planning."""

    def __init__(self, *, model_service: ModelService) -> None:
        """Initialize the advisor with the configured model service."""

        self._model_service = model_service

    def analyze(self, plan: ImplementationPlan) -> ModelResponse:
        """Analyze an existing plan without modifying it."""

        return self._model_service.generate(
            prompt=self._build_prompt(plan),
        )

    @staticmethod
    def _build_prompt(plan: ImplementationPlan) -> str:
        """Build a deterministic planning-analysis prompt."""

        branch = plan.branch if plan.branch is not None else "detached HEAD"
        head_commit = (
            plan.head_commit
            if plan.head_commit is not None
            else "no HEAD commit"
        )

        scope_items = PlanningAdvisor._format_items(plan.scope_items)
        affected_files = PlanningAdvisor._format_items(
            tuple(str(path) for path in plan.affected_files)
        )
        required_tests = PlanningAdvisor._format_items(plan.required_tests)
        risks = PlanningAdvisor._format_items(
            tuple(
                f"[{risk.source}] {risk.code}: {risk.summary}"
                for risk in plan.risks
            )
        )

        return (
            "Analyze the following approved implementation plan.\n"
            "Provide planning analysis only. Do not modify files, execute "
            "commands, or expand the approved scope.\n\n"
            f"Checkpoint: {plan.checkpoint_id}\n"
            f"Title: {plan.title}\n"
            f"Goal: {plan.goal}\n"
            f"Repository root: {plan.repository_root}\n"
            f"Branch: {branch}\n"
            f"HEAD commit: {head_commit}\n\n"
            f"Approved scope:\n{scope_items}\n\n"
            f"Affected files:\n{affected_files}\n\n"
            f"Required tests:\n{required_tests}\n\n"
            f"Known risks:\n{risks}\n"
        )

    @staticmethod
    def _format_items(items: tuple[str, ...]) -> str:
        """Format ordered values for a stable prompt."""

        if not items:
            return "- None"

        return "\n".join(f"- {item}" for item in items)
