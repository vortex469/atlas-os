from __future__ import annotations

import re
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from app.deploy.analysis import AnalysisRequest, AnalysisResult
from app.deploy.analyzers.base import DeploymentAnalyzer
from app.deploy.components import (
    ApplicationComponent,
    HealthCheck,
    PortBinding,
    StorageMount,
)
from app.deploy.enums import (
    ComponentKind,
    DeploymentSource,
)
from app.deploy.plan import DeploymentPlan

from app.deploy.components import (
    ApplicationComponent,
    HealthCheck,
    PortBinding,
    StorageMount,
)

class ComposeAnalyzer(DeploymentAnalyzer):
    """Analyze parsed Docker Compose documents."""

    source_type = DeploymentSource.COMPOSE.value

    def analyze(
        self,
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Convert a parsed Compose document into a deployment plan."""

        started_at = perf_counter()

        if request.source != DeploymentSource.COMPOSE:
            raise ValueError(
                "ComposeAnalyzer only supports Compose analysis requests."
            )

        services = request.document.get("services", {})

        if not isinstance(services, Mapping):
            raise ValueError(
                "Compose document 'services' must be a mapping."
            )

        components = [
            self._build_component(service_name, service)
            for service_name, service in services.items()
        ]

        plan_id = self._build_plan_id(
            request.reference or "compose"
        )

        plan = DeploymentPlan(
            id=plan_id,
            name=self._build_plan_name(
                request.document,
                request.reference,
            ),
            source=DeploymentSource.COMPOSE,
            source_reference=request.reference,
            components=components,
        )

        elapsed_ms = (
            perf_counter() - started_at
        ) * 1000

        return AnalysisResult(
            analyzer=self.source_type,
            plan=plan,
            elapsed_ms=elapsed_ms,
        )

    def _build_component(
        self,
        service_name: str,
        service: Any,
    ) -> ApplicationComponent:
        if not isinstance(service, Mapping):
            raise ValueError(
                f"Compose service '{service_name}' must be a mapping."
            )

        return ApplicationComponent(
            id=self._normalize_id(service_name),
            name=service_name.replace("-", " ").replace(
                "_",
                " ",
            ).title(),
            kind=ComponentKind.SERVICE,
            image=self._optional_string(
                service.get("image")
            ),
            command=self._parse_command(
                service.get("command")
            ),
            ports=self._parse_ports(
                service.get("ports", [])
            ),
            storage=self._parse_volumes(
                service.get("volumes", [])
            ),
            environment=self._parse_environment(
                service.get("environment", {})
            ),
            dependencies=self._parse_dependencies(
                service.get("depends_on", [])
            ),
            healthcheck=self._parse_healthcheck(
                service.get("healthcheck")
            ),
            metadata={
                "build": service.get("build"),
                "restart": service.get("restart"),
                "network_mode": service.get(
                    "network_mode"
                ),
                "privileged": bool(
                    service.get("privileged", False)
                ),
            },
        )

    def _parse_ports(
        self,
        ports: Any,
    ) -> list[PortBinding]:
        if ports is None:
            return []

        if not isinstance(ports, list):
            raise ValueError(
                "Compose service ports must be a list."
            )

        bindings: list[PortBinding] = []

        for port in ports:
            if isinstance(port, int):
                bindings.append(
                    PortBinding(
                        container_port=port,
                    )
                )
                continue

            if isinstance(port, str):
                bindings.append(
                    self._parse_short_port(port)
                )
                continue

            if isinstance(port, Mapping):
                target = port.get("target")

                if target is None:
                    raise ValueError(
                        "Compose long-form port requires 'target'."
                    )

                published = port.get("published")
                protocol = str(
                    port.get("protocol", "tcp")
                )

                bindings.append(
                    PortBinding(
                        container_port=int(target),
                        host_port=(
                            int(published)
                            if published is not None
                            else None
                        ),
                        protocol=protocol,
                        public=self._is_public_host_ip(
                            port.get("host_ip")
                        ),
                    )
                )
                continue

            raise ValueError(
                "Unsupported Compose port definition."
            )

        return bindings

    def _parse_short_port(
        self,
        value: str,
    ) -> PortBinding:
        definition, _, protocol = value.partition("/")

        parts = definition.rsplit(":", 2)

        host_ip: str | None = None
        host_port: int | None = None

        if len(parts) == 1:
            container_port = int(parts[0])

        elif len(parts) == 2:
            host_port = int(parts[0])
            container_port = int(parts[1])

        else:
            host_ip = parts[0]
            host_port = int(parts[1])
            container_port = int(parts[2])

        return PortBinding(
            container_port=container_port,
            host_port=host_port,
            protocol=protocol or "tcp",
            public=self._is_public_host_ip(host_ip),
        )

    def _parse_volumes(
        self,
        volumes: Any,
    ) -> list[StorageMount]:
        if volumes is None:
            return []

        if not isinstance(volumes, list):
            raise ValueError(
                "Compose service volumes must be a list."
            )

        mounts: list[StorageMount] = []

        for volume in volumes:
            if isinstance(volume, str):
                mounts.append(
                    self._parse_short_volume(volume)
                )
                continue

            if isinstance(volume, Mapping):
                target = volume.get("target")

                if not target:
                    raise ValueError(
                        "Compose long-form volume requires 'target'."
                    )

                mount_type = str(
                    volume.get("type", "volume")
                )

                mounts.append(
                    StorageMount(
                        source=self._optional_string(
                            volume.get("source")
                        ),
                        target=str(target),
                        read_only=bool(
                            volume.get(
                                "read_only",
                                False,
                            )
                        ),
                        persistent=(
                            mount_type != "tmpfs"
                        ),
                    )
                )
                continue

            raise ValueError(
                "Unsupported Compose volume definition."
            )

        return mounts

    def _parse_short_volume(
        self,
        value: str,
    ) -> StorageMount:
        parts = value.split(":")

        if len(parts) == 1:
            return StorageMount(
                target=parts[0],
            )

        source = parts[0]
        target = parts[1]
        options = (
            parts[2].split(",")
            if len(parts) >= 3
            else []
        )

        return StorageMount(
            source=source,
            target=target,
            read_only="ro" in options,
        )

    def _parse_environment(
        self,
        environment: Any,
    ) -> dict[str, str]:
        if environment is None:
            return {}

        if isinstance(environment, Mapping):
            return {
                str(key): (
                    ""
                    if value is None
                    else str(value)
                )
                for key, value in environment.items()
            }

        if isinstance(environment, list):
            result: dict[str, str] = {}

            for item in environment:
                if not isinstance(item, str):
                    raise ValueError(
                        "Compose environment list values must be strings."
                    )

                key, separator, value = item.partition("=")

                result[key] = (
                    value
                    if separator
                    else ""
                )

            return result

        raise ValueError(
            "Compose environment must be a mapping or list."
        )

    def _parse_dependencies(
        self,
        depends_on: Any,
    ) -> list[str]:
        if depends_on is None:
            return []

        if isinstance(depends_on, list):
            return [
                self._normalize_id(str(item))
                for item in depends_on
            ]

        if isinstance(depends_on, Mapping):
            return [
                self._normalize_id(str(item))
                for item in depends_on.keys()
            ]

        raise ValueError(
            "Compose depends_on must be a list or mapping."
        )
    
    def _parse_healthcheck(
        self,
        healthcheck: Any,
    ) -> HealthCheck | None:
        if healthcheck is None:
            return None

        if not isinstance(healthcheck, Mapping):
            raise ValueError(
                "Compose service healthcheck must be a mapping."
            )

        disabled = bool(
            healthcheck.get("disable", False)
        )

        raw_test = healthcheck.get("test", [])

        if isinstance(raw_test, str):
            test = [raw_test]
        elif isinstance(raw_test, list):
            test = [str(item) for item in raw_test]
        else:
            raise ValueError(
                "Compose healthcheck test must be a string or list."
            )

        return HealthCheck(
            test=test,
            interval=self._optional_string(
                healthcheck.get("interval")
            ),
            timeout=self._optional_string(
                healthcheck.get("timeout")
            ),
            retries=(
                int(healthcheck["retries"])
                if healthcheck.get("retries") is not None
                else None
            ),
            start_period=self._optional_string(
                healthcheck.get("start_period")
            ),
            disabled=disabled,
        )

    def _parse_command(
        self,
        command: Any,
    ) -> list[str]:
        if command is None:
            return []

        if isinstance(command, list):
            return [
                str(item)
                for item in command
            ]

        if isinstance(command, str):
            return [command]

        raise ValueError(
            "Compose command must be a string or list."
        )

    def _build_plan_name(
        self,
        document: Mapping[str, Any],
        reference: str | None,
    ) -> str:
        configured_name = document.get("name")

        if configured_name:
            return str(configured_name)

        if reference:
            filename = reference.rsplit("/", 1)[-1]

            for suffix in (
                ".yaml",
                ".yml",
            ):
                if filename.endswith(suffix):
                    filename = filename[
                        :-len(suffix)
                    ]

            return filename

        return "Compose Deployment"

    def _build_plan_id(
        self,
        reference: str,
    ) -> str:
        filename = reference.rsplit("/", 1)[-1]

        for suffix in (
            ".yaml",
            ".yml",
        ):
            if filename.endswith(suffix):
                filename = filename[
                    :-len(suffix)
                ]

        return self._normalize_id(filename)

    def _normalize_id(
        self,
        value: str,
    ) -> str:
        normalized = re.sub(
            r"[^a-z0-9]+",
            "-",
            value.lower(),
        ).strip("-")

        return normalized or "deployment"

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        return str(value)

    def _is_public_host_ip(
        self,
        host_ip: Any,
    ) -> bool:
        if host_ip is None:
            return True

        return str(host_ip) not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }