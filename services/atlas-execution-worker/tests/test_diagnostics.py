import subprocess

import pytest
from app.execution.worker_contracts import BoundedOutput
from atlas_execution_worker import diagnostics
from atlas_execution_worker.process import CapturedCommand


@pytest.mark.parametrize('returncode', [0, 1])
def test_helper_is_independent_and_does_not_echo_raw_output(monkeypatch, returncode):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return CapturedCommand(returncode, BoundedOutput('private output'), BoundedOutput('private detail'))
    monkeypatch.setattr(diagnostics, 'run_command', run)
    report = diagnostics.capability_report(shell_boundaries_passed=True, helper=diagnostics.helper_network_namespace())
    assert report['shell_boundaries'] == 'passed'
    assert report['helper_network_namespace_supported'] is (returncode == 0)
    assert report['activation_authorized'] is False
    assert 'private' not in str(report)
    assert calls[0][0][0] == 'bwrap'
    assert 'codex' not in calls[0][0]
    assert calls[0][1]['timeout'] == 5


def test_missing_helper_is_not_readiness(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError('private path')
    monkeypatch.setattr(diagnostics, 'run_command', fail)
    assert diagnostics.helper_network_namespace()['status'] == 'unavailable'


def test_helper_timeout_is_not_readiness(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired('bwrap', 5)
    monkeypatch.setattr(diagnostics, 'run_command', fail)
    report = diagnostics.capability_report(shell_boundaries_passed=False, helper=diagnostics.helper_network_namespace())
    assert report['helper_network_namespace_supported'] is False
    assert report['model_invocations'] == 0
