import time
from concurrent.futures import ThreadPoolExecutor
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


HEALTH_CHECK_WORKERS = 4


def _service_health(item: tuple[str, dict]) -> tuple[str, dict] | None:
    service_id, service = item
    url = build_service_url(service)
    if url is None:
        return None

    result = check_service(
        url=url,
        expected_statuses=service.get("expected_status", [200]),
        critical=service.get("critical", False),
    )
    status = result["status"]
    return service.get("name", service_id), {
        "provider_id": service_id.replace("_", "-"),
        "status": status,
        "latency_ms": result.get("latency_ms"),
        "http_status": result.get("http_status"),
        "message": (
            None if status == "online"
            else result.get("error", "Service returned an unexpected status.")
        ),
        "details": {
            "url": result.get("url"),
            "critical": result.get("critical", False),
        },
    }


def get_health() -> dict:
    inventory = load_inventory()
    results = {}
    # Bound each request's fan-out and retain inventory order, even when probes
    # finish out of order. Each probe keeps the existing HTTP timeout and rules.
    with ThreadPoolExecutor(max_workers=HEALTH_CHECK_WORKERS) as probes:
        for observation in probes.map(
            _service_health, inventory.get("services", {}).items()
        ):
            if observation is not None:
                name, result = observation
                results[name] = result
    return results
