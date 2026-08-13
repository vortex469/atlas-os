from __future__ import annotations

from proxmoxer import ProxmoxAPI

from app.context import AtlasContext
from app.services.atlas_contexts import LegacyAtlasContextResolver


def create_proxmox_client(
    *,
    host: str,
    user: str,
    token_name: str,
    token_value: str,
    port: int = 8006,
    verify_ssl: bool = False,
) -> ProxmoxAPI:
    return ProxmoxAPI(
        host,
        user=user,
        token_name=token_name,
        token_value=token_value,
        port=port,
        verify_ssl=verify_ssl,
    )


def get_proxmox_client(
    atlas_context: AtlasContext | None = None,
) -> ProxmoxAPI:
    """Build a Proxmox client from AtlasContext.

    The optional resolver fallback is a temporary compatibility seam for
    legacy routes and tests that still call the service layer directly.
    The client itself does not read global settings or environment variables.
    """

    context = atlas_context or LegacyAtlasContextResolver().resolve_context(
        "proxmox",
    )
    connection = context.connection
    if connection is None or not connection.host:
        raise RuntimeError("Proxmox connection host is not configured.")

    user = _required_secret(context, "user")
    token_name = _required_secret(context, "token_name")
    token_value = _required_secret(context, "token_value")

    return create_proxmox_client(
        host=connection.host,
        user=user,
        token_name=token_name,
        token_value=token_value,
        port=connection.port or 8006,
        verify_ssl=connection.verify_tls,
    )


def _required_secret(context: AtlasContext, name: str) -> str:
    secret = context.secrets.get(name)
    value = secret.reveal() if secret is not None else None
    if not value:
        raise RuntimeError(f"Proxmox secret '{name}' is not configured.")
    return value
