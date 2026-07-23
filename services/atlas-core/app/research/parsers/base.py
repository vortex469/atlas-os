from __future__ import annotations

from abc import ABC, abstractmethod

from app.research.models import ResearchDocument


class ResearchParser(ABC):
    @abstractmethod
    def parse(
        self,
        response: dict,
    ) -> list[ResearchDocument]:
        ...