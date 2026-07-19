from fastapi import APIRouter, HTTPException

from app.providers.registry import (
    ProviderNotFoundError,
    provider_registry,
)
from app.providers.serializer import serialize_provider

router = APIRouter()


@router.get("/providers")
async def providers():
    return [
        await serialize_provider(provider)
        for provider in provider_registry.all()
    ]


@router.get("/providers/{provider_id}")
async def provider_detail(provider_id: str):
    try:
        provider = provider_registry.get(provider_id)
    except ProviderNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider_id}'.",
        ) from error

    return await serialize_provider(provider)