from enum import Enum


class DeploymentSource(str, Enum):
    """Supported sources used to describe an application deployment."""

    COMPOSE = "compose"
    GITHUB = "github"
    RECIPE = "recipe"
    HELM = "helm"
    KUBERNETES = "kubernetes"
    CUSTOM = "custom"


class DeploymentRisk(str, Enum):
    """Overall risk assigned to a deployment plan."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationSeverity(str, Enum):
    """Importance assigned to recommendations and warnings."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ComponentKind(str, Enum):
    """Normalized kinds of application components."""

    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    STORAGE = "storage"
    NETWORK = "network"
    MODEL = "model"
    VM = "vm"
    CONTAINER = "container"
    OTHER = "other"


class ExecutionStepStatus(str, Enum):
    """Lifecycle state of a planned execution step."""

    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    COMPLETED = "completed"
    FAILED = "failed"
