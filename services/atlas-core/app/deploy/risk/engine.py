from __future__ import annotations

from collections.abc import Iterable

from app.deploy.analysis import Diagnostic
from app.deploy.plan import DeploymentPlan
from app.deploy.risk.base import RiskRule


class RiskEngine:
    """Evaluate deployment plans using registered risk rules."""

    def __init__(
        self,
        rules: Iterable[RiskRule] | None = None,
    ) -> None:
        self._rules: dict[str, RiskRule] = {}

        for rule in rules or []:
            self.register(rule)

    def register(
        self,
        rule: RiskRule,
    ) -> None:
        """Register a risk rule by its unique rule ID."""

        if rule.rule_id in self._rules:
            raise ValueError(
                f"Risk rule already registered: {rule.rule_id}"
            )

        self._rules[rule.rule_id] = rule

    def get(
        self,
        rule_id: str,
    ) -> RiskRule:
        """Return a registered rule."""

        try:
            return self._rules[rule_id]
        except KeyError as exc:
            raise KeyError(
                f"No risk rule registered for '{rule_id}'"
            ) from exc

    def registered(self) -> list[str]:
        """Return registered rule IDs in deterministic order."""

        return sorted(self._rules)

    def evaluate(
        self,
        plan: DeploymentPlan,
    ) -> list[Diagnostic]:
        """Evaluate a plan against every registered rule."""

        diagnostics: list[Diagnostic] = []

        for rule_id in self.registered():
            diagnostics.extend(
                self._rules[rule_id].evaluate(plan)
            )

        return diagnostics