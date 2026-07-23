from __future__ import annotations

import json
import subprocess

from app.research.models import ResearchDocument
from app.research.parsers.exa import ExaParser
from app.research.providers.base import ResearchProvider


class MCPResearchProvider(ResearchProvider):
    """Research provider backed by MCPorter."""

    MCPORTER = "/usr/local/bin/mcporter"
    MCPORTER_CONFIG = "/opt/atlas/config/mcporter.json"

    def __init__(self) -> None:
        self._parser = ExaParser()

    def search(
        self,
        query: str,
    ) -> list[ResearchDocument]:

        response = self._search(query)

        return self._parser.parse(response)

    def _search(
        self,
        query: str,
    ) -> dict:

        raw = self._run_mcporter(
            "call",
            "exa.web_search_exa",
            f"query={query}",
            "numResults=5",
            "--output",
            "json",
        )

        return json.loads(raw)

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
                f"MCPorter failed with exit code "
                f"{result.returncode}: {error}"
            )

        return result.stdout