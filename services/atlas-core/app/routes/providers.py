from fastapi import APIRouter, HTTPException

from app.providers import Provider, ProviderNotFoundError
from app.providers.registry import provider_registry
from app.providers.serializer import (
    serialize_action,
    serialize_provider,
)

router = APIRouter(prefix="/providers", tags=["providers"])


def get_registered_provider(provider_id: str) -> Provider:
    """Resolve a provider or return a consistent HTTP 404 response."""

    try:
        return provider_registry.get(provider_id)
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error


@router.get("")
async def list_providers():
    return [
        await serialize_provider(provider)
        for provider in provider_registry.all()
    ]


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    provider = get_registered_provider(provider_id)

    return await serialize_provider(provider)


@router.get("/{provider_id}/actions")
async def list_provider_actions(provider_id: str):
    provider = get_registered_provider(provider_id)
    actions = await provider.get_actions()

    return [
        serialize_action(action)
        for action in actions
    ]
