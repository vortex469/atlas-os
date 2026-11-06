from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

import httpx
import pytest

from app.services import health_service as health


def inventory(count):
    return {
        "services": {
            f"service_{index}": {"host": "example.invalid", "port": 8000 + index}
            for index in range(count)
        }
    }


def online(url, expected_statuses, critical):
    return {
        "url": url,
        "status": "online",
        "latency_ms": 1,
        "http_status": 200,
        "critical": critical,
    }


def test_health_checks_overlap_without_network(monkeypatch):
    monkeypatch.setattr(health, "load_inventory", lambda: inventory(4))
    together = Barrier(4)

    def probe(**kwargs):
        together.wait(timeout=5)
        return online(**kwargs)

    monkeypatch.setattr(health, "check_service", probe)
    result = health.get_health()
    assert list(result) == [f"service_{index}" for index in range(4)]
    assert all(item["status"] == "online" for item in result.values())


def test_health_fanout_is_bounded_and_all_services_are_reported(monkeypatch):
    monkeypatch.setattr(health, "load_inventory", lambda: inventory(10))
    full = Event()
    release = Event()
    lock = Lock()
    active = peak = started = 0

    def probe(**kwargs):
        nonlocal active, peak, started
        with lock:
            active += 1
            started += 1
            peak = max(peak, active)
            if active == 4:
                full.set()
        try:
            assert release.wait(timeout=5)
            return online(**kwargs)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(health, "check_service", probe)
    with ThreadPoolExecutor(max_workers=1) as caller:
        pending = caller.submit(health.get_health)
        try:
            assert full.wait(timeout=5)
            with lock:
                assert started == 4
                assert peak == 4
        finally:
            release.set()
        result = pending.result(timeout=5)
    assert len(result) == 10
    assert started == 10
    assert peak <= 4
    assert active == 0


def test_health_preserves_mapping_and_skips_unaddressable_services(monkeypatch):
    monkeypatch.setattr(
        health,
        "load_inventory",
        lambda: {
            "services": {
                "first_service": {
                    "host": "example.invalid",
                    "port": 8000,
                    "name": "First",
                    "critical": True,
                    "expected_status": [204],
                },
                "missing_host": {"port": 8001},
                "last_service": {"host": "example.invalid", "port": 8002},
            }
        },
    )
    calls = []

    def probe(**kwargs):
        calls.append(kwargs)
        return {
            "status": "offline",
            "url": kwargs["url"],
            "critical": kwargs["critical"],
            "error": "Timed out",
        }

    monkeypatch.setattr(health, "check_service", probe)
    result = health.get_health()
    assert list(result) == ["First", "last_service"]
    assert result["First"] == {
        "provider_id": "first-service",
        "status": "offline",
        "latency_ms": None,
        "http_status": None,
        "message": "Timed out",
        "details": {"url": "http://example.invalid:8000/", "critical": True},
    }
    assert len(calls) == 2
    assert any(
        call["expected_statuses"] == [204] and call["critical"] is True
        for call in calls
    )
    assert result["last_service"]["details"]["critical"] is False


def test_duplicate_display_names_keep_the_last_inventory_entry(monkeypatch):
    services = inventory(2)
    for service in services["services"].values():
        service["name"] = "Shared name"
    monkeypatch.setattr(health, "load_inventory", lambda: services)
    monkeypatch.setattr(health, "check_service", online)
    assert health.get_health()["Shared name"]["provider_id"] == "service-1"


def test_empty_inventory_does_not_probe(monkeypatch):
    monkeypatch.setattr(health, "load_inventory", dict)
    monkeypatch.setattr(
        health, "check_service", lambda **_: pytest.fail("No probe expected")
    )
    assert health.get_health() == {}


def test_probe_keeps_existing_timeout_and_offline_result(monkeypatch):
    def unavailable(url, **kwargs):
        assert kwargs == {"timeout": 3.0, "follow_redirects": True}
        raise httpx.ConnectTimeout("Timed out")

    monkeypatch.setattr(health.httpx, "get", unavailable)
    assert health.check_service("http://example.invalid/", [200], True) == {
        "status": "offline",
        "critical": True,
        "url": "http://example.invalid/",
        "error": "Timed out",
    }
