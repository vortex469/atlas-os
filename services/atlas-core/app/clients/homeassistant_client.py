import os

import httpx
from dotenv import load_dotenv


load_dotenv("/opt/atlas/.env")


def get_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['HASS_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_api_status() -> dict:
    url = f"{os.environ['HASS_URL'].rstrip('/')}/api/"

    response = httpx.get(
        url,
        headers=get_headers(),
        timeout=10.0,
    )
    response.raise_for_status()

    return response.json()


def get_states() -> list[dict]:
    url = f"{os.environ['HASS_URL'].rstrip('/')}/api/states"

    response = httpx.get(
        url,
        headers=get_headers(),
        timeout=15.0,
    )
    response.raise_for_status()

    return response.json()
