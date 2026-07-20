class PlanningError(Exception):
    """Base exception for planning failures."""


class InvalidPlanningRequestError(PlanningError):
    """Raised when a planning request cannot be processed."""