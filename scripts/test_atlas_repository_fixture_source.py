import hashlib
import importlib.util
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest

DIRECTORY = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('fixture_source', DIRECTORY/'atlas_repository_fixture_source.py')
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def checkout(tmp_path):
    root = tmp_path/'code'
    file = root/'services/atlas-agent/app/example.py'
    file.parent.mkdir(parents=True)
    file.write_text('value = 1\n')
    return root, file


def valid_report(tmp_path):
    root, file = checkout(tmp_path)
    directory = tmp_path/'report'
    directory.mkdir()
    log = directory/'fixture.log'
    log.write_text('1 passed\n')
    report = {'phase':'audit','status':'passed','complete':True,'source':source.source_snapshot(root),'source_changed':False,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'exit_code':0,'passed_tests':1,'synthetic_approvals':True,'real_model_invocations':0,'account_credentials_used':False,'production_contact_allowed':False}
    path = directory/'report.json'
    source.write_report(path, report)
    return root,file,path,report


def test_verify_is_read_only_and_binds_source_and_log(tmp_path):
    root, _, path, _ = valid_report(tmp_path)
    before = path.read_bytes()
    assert source.verify_report(path,root)['valid']
    assert path.read_bytes() == before
    assert path.stat().st_mode & 0o777 == 0o600
    assert not list(path.parent.glob('.fixture-report-*'))


@pytest.mark.parametrize('change', ['source','log','incomplete','failure','scope'])
def test_stale_or_incomplete_report_cannot_be_a_pass(tmp_path, change):
    root,file,path,report = valid_report(tmp_path)
    if change == 'source':
        file.write_text('value = 2\n')
    elif change == 'log':
        (path.parent/'fixture.log').write_text('different')
    elif change == 'incomplete':
        report['complete'] = False
    elif change == 'failure':
        report['exit_code'] = 1
    else:
        report['production_contact_allowed'] = True
    if change not in {'source','log'}:
        source.write_report(path,report)
    with pytest.raises(ValueError):
        source.verify_report(path,root)


def test_source_symlink_is_not_hashed(tmp_path):
    root,file = checkout(tmp_path)
    other = tmp_path/'outside.py'
    other.write_text('outside')
    file.unlink()
    file.symlink_to(other)
    with pytest.raises(ValueError, match='escapes'):
        source.source_snapshot(root)


def test_midrun_source_change_is_not_reported_as_pass(tmp_path, monkeypatch):
    tool = runpy.run_path(str(DIRECTORY/'atlas-repository-action-check'))
    check = tool['run_check']
    snapshots = iter([{'content_sha256':'before'}, {'content_sha256':'after'}])
    monkeypatch.setitem(check.__globals__,'source_snapshot',lambda root: next(snapshots))
    process = Mock(pid=12345)
    process.wait.return_value = 0
    def start(*args, **kwargs):
        kwargs['stdout'].write(b'1 passed\n')
        return process
    monkeypatch.setattr(check.__globals__['subprocess'],'Popen',start)
    monkeypatch.setattr(check.__globals__['subprocess'],'run',lambda *args, **kwargs: None)
    monkeypatch.setattr(check.__globals__['os'],'killpg',lambda *args: None)
    report = check('audit',tmp_path/'result')
    assert report['exit_code'] == 3
    assert report['complete'] is False
    assert report['source_changed'] is True
    assert process.wait.call_count == 2


@pytest.mark.parametrize('outcome, code', [('timeout',124),('interrupt',130),('launch',125)])
def test_partial_checker_exit_never_produces_a_complete_pass(tmp_path, monkeypatch, outcome, code):
    import subprocess
    tool = runpy.run_path(str(DIRECTORY/'atlas-repository-action-check'))
    check = tool['run_check']
    monkeypatch.setitem(check.__globals__,'source_snapshot',lambda root: {'content_sha256':'same'})
    process = Mock(pid=12345)
    error = subprocess.TimeoutExpired('pytest',120) if outcome == 'timeout' else KeyboardInterrupt()
    process.wait.side_effect = [error,0]
    def start(*args, **kwargs):
        kwargs['stdout'].write(b'1 passed\n')
        if outcome == 'launch':
            raise FileNotFoundError('fixture launch unavailable')
        return process
    monkeypatch.setattr(check.__globals__['subprocess'],'Popen',start)
    monkeypatch.setattr(check.__globals__['subprocess'],'run',lambda *args, **kwargs: None)
    monkeypatch.setattr(check.__globals__['os'],'killpg',lambda *args: None)
    report = check('audit',tmp_path/'result')
    assert report['exit_code'] == code
    assert report['complete'] is False
    assert (tmp_path/'result'/'report.json').is_file()
