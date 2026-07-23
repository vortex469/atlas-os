from app.knowledge_engine.assessors.postgres import (
    PostgresAssessor,
)
from app.knowledge_engine.assessors.registry import (
    AssessorRegistry,
)


def test_returns_postgres_assessor() -> None:
    registry = AssessorRegistry()

    assessor = registry.get("postgres")

    assert isinstance(
        assessor,
        PostgresAssessor,
    )


def test_returns_none_for_unknown_application() -> None:
    registry = AssessorRegistry()

    assert registry.get("unknown") is None
