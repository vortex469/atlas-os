"""Credential-free diagnostics; observations never grant execution authority."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .process import run_command


def helper_network_namespace() -> dict[str, str | int | None]:
    """Probe the primitive used by filesystem helpers, separately from shell IO."""
    argv = ['bwrap','--ro-bind','/','/','--dev','/dev','--proc','/proc','--unshare-user','--unshare-net','--','/bin/true']
    try:
        result = run_command(argv, cwd=Path('/tmp'), timeout=5, output_limit=1024)
    except (OSError, subprocess.TimeoutExpired):
        return {'status':'unavailable','reason':'helper_probe_unavailable','return_code':None}
    return {'status':'supported' if result.returncode == 0 else 'unavailable',
            'reason':'probe_passed' if result.returncode == 0 else 'network_namespace_probe_failed',
            'return_code':result.returncode}


def capability_report(*, shell_boundaries_passed: bool, helper: dict) -> dict:
    return {'shell_boundaries':'passed' if shell_boundaries_passed else 'failed',
            'helper_network_namespace':helper,
            'helper_network_namespace_supported':helper.get('status') == 'supported',
            'full_runtime_readiness_proven':False,
            'activation_authorized':False,'model_invocations':0,'account_credentials_used':False}
