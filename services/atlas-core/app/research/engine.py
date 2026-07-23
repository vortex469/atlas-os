from __future__ import annotations

from app.research.models import ResearchDocument
from app.research.parsers.base import ResearchParser
from app.research.providers.base import ResearchProvider


class ResearchEngine:
    """Coordinate a research provider and parser."""

    def __init__(
        self,
        provider: ResearchProvider,
        parser: ResearchParser,
    ) -> None:
        self.provider = provider
        self.parser = parser

    def search(
        self,
        query: str,
    ) -> list[ResearchDocument]:
        response = self.provider.search(query)
        documents = self.parser.parse(response)

        return self._deduplicate(documents)

    def _deduplicate(
        self,
        documents: list[ResearchDocument],
    ) -> list[ResearchDocument]:
        unique_documents: list[ResearchDocument] = []
        seen_urls: set[str] = set()

        for document in documents:
            normalized_url = self._normalize_url(document.url)

            if normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)
            unique_documents.append(document)

        return unique_documents

    def _normalize_url(
        self,
        url: str,
    ) -> str:
        return url.strip().rstrip("/").lower()
