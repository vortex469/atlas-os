import runpy
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).parent


def test_checker_rejects_arbitrary_phase_and_existing_directory(tmp_path):
    check = runpy.run_path(str(ROOT/'atlas-repository-action-check'))['run_check']
    with pytest.raises(ValueError, match='unknown'):
        check('arbitrary-command', tmp_path/'new')
    assert not (tmp_path/'new').exists()
    (tmp_path/'keep').write_text('original')
    with pytest.raises(ValueError, match='empty'):
        check('all', tmp_path)
    assert (tmp_path/'keep').read_text() == 'original'


def test_guard_denies_external_connect_and_resolution(monkeypatch):
    guard = runpy.run_path(str(ROOT/'atlas_repository_fixture_guard.py'))
    calls = []
    monkeypatch.setattr(socket.socket, 'connect', lambda *args: calls.append('connect'))
    monkeypatch.setattr(socket.socket, 'connect_ex', lambda *args: calls.append('connect_ex'))
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: calls.append('resolve'))
    guard['pytest_configure'](None)
    with pytest.raises(RuntimeError):
        socket.socket.connect(None, ('203.0.113.1', 80))
    with pytest.raises(RuntimeError):
        socket.socket.connect_ex(None, ('203.0.113.1', 80))
    with pytest.raises(RuntimeError):
        socket.getaddrinfo('external.invalid', 80)
    assert calls == []


@pytest.mark.parametrize('host, expected', [('127.0.0.1',True),('::1',True),('localhost',True),('203.0.113.1',False),('external.invalid',False)])
def test_loopback_classification(host, expected):
    assert runpy.run_path(str(ROOT/'atlas_repository_fixture_guard.py'))['_local'](host) is expected
