from __future__ import annotations

from pathlib import Path

from app.context import MetadataContext, RuntimeContext


class RuntimeContextResolver:
    """Resolve immutable runtime paths without creating or mutating them."""

    def __init__(self, data_root: Path | str = Path("/opt/atlas/data")) -> None:
        self._data_root = Path(data_root)

    def resolve_runtime(self, metadata: MetadataContext) -> RuntimeContext:
        provider_root = self._data_root / "providers" / metadata.consumer_id
        return RuntimeContext(
            data_root=self._data_root,
            config_root=self._data_root / "config",
            history_root=self._data_root / "history",
            cache_root=self._data_root / "cache",
            knowledge_root=self._data_root / "knowledge",
            consumer_data_root=provider_root,
            consumer_cache_root=self._data_root / "cache" / "providers" / metadata.consumer_id,
            metadata={
                "consumer_id": metadata.consumer_id,
                "consumer_type": metadata.consumer_type,
            },
        )
