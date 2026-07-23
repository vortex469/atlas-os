from __future__ import annotations

from typing import Any

from app.research.engine import ResearchEngine
from app.research.models import ResearchDocument


class FakeProvider:
    def __init__(
        self,
        response: dict[str, Any],
    ) -> None:
        self.response = response
        self.queries: list[str] = []

    def search(
        self,
        query: str,
    ) -> dict[str, Any]:
        self.queries.append(query)
        return self.response


class FakeParser:
    def __init__(
        self,
        documents: list[ResearchDocument],
    ) -> None:
        self.documents = documents
        self.responses: list[dict[str, Any]] = []

    def parse(
        self,
        response: dict[str, Any],
    ) -> list[ResearchDocument]:
        self.responses.append(response)
        return self.documents


def make_document(
    title: str,
    url: str,
) -> ResearchDocument:
    return ResearchDocument(
        title=title,
        url=url,
        source="test",
        provider="fake",
        content="Test content",
    )


def test_search_calls_provider_with_query() -> None:
    provider = FakeProvider(response={"content": []})
    parser = FakeParser(documents=[])
    engine = ResearchEngine(
        provider=provider,
        parser=parser,
    )

    engine.search("Atlas research")

    assert provider.queries == ["Atlas research"]


def test_search_passes_provider_response_to_parser() -> None:
    response = {"content": [{"type": "text", "text": "Example"}]}
    provider = FakeProvider(response=response)
    parser = FakeParser(documents=[])
    engine = ResearchEngine(
        provider=provider,
        parser=parser,
    )

    engine.search("Atlas")

    assert parser.responses == [response]


def test_search_returns_unique_documents() -> None:
    documents = [
        make_document(
            title="First",
            url="https://example.com/first",
        ),
        make_document(
            title="Second",
            url="https://example.com/second",
        ),
    ]

    engine = ResearchEngine(
        provider=FakeProvider(response={}),
        parser=FakeParser(documents=documents),
    )

    result = engine.search("Atlas")

    assert result == documents


def test_search_removes_duplicate_urls() -> None:
    first = make_document(
        title="First result",
        url="https://example.com/article",
    )
    duplicate = make_document(
        title="Duplicate result",
        url="HTTPS://EXAMPLE.COM/ARTICLE/",
    )

    engine = ResearchEngine(
        provider=FakeProvider(response={}),
        parser=FakeParser(documents=[first, duplicate]),
    )

    result = engine.search("Atlas")

    assert result == [first]


def test_search_preserves_document_order() -> None:
    first = make_document(
        title="First",
        url="https://example.com/first",
    )
    second = make_document(
        title="Second",
        url="https://example.com/second",
    )
    duplicate_first = make_document(
        title="Duplicate first",
        url="https://example.com/first/",
    )

    engine = ResearchEngine(
        provider=FakeProvider(response={}),
        parser=FakeParser(
            documents=[
                first,
                second,
                duplicate_first,
            ]
        ),
    )

    result = engine.search("Atlas")

    assert result == [first, second]


def test_search_returns_empty_list() -> None:
    engine = ResearchEngine(
        provider=FakeProvider(response={}),
        parser=FakeParser(documents=[]),
    )

    result = engine.search("Atlas")

    assert result == []