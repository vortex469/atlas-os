import pytest

from app import doctor
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
    assert (
        report.checks[0].error
        == "Check unavailable. Review its configuration and access, then run Doctor again."
    )
    assert report.critical == [
        "Docker: Check unavailable. Review its configuration and access, then run Doctor again."
    ]


_PRIVATE_EXCEPTION = "Authorization: Bearer doctor-private-test-canary; https://example.invalid/?token=doctor-private-test-canary"


@pytest.mark.parametrize("source", ("configuration", "infrastructure"))
def test_doctor_does_not_publish_exception_contents(source: str) -> None:
    def unavailable() -> None:
        raise RuntimeError(_PRIVATE_EXCEPTION)

    report = run_diagnostics(
        configuration_check=unavailable
        if source == "configuration"
        else valid_configuration,
        infrastructure_checks=(("Docker", unavailable),)
        if source == "infrastructure"
        else (),
    )
    assert "doctor-private-test-canary" not in report.model_dump_json()
    assert "example.invalid" not in report.model_dump_json()
    assert report.status == "critical"
    assert report.score == (60 if source == "configuration" else 80)
    assert report.configuration_ok is (source != "configuration")
    if source == "infrastructure":
        assert report.checks[0].name == "Docker"
        assert report.checks[0].passed is False
        assert (
            report.checks[0].error
            == "Check unavailable. Review its configuration and access, then run Doctor again."
        )
    else:
        assert report.checks == []
        assert report.critical == [
            "Configuration validation failed. Review Atlas configuration and inventory, required credentials, and Docker access."
        ]


def test_doctor_does_not_stringify_failed_checks() -> None:
    class UnprintableError(RuntimeError):
        def __str__(self) -> str:
            raise AssertionError("Exception formatting must not be called")

    def unavailable() -> None:
        raise UnprintableError()

    report = run_diagnostics(
        configuration_check=unavailable,
        infrastructure_checks=(("Docker", unavailable),),
    )
    assert report.status == "critical"
    assert report.score == 40
    assert report.configuration_ok is False
    assert report.checks[0].passed is False
    assert len(report.critical) == 2


def test_doctor_redacts_offline_docker_payload_without_mutating_it() -> None:
    payload = {"status": "offline", "error": _PRIVATE_EXCEPTION}
    report = run_diagnostics(
        configuration_check=valid_configuration,
        infrastructure_checks=(("Docker", lambda: payload),),
    )
    assert "doctor-private-test-canary" not in report.model_dump_json()
    assert "example.invalid" not in report.model_dump_json()
    assert payload["error"] == _PRIVATE_EXCEPTION
    assert report.status == "critical"
    assert report.score == 85
    # Collection returned; the existing finding still owns the health decision.
    assert report.checks[0].passed is True
    assert report.critical == [
        "ACE could not collect Docker status: Docker status is unavailable. Review Docker connection settings and access."
    ]


def test_doctor_cli_uses_the_same_controlled_report(monkeypatch, capsys) -> None:
    def unavailable() -> None:
        raise RuntimeError(_PRIVATE_EXCEPTION)

    report = run_diagnostics(
        configuration_check=valid_configuration,
        infrastructure_checks=(("Docker", unavailable),),
    )
    monkeypatch.setattr(doctor, "run_diagnostics", lambda: report)
    assert doctor.main() == 2
    output = capsys.readouterr().out
    assert "doctor-private-test-canary" not in output
    assert "example.invalid" not in output
    assert "Check unavailable" in output
    assert "Score: 80/100" in output
    assert "Status: CRITICAL" in output
