from app.intelligence.findings import Finding, Severity
from app.provider_intents.authority import ProxmoxMonitoringIntentSnapshot
from app.provider_intents.resolver import (
    ProviderIntentResolutionSet,
    ProviderIntentResolutionStatus,
)

CPU_WARNING_PERCENT = 85
CPU_CRITICAL_PERCENT = 95

MEMORY_WARNING_PERCENT = 85
MEMORY_CRITICAL_PERCENT = 95


def evaluate_proxmox(
    status: dict,
    guests: dict,
    expected_guest_checker=None,
    expected_guest_state_getter=None,
    intent_resolution: ProviderIntentResolutionSet | None = None,
    monitoring_intent: ProxmoxMonitoringIntentSnapshot | None = None,
) -> list[Finding]:
    findings: list[Finding] = []

    if monitoring_intent is not None:
        intent_resolution = monitoring_intent.provider_intent_resolution
        legacy_expectations = dict(monitoring_intent.legacy_expectations)
        expected_guest_state_getter = lambda vmid: legacy_expectations.get(str(vmid))
        expected_guest_checker = (
            lambda vmid, state: legacy_expectations.get(str(vmid)) == state
        )

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

    if intent_resolution is not None and not intent_resolution.authority_available:
        findings.append(
            Finding(
                id="proxmox-provider-intent-authority-unavailable",
                severity=Severity.CRITICAL,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Proxmox monitoring intent authority unavailable",
                message="Atlas cannot validate Proxmox monitoring expectations.",
                recommendation="Restore the configured Provider Intent authority.",
                score_penalty=20,
            )
        )

    resolved = {
        (item.resource_type, item.resource_id): item
        for item in (intent_resolution.resources if intent_resolution else ())
    }
    unexpected_stopped = []

    for guest in guest_items:
        if guest.get("status") == "running":
            continue

        vmid = guest.get("vmid")

        if intent_resolution is not None:
            item = resolved.get((str(guest.get("type", "unknown")), str(vmid)))
            if item is None or item.status is not ProviderIntentResolutionStatus.CONFIGURED:
                continue
            expected_state = item.expectation.value if item.expectation else None
            if expected_state in {"ignored", "stopped"}:
                continue
        else:
            expected_state = (
                expected_guest_state_getter(vmid)
                if expected_guest_state_getter is not None
                else None
            )
            if expected_state in {"ignored", "stopped"}:
                continue
            if expected_guest_checker is not None and expected_guest_checker(
                vmid, "stopped"
            ):
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

    missing_running = [
        item
        for item in (intent_resolution.resources if intent_resolution else ())
        if item.status is ProviderIntentResolutionStatus.MISSING
        and item.expectation is not None
        and item.expectation.value == "running"
    ]
    if missing_running:
        findings.append(
            Finding(
                id="proxmox-configured-qemu-missing",
                severity=Severity.WARNING,
                category="infrastructure",
                source="proxmox",
                component="Proxmox",
                title="Configured Proxmox QEMU missing",
                message=f"{len(missing_running)} configured QEMU resource(s) are missing.",
                recommendation="Review provider discovery and the configured resources.",
                metric={"missing_configured_qemu": len(missing_running)},
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
