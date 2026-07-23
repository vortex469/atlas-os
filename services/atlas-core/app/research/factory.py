from __future__ import annotations

from app.research.engine import ResearchEngine
from app.research.parsers.exa import ExaParser
from app.research.providers.mcp_provider import MCPResearchProvider


def create_research_engine() -> ResearchEngine:
    """Create the default ResearchEngine."""

    return ResearchEngine(
        provider=MCPResearchProvider(),
        parser=ExaParser(),
    )