from __future__ import annotations

from app.discovery.compatibility import (
    CompatibilityContext,
    CompatibilityContextBuilder,
    ObservedFact,
)


class StaticCompatibilityContextBuilder:
    """Default provider-neutral context builder for Discovery compatibility.

    The compatibility engine consumes only observed facts. Provider-specific and
    system-specific observation belongs in builder implementations like this one,
    not in the evaluator. D7 keeps the default context intentionally conservative
    until Atlas has a richer host inventory source.
    """

    def build_context(self, target: str = "atlas") -> CompatibilityContext:
        return CompatibilityContext(
            target_id=target,
            target_type="atlas_environment",
            facts=(
                ObservedFact(
                    id="context-builder",
                    kind="context_builder",
                    value="static",
                    source="atlas.discovery.environment",
                    metadata={
                        "note": (
                            "D7 default context is provider-neutral and does not "
                            "infer unavailable hardware, runtime, or network facts."
                        ),
                    },
                ),
            ),
            capabilities=None,
            runtimes=None,
            operating_system=None,
            architecture=None,
            cpu_cores=None,
            memory_mb=None,
            storage_gb=None,
            gpu_available=None,
            gpu_memory_gb=None,
            devices=None,
            open_ports=None,
            installed_services=None,
        )


def get_default_context_builder() -> CompatibilityContextBuilder:
    return StaticCompatibilityContextBuilder()
