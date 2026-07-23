from enum import StrEnum


class ProviderCapability(StrEnum):
    """Capabilities that an Atlas provider may expose."""

    HEALTH = "health"
    FINDINGS = "findings"
    RECOMMENDATIONS = "recommendations"
    ACTIONS = "actions"
    METRICS = "metrics"
    LOGS = "logs"
    CONFIGURATION = "configuration"


class ProviderWorkspace(StrEnum):
    """Atlas workspace in which a provider primarily belongs."""

    OPERATIONS = "operations"
    AUTOMATION = "automation"
    KNOWLEDGE = "knowledge"
    DEVELOPER = "developer"


class ProviderPriority(StrEnum):
    """Controls provider ordering and operational importance."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
