"""Inert construction for the InstallationPlan read dependency."""

from app.config.inventory import ATLAS_ROOT
from app.installation_plan.assembly import (
    InstallationPlanReadDependency,
    default_installation_plan_dependency,
)


def get_installation_plan_read_dependency() -> InstallationPlanReadDependency:
    """Construct the local-only read dependency without reading any inputs."""

    return default_installation_plan_dependency(repository_root=ATLAS_ROOT)
