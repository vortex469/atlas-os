import time
from urllib.parse import urljoin

import httpx

from app.config.inventory import load_inventory


def check_service(
    url: str,
    expected_statuses: list[int],
    critical: bool,
) -> dict:
    started = time.perf_counter()

    try:
        response = httpx.get(
            url,
            timeout=3.0,
            follow_redirects=True,
        )

        latency_ms = round((time.perf_counter() - started) * 1000)

        status = (
            "online"
            if response.status_code in expected_statuses
            else "degraded"
        )

        return {
            "status": status,
            "critical": critical,
            "url": url,
            "latency_ms": latency_ms,
            "http_status": response.status_code,
        }

    except httpx.RequestError as error:
        return {
            "status": "offline",
            "critical": critical,
            "url": url,
            "error": str(error),
        }


def build_service_url(service: dict) -> str | None:
    host = service.get("host")
    port = service.get("port")

    if not host or not port:
        return None

    protocol = service.get("protocol", "http")
    endpoint = service.get("health_endpoint", "/")

    base_url = f"{protocol}://{host}:{port}/"

    return urljoin(base_url, endpoint.lstrip("/"))


def get_health() -> dict:
    inventory = load_inventory()
    results = {}

    for service_id, service in inventory.get("services", {}).items():
        url = build_service_url(service)

        if url is None:
            continue

        display_name = service.get("name", service_id)
        critical = service.get("critical", False)
        expected_statuses = service.get("expected_status", [200])

        results[display_name] = check_service(
            url=url,
            expected_statuses=expected_statuses,
            critical=critical,
        )

    return results