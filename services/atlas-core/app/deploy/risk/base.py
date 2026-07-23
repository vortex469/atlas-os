from __future__ import annotations

from abc import ABC, abstractmethod

from app.deploy.analysis import Diagnostic
from app.deploy.plan import DeploymentPlan


class RiskRule(ABC):
    """Base class for deployment risk rules."""

    rule_id: str = "UNKNOWN"

    @abstractmethod
    def evaluate(
        self,
        plan: DeploymentPlan,
    ) -> list[Diagnostic]:
        """Evaluate a deployment plan and return diagnostics."""

        raise NotImplementedError