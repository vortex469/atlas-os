from __future__ import annotations

from abc import ABC, abstractmethod

from app.research.models import ResearchDocument


class ResearchProvider(ABC):
    """
    Base class for all research providers.
    """

    @abstractmethod
    def search(
        self,
        query: str,
    ) -> list[ResearchDocument]:
        """
        Execute a research query.
        """
        raise NotImplementedError