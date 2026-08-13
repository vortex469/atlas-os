from app.intelligence.findings import Severity
from app.intelligence.proxmox_rules import evaluate_proxmox


def test_unexpected_stopped_guest() -> None:
    findings = evaluate_proxmox(
        status={
            "status": "online",
            "node": "vorex469",
            "cpu_percent": 12.5,
            "memory": {
                "used_gib": 14.0,
                "total_gib": 32.0,
                "percent": 43.75,
            },
            "uptime_seconds": 86400,
            "load_average": ["0.20", "0.25", "0.30"],
        },
        guests={
            "node": "vorex469",
            "running": 1,
            "stopped": 1,
            "guests": [
                {
                    "vmid": 100,
                    "name": "running-vm",
                    "type": "vm",
                    "status": "running",
                },
                {
                    "vmid": 101,
                    "name": "stopped-vm",
                    "type": "vm",
                    "status": "stopped",
                },
            ],
        },
        expected_guest_checker=lambda vmid, state: False,
        expected_guest_state_getter=lambda vmid: None,
    )

    assert len(findings) == 2

    stopped = next(
        finding
        for finding in findings
        if finding.id == "proxmox-guests-unexpected-stopped"
    )
    node_status = next(
        finding
        for finding in findings
        if finding.id == "proxmox-node-status"
    )

    assert stopped.severity == Severity.WARNING
    assert stopped.affects_health is True
    assert stopped.score_penalty == 5
    assert stopped.metric["unexpected_stopped"] == 1

    assert node_status.metric["cpu_percent"] == 12.5
    assert node_status.metric["running_guests"] == 1


def test_expected_stopped_guest_is_suppressed() -> None:
    findings = evaluate_proxmox(
        status={
            "status": "online",
            "node": "vorex469",
            "cpu_percent": 12.5,
            "memory": {
                "used_gib": 14.0,
                "total_gib": 32.0,
                "percent": 43.75,
            },
            "uptime_seconds": 86400,
            "load_average": ["0.20", "0.25", "0.30"],
        },
        guests={
            "node": "vorex469",
            "running": 1,
            "stopped": 1,
            "guests": [
                {
                    "vmid": 100,
                    "name": "running-vm",
                    "type": "vm",
                    "status": "running",
                },
                {
                    "vmid": 101,
                    "name": "expected-stopped-vm",
                    "type": "vm",
                    "status": "stopped",
                },
            ],
        },
        expected_guest_checker=lambda vmid, state: (
            vmid == 101 and state == "stopped"
        ),
        expected_guest_state_getter=lambda vmid: None,
    )

    assert len(findings) == 1
    assert findings[0].id == "proxmox-node-status"


def test_ignored_guest_is_suppressed() -> None:
    findings = evaluate_proxmox(
        status={
            "status": "online",
            "node": "vorex469",
            "cpu_percent": 12.5,
            "memory": {
                "used_gib": 14.0,
                "total_gib": 32.0,
                "percent": 43.75,
            },
        },
        guests={
            "node": "vorex469",
            "running": 1,
            "stopped": 1,
            "guests": [
                {
                    "vmid": 109,
                    "name": "kenny",
                    "type": "lxc",
                    "status": "stopped",
                },
            ],
        },
        expected_guest_checker=lambda vmid, state: False,
        expected_guest_state_getter=lambda vmid: "ignored"
        if vmid == 109
        else None,
    )

    assert len(findings) == 1
    assert findings[0].id == "proxmox-node-status"


def test_critical_memory() -> None:
    findings = evaluate_proxmox(
        status={
            "node": "vorex469",
            "cpu_percent": 20,
            "memory": {
                "used_gib": 31,
                "total_gib": 32,
                "percent": 96.88,
            },
        },
        guests={
            "running": 3,
            "stopped": 0,
            "guests": [],
        },
        expected_guest_checker=lambda vmid, state: False,
        expected_guest_state_getter=lambda vmid: None,
    )

    critical = next(
        finding
        for finding in findings
        if finding.id == "proxmox-memory-critical"
    )

    assert critical.severity == Severity.CRITICAL
    assert critical.score_penalty == 20
    assert critical.metric["memory_percent"] == 96.88


if __name__ == "__main__":
    test_unexpected_stopped_guest()
    test_expected_stopped_guest_is_suppressed()
    test_critical_memory()
    print("Proxmox intelligence rules tests passed")
