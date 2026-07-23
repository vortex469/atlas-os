from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class ResearchDocument:
    """
    Normalized research result returned by any provider.

    Every provider (MCP, Crawl4AI, GitHub, PDFs, etc.)
    should return this object.
    """

    title: str
    url: str
    source: str
    provider: str
    content: str

    published: str | None = None
    author: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )