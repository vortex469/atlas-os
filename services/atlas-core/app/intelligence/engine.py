from collections import Counter

from app.intelligence.findings import Finding, Severity


class IntelligenceEngine:
    def __init__(self) -> None:
        self._findings: list[Finding] = []

    def add(self, finding: Finding) -> None:
        self._findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self._findings.extend(findings)

    def findings(self) -> list[Finding]:
        return list(self._findings)

    def calculate_score(self) -> int:
        penalty = sum(
            finding.score_penalty
            for finding in self._findings
            if finding.affects_health
        )
        return max(0, 100 - penalty)

    def status(self) -> str:
        if any(
            finding.severity == Severity.CRITICAL
            and finding.affects_health
            for finding in self._findings
        ):
            return "critical"

        if any(
            finding.severity == Severity.WARNING
            and finding.affects_health
            for finding in self._findings
        ):
            return "degraded"

        return "healthy"

    def summary(self) -> dict:
        counts = Counter(
            finding.severity.value
            for finding in self._findings
        )

        return {
            "score": self.calculate_score(),
            "status": self.status(),
            "counts": {
                "critical": counts.get("critical", 0),
                "warning": counts.get("warning", 0),
                "info": counts.get("info", 0),
            },
            "findings": [
                finding.model_dump(mode="json")
                for finding in self._findings
            ],
        }
