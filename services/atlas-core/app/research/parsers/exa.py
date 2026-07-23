from __future__ import annotations

from typing import Any

from app.research.models import ResearchDocument
from app.research.parsers.base import ResearchParser


class ExaParser(ResearchParser):
    """Convert Exa MCP search responses into ResearchDocument objects."""

    RESULT_SEPARATOR = "\n---\n"

    def parse(
        self,
        response: dict[str, Any],
    ) -> list[ResearchDocument]:
        text = self._extract_text(response)

        if not text:
            return []

        search_time = self._extract_search_time(response)
        documents: list[ResearchDocument] = []

        for block in text.split(self.RESULT_SEPARATOR):
            document = self._parse_block(
                block=block.strip(),
                search_time=search_time,
            )

            if document is not None:
                documents.append(document)

        return documents

    def _extract_text(
        self,
        response: dict[str, Any],
    ) -> str:
        content = response.get("content", [])

        for item in content:
            if item.get("type") == "text":
                return str(item.get("text", "")).strip()

        return ""

    def _extract_search_time(
        self,
        response: dict[str, Any],
    ) -> float | None:
        content = response.get("content", [])

        for item in content:
            metadata = item.get("_meta", {})
            search_time = metadata.get("searchTime")

            if isinstance(search_time, int | float):
                return float(search_time)

        return None

    def _parse_block(
        self,
        block: str,
        search_time: float | None,
    ) -> ResearchDocument | None:
        if not block:
            return None

        lines = block.splitlines()

        title = self._field_value(lines, "Title:")
        url = self._field_value(lines, "URL:")
        published = self._optional_field_value(lines, "Published:")
        author = self._optional_field_value(lines, "Author:")
        content = self._extract_highlights(lines)

        if not url:
            return None

        metadata: dict[str, Any] = {}

        if search_time is not None:
            metadata["search_time_seconds"] = search_time

        return ResearchDocument(
            title=title or url,
            url=url,
            source="exa",
            provider="mcp",
            content=content,
            published=published,
            author=author,
            metadata=metadata,
        )

    def _field_value(
        self,
        lines: list[str],
        prefix: str,
    ) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip()

        return ""

    def _optional_field_value(
        self,
        lines: list[str],
        prefix: str,
    ) -> str | None:
        value = self._field_value(lines, prefix)

        if not value or value == "N/A":
            return None

        return value

    def _extract_highlights(
        self,
        lines: list[str],
    ) -> str:
        try:
            start = lines.index("Highlights:") + 1
        except ValueError:
            return ""

        return "\n".join(lines[start:]).strip()