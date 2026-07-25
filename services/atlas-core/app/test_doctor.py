from app.doctor import run_diagnostics


def valid_configuration() -> None:
    return None


def test_doctor_reports_healthy_checks() -> None:
    report = run_diagnostics(
        configuration_check=valid_configuration,
        infrastructure_checks=(
            (
                "Service inventory",
                lambda: {
                    "atlas-core": {
                        "status": "online",
                        "critical": True,
                    },
                },
            ),
        ),
    )

    assert report.status == "healthy"
    assert report.score == 100
    assert report.configuration_ok is True
    assert report.checks[0].passed is True


def test_doctor_classifies_service_warning() -> None:
    report = run_diagnostics(
        configuration_check=valid_configuration,
        infrastructure_checks=(
            (
                "Service inventory",
                lambda: {
                    "optional-service": {
                        "status": "offline",
                        "critical": False,
                    },
                },
            ),
        ),
    )

    assert report.status == "degraded"
    assert report.score == 95
    assert report.warnings == ["optional-service: offline"]


def test_doctor_classifies_check_failure() -> None:
    def failed_check() -> None:
        raise RuntimeError("Connection refused")

    report = run_diagnostics(
        configuration_check=valid_configuration,
        infrastructure_checks=(("Docker", failed_check),),
    )

    assert report.status == "critical"
    assert report.score == 80
    assert report.checks[0].error == "Connection refused"
    assert report.critical == ["Docker: Connection refused"]
