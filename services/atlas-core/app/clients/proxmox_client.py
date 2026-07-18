import os

from proxmoxer import ProxmoxAPI

from app.config.settings import settings


def get_proxmox_client() -> ProxmoxAPI:
    return ProxmoxAPI(
        settings.proxmox.host,
        user=os.environ["PROXMOX_USER"],
        token_name=os.environ["PROXMOX_TOKEN_NAME"],
        token_value=os.environ["PROXMOX_TOKEN_VALUE"],
        port=settings.proxmox.port,
        verify_ssl=settings.proxmox.verify_ssl,
    )
