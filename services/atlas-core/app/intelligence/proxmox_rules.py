from app.intelligence.findings import Finding, Severity
from app.config.policies import is_expected_guest

CPU_WARNING_PERCENT = 85
CPU_CRITICAL_PERCENT = 95

MEMORY_WARNING_PERCENT = 85
MEMORY_CRITICAL_PERCENT = 95


def evaluate_proxmox(
    status: dict,
    guests: dict,
    expected_guest_checker=is_expected_guest,
) -> list[Finding]:
    findings: list[Finding] = []

    node = status.get("node", "unknown")
    cpu_percent = float(status.get("cpu_percent", 0))

    memory = status.get("memory", {})
    memory_percent = float(memory.get("percent", 0))
    memory_used_gib = float(memory.get("used_gib", 0))
    memory_total_gib = float(memory.get("total_gib", 0))

    running_guests = int(guests.get("running", 0))
    stopped_guests = int(guests.get("stopped", 0))
    guest_items = guests.get("guests", [])

    if cpu_percent >= CPU_CRITICAL_PERCENT:
        findings.append(
            Finding(
                id="proxmox-cpu-critical",
                severity=Severity.CRITICAL,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Proxmox CPU usage critical",
                message=(
                    f"Node {node} CPU usage is "
                    f"{cpu_percent:.2f}%."
                ),
                recommendation=(
                    "Identify high-CPU guests or processes and reduce "
                    "the workload immediately."
                ),
                metric={
                    "cpu_percent": cpu_percent,
                    "threshold_percent": CPU_CRITICAL_PERCENT,
                },
                details={
                    "node": node,
                },
                score_penalty=20,
            )
        )
    elif cpu_percent >= CPU_WARNING_PERCENT:
        findings.append(
            Finding(
                id="proxmox-cpu-warning",
                severity=Severity.WARNING,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Proxmox CPU usage high",
                message=(
                    f"Node {node} CPU usage is "
                    f"{cpu_percent:.2f}%."
                ),
                recommendation=(
                    "Review guest and host CPU usage for sustained load."
                ),
                metric={
                    "cpu_percent": cpu_percent,
                    "threshold_percent": CPU_WARNING_PERCENT,
                },
                details={
                    "node": node,
                },
                score_penalty=10,
            )
        )

    if memory_percent >= MEMORY_CRITICAL_PERCENT:
        findings.append(
            Finding(
                id="proxmox-memory-critical",
                severity=Severity.CRITICAL,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Proxmox memory usage critical",
                message=(
                    f"Node {node} memory usage is "
                    f"{memory_percent:.2f}%."
                ),
                recommendation=(
                    "Reduce memory usage, stop nonessential workloads, "
                    "or increase host memory."
                ),
                metric={
                    "memory_percent": memory_percent,
                    "memory_used_gib": memory_used_gib,
                    "memory_total_gib": memory_total_gib,
                    "threshold_percent": MEMORY_CRITICAL_PERCENT,
                },
                details={
                    "node": node,
                },
                score_penalty=20,
            )
        )
    elif memory_percent >= MEMORY_WARNING_PERCENT:
        findings.append(
            Finding(
                id="proxmox-memory-warning",
                severity=Severity.WARNING,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Proxmox memory usage high",
                message=(
                    f"Node {node} memory usage is "
                    f"{memory_percent:.2f}%."
                ),
                recommendation=(
                    "Review guest memory allocations and watch for "
                    "continued growth."
                ),
                metric={
                    "memory_percent": memory_percent,
                    "memory_used_gib": memory_used_gib,
                    "memory_total_gib": memory_total_gib,
                    "threshold_percent": MEMORY_WARNING_PERCENT,
                },
                details={
                    "node": node,
                },
                score_penalty=10,
            )
        )

    unexpected_stopped = []

    for guest in guest_items:
        if guest.get("status") == "running":
            continue

        vmid = guest.get("vmid")

        if expected_guest_checker(vmid, "stopped"):
            continue

        unexpected_stopped.append(
            {
                "vmid": vmid,
                "name": guest.get("name"),
                "type": guest.get("type"),
                "status": guest.get("status"),
            }
        )

    if unexpected_stopped:
        findings.append(
            Finding(
                id="proxmox-guests-unexpected-stopped",
                severity=Severity.WARNING,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Unexpected Proxmox guests stopped",
                message=(
                    f"{len(unexpected_stopped)} guest(s) are stopped "
                    "unexpectedly."
                ),
                recommendation=(
                    "Review guests that are stopped but expected to be running."
                ),
                metric={
                    "unexpected_stopped": len(unexpected_stopped),
                    "running_guests": running_guests,
                },
                details={
                    "node": node,
                    "guests": unexpected_stopped,
                },
                score_penalty=5,
            )
        )

    findings.append(
        Finding(
            id="proxmox-node-status",
            severity=Severity.INFO,
            category="infrastructure",
            source="proxmox",
            component="Proxmox",
            title="Proxmox node online",
            message=(
                f"Node {node} is online with {running_guests} "
                "running guest(s)."
            ),
            metric={
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_used_gib": memory_used_gib,
                "memory_total_gib": memory_total_gib,
                "running_guests": running_guests,
                "stopped_guests": stopped_guests,
            },
            details={
                "node": node,
                "uptime_seconds": status.get("uptime_seconds", 0),
                "load_average": status.get("load_average", []),
            },
            affects_health=False,
            score_penalty=0,
        )
    )

    return findings
