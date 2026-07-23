from __future__ import annotations

from app.research.models import ResearchDocument
from app.research.parsers.base import ResearchParser


class ExaParser(ResearchParser):

    def parse(
        self,
        response: dict,
    ) -> list[ResearchDocument]:

        content = response.get("content", [])

        if not content:
            return []

        print(content[0]["text"])

        return []