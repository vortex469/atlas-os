from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import policies as policy_config
from app.config.resource_policies import update_proxmox_guest_expectation
from app.context import MetadataContext, RuntimeContext


class ProxmoxRuntimeIntentService:
    """Runtime-backed Proxmox intent access hidden behind AtlasContext."""

    def list_guest_expectations(self) -> dict[str, Any]:
        return dict(policy_config.load_policies().proxmox.guests)

    def update_guest_expectation(
        self,
        resource_id: str,
        expectation: str,
    ) -> str:
        return update_proxmox_guest_expectation(resource_id, expectation)


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


def _intent_service_for(consumer_id: str) -> ProxmoxRuntimeIntentService | None:
    if consumer_id == "proxmox":
        return ProxmoxRuntimeIntentService()
    return None
