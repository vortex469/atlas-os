from __future__ import annotations

import httpx

from app.context import AtlasContext
from app.providers.context_helpers import secret_value, timeout_from_context
from app.services.atlas_contexts import LegacyAtlasContextResolver


def get_headers(atlas_context: AtlasContext | None = None) -> dict[str, str]:
    token = _required_token(_homeassistant_context(atlas_context))

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_api_status(atlas_context: AtlasContext | None = None) -> dict:
    context = _homeassistant_context(atlas_context)
    response = httpx.get(
        _url(context, "/api/"),
        headers=get_headers(context),
        timeout=timeout_from_context(context),
        verify=_verify_tls(context),
    )
    response.raise_for_status()

    return response.json()


def get_states(atlas_context: AtlasContext | None = None) -> list[dict]:
    context = _homeassistant_context(atlas_context)
    response = httpx.get(
        _url(context, "/api/states"),
        headers=get_headers(context),
        timeout=timeout_from_context(context, 15.0),
        verify=_verify_tls(context),
    )
    response.raise_for_status()

    return response.json()


def _homeassistant_context(
    atlas_context: AtlasContext | None,
) -> AtlasContext:
    # Temporary compatibility seam for legacy routes and direct service tests.
    # The migrated loader/provider path passes AtlasContext explicitly.
    return atlas_context or LegacyAtlasContextResolver().resolve_context(
        "home_assistant",
    )


def _required_token(atlas_context: AtlasContext) -> str:
    token = secret_value(atlas_context, "token")
    if not token:
        raise RuntimeError("Home Assistant token is not configured.")
    return token


def _url(atlas_context: AtlasContext, path: str) -> str:
    connection = atlas_context.connection
    if connection is None or not connection.base_url:
        raise RuntimeError("Home Assistant URL is not configured.")
    return f"{connection.base_url.rstrip('/')}/{path.lstrip('/')}"


def _verify_tls(atlas_context: AtlasContext) -> bool | str:
    connection = atlas_context.connection
    if connection is None:
        return True
    if connection.ca_bundle:
        return connection.ca_bundle
    return connection.verify_tls
