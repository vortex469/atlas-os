from app.research.engine import ResearchEngine
from app.research.factory import create_research_engine
from app.research.parsers.exa import ExaParser
from app.research.providers.mcp_provider import MCPResearchProvider


def test_factory_creates_default_engine() -> None:
    engine = create_research_engine()

    assert isinstance(engine, ResearchEngine)
    assert isinstance(engine.provider, MCPResearchProvider)
    assert isinstance(engine.parser, ExaParser)
