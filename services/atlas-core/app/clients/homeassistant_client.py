import os

import httpx

from app.config.settings import settings


def get_headers() -> dict[str, str]:
    token = os.environ["HASS_TOKEN"]

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_api_status() -> dict:
    url = f"{settings.home_assistant.url.rstrip('/')}/api/"

    response = httpx.get(
        url,
        headers=get_headers(),
        timeout=10.0,
    )
    response.raise_for_status()

    return response.json()


def get_states() -> list[dict]:
    url = f"{settings.home_assistant.url.rstrip('/')}/api/states"

    response = httpx.get(
        url,
        headers=get_headers(),
        timeout=15.0,
    )
    response.raise_for_status()

    return response.json()
