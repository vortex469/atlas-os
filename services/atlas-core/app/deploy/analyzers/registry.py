from __future__ import annotations

from app.deploy.analyzers.base import DeploymentAnalyzer


class AnalyzerRegistry:
    """Registry of deployment analyzers by source type."""

    def __init__(self) -> None:
        self._analyzers: dict[str, DeploymentAnalyzer] = {}

    def register(self, analyzer: DeploymentAnalyzer) -> None:
        """Register an analyzer for its declared source type."""

        if analyzer.source_type in self._analyzers:
            raise ValueError(
                f"Analyzer already registered: {analyzer.source_type}"
            )

        self._analyzers[analyzer.source_type] = analyzer

    def get(self, source_type: str) -> DeploymentAnalyzer:
        """Return the analyzer registered for a source type."""

        try:
            return self._analyzers[source_type]
        except KeyError as exc:
            raise KeyError(
                f"No analyzer registered for '{source_type}'"
            ) from exc

    def registered(self) -> list[str]:
        """Return registered source types in deterministic order."""

        return sorted(self._analyzers)
