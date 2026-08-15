from __future__ import annotations

from pathlib import Path

from app.context import MetadataContext, RuntimeContext
from app.provider_intents.authority import get_monitoring_intent_authority


class RuntimeContextResolver:
    """Resolve immutable runtime paths without creating or mutating them."""

    def __init__(self, data_root: Path | str = Path("/opt/atlas/data")) -> None:
        self._data_root = Path(data_root)

    def resolve_runtime(self, metadata: MetadataContext) -> RuntimeContext:
        provider_root = self._data_root / "providers" / metadata.consumer_id
        intent_service = _intent_service_for(metadata.consumer_id)
        return RuntimeContext(
            data_root=self._data_root,
            config_root=self._data_root / "config",
            history_root=self._data_root / "history",
            cache_root=self._data_root / "cache",
            knowledge_root=self._data_root / "knowledge",
            consumer_data_root=provider_root,
            consumer_cache_root=self._data_root
            / "cache"
            / "providers"
            / metadata.consumer_id,
            intent_reader=intent_service,
            intent_writer=intent_service,
            metadata={
                "consumer_id": metadata.consumer_id,
                "consumer_type": metadata.consumer_type,
            },
        )


def _intent_service_for(consumer_id: str):
    if consumer_id == "proxmox":
        return get_monitoring_intent_authority()
    return None
