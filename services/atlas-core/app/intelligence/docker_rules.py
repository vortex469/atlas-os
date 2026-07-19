from app.intelligence.findings import Finding, Severity


def evaluate_docker(status: dict) -> list[Finding]:
    findings: list[Finding] = []

    unhealthy = status.get("unhealthy", 0)
    stopped = status.get("stopped", 0)
    running = status.get("running", 0)

    if unhealthy > 0:
        findings.append(
            Finding(
                id="docker-unhealthy",
                severity=Severity.WARNING,
                category="docker",
                source="docker",
                title="Docker containers unhealthy",
                message=f"{unhealthy} Docker container(s) are unhealthy.",
                recommendation=(
                    "Inspect unhealthy containers and review their logs."
                ),
                score_penalty=10,
                details={
                    "unhealthy": unhealthy,
                },
            )
        )

    if stopped > 0:
        findings.append(
            Finding(
                id="docker-stopped",
                severity=Severity.INFO,
                category="docker",
                source="docker",
                title="Docker containers stopped",
                message=f"{stopped} Docker container(s) are stopped.",
                affects_health=False,
                score_penalty=0,
                details={
                    "stopped": stopped,
                },
            )
        )

    findings.append(
        Finding(
            id="docker-running",
            severity=Severity.INFO,
            category="docker",
            source="docker",
            title="Docker engine healthy",
            message=f"{running} Docker container(s) are running.",
            affects_health=False,
            score_penalty=0,
            details={
                "running": running,
            },
        )
    )

    return findings
