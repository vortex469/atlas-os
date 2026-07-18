import os

from dotenv import load_dotenv
from proxmoxer import ProxmoxAPI

load_dotenv("/opt/atlas/.env")


def get_client():
    return ProxmoxAPI(
        host=os.getenv("PROXMOX_HOST"),
        user=os.getenv("PROXMOX_USER"),
        token_name=os.getenv("PROXMOX_TOKEN_NAME"),
        token_value=os.getenv("PROXMOX_TOKEN_SECRET"),
        verify_ssl=False,
    )
