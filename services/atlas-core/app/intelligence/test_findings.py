from app.intelligence.findings import Finding, Severity


def test_finding_model() -> None:
    finding = Finding(
        id="proxmox-offline",
        severity=Severity.CRITICAL,
        category="infrastructure",
        source="proxmox",
        title="Proxmox unavailable",
        message="Atlas could not connect to the Proxmox API.",
        recommendation="Check the Proxmox host and API credentials.",
        score_penalty=25,
    )

    assert finding.severity == Severity.CRITICAL
    assert finding.affects_health is True
    assert finding.score_penalty == 25


if __name__ == "__main__":
    test_finding_model()
    print("Finding model test passed")
