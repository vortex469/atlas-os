from __future__ import annotations

import subprocess

from app.research.models import ResearchDocument
from app.research.providers.base import ResearchProvider


class AgentReachProvider(ResearchProvider):
    """Research provider backed by Agent-Reach and MCPorter."""

    MCPORTER = "/usr/local/bin/mcporter"
    MCPORTER_CONFIG = "/opt/atlas/config/mcporter.json"

    def search(
        self,
        query: str,
    ) -> list[ResearchDocument]:
        raw = self._search(query)
        return self._normalize(raw)

    def _search(
        self,
        query: str,
    ) -> str:
        return self._run_mcporter(
            "call",
            "exa.web_search_exa",
            f"query={query}",
            "numResults=5",
        )

    def _normalize(
        self,
        raw: str,
    ) -> list[ResearchDocument]:
        raise NotImplementedError

    def _run_mcporter(
        self,
        *args: str,
    ) -> str:
        """Execute an MCPorter command and return stdout."""

        result = subprocess.run(
            [
                self.MCPORTER,
                "--config",
                self.MCPORTER_CONFIG,
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"MCPorter failed with exit code {result.returncode}: {error}"
            )

        return result.stdout
