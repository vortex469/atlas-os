from __future__ import annotations

from pathlib import PurePosixPath

from app.deploy.analysis import Diagnostic
from app.deploy.enums import RecommendationSeverity
from app.deploy.plan import DeploymentPlan
from app.deploy.risk.base import RiskRule


class DockerSocketMountRule(RiskRule):
    """Detect access to the host Docker control socket."""

    rule_id = "DOCKER_SOCKET_MOUNT"

    def evaluate(
        self,
        plan: DeploymentPlan,
    ) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []

        for component in plan.components:
            for mount in component.storage:
                if not self._is_docker_socket_mount(
                    mount.source,
                    mount.target,
                ):
                    continue

                diagnostics.append(
                    Diagnostic(
                        code=self.rule_id,
                        severity=RecommendationSeverity.CRITICAL,
                        message=(
                            f"Component '{component.name}' mounts "
                            "the Docker socket."
                        ),
                        component_id=component.id,
                        recommendation=(
                            "Remove Docker socket access unless it is "
                            "strictly required. Prefer a restricted "
                            "socket proxy when access is unavoidable."
                        ),
                    )
                )

        return diagnostics

    def _is_docker_socket_mount(
        self,
        source: str | None,
        target: str,
    ) -> bool:
        docker_socket = PurePosixPath(
            "/var/run/docker.sock"
        )

        source_path = (
            PurePosixPath(source)
            if source and source.startswith("/")
            else None
        )

        target_path = (
            PurePosixPath(target)
            if target.startswith("/")
            else None
        )

        return (
            source_path == docker_socket
            or target_path == docker_socket
        )