"""Local fixture source/report integrity; not a signature or approval proof."""
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_LOG_BYTES = 16 * 1024 * 1024


def source_snapshot(root: Path) -> dict:
    root = root.resolve()
    paths = set()
    for relative in ('services/atlas-agent/app','services/atlas-agent/tests','services/atlas-execution-worker/atlas_execution_worker'):
        paths.update((root/relative).rglob('*.py'))
    for relative in ('scripts/atlas-repository-action-check','scripts/atlas_repository_fixture_guard.py','scripts/atlas_repository_fixture_source.py','services/atlas-agent/requirements.txt','services/atlas-agent/requirements-dev.txt'):
        if (root/relative).exists():
            paths.add(root/relative)
    if not paths or len(paths) > 5000:
        raise ValueError('unsupported fixture source set')
    digest = hashlib.sha256()
    total = 0
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('fixture source escapes checkout')
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise ValueError('fixture source file exceeds bound')
        with path.open('rb') as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        after = path.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) or len(content) > MAX_FILE_BYTES:
            raise ValueError('fixture source changed during snapshot')
        total += len(content)
        if total > MAX_SOURCE_BYTES:
            raise ValueError('fixture source set exceeds bound')
        digest.update(str(path.relative_to(root)).encode()+b'\x00'+hashlib.sha256(content).digest())
    commit = subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,check=False,timeout=5)
    cleanliness = subprocess.run(['git','--no-optional-locks','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-C',str(root),'status','--porcelain','--untracked-files=all','--','services/atlas-agent/app','services/atlas-agent/tests','services/atlas-execution-worker/atlas_execution_worker','scripts/atlas-repository-action-check','scripts/atlas_repository_fixture_guard.py','scripts/atlas_repository_fixture_source.py','services/atlas-agent/requirements.txt','services/atlas-agent/requirements-dev.txt'],capture_output=True,text=True,check=False,timeout=5)
    return {'content_sha256':digest.hexdigest(),'files':len(paths),'bytes':total,'commit':commit.stdout.strip() if commit.returncode == 0 else None,'source_tree_clean':not cleanliness.stdout if cleanliness.returncode == 0 else None}


def log_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LOG_BYTES:
        raise ValueError('invalid bounded fixture log')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def write_report(path: Path, report: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix='.fixture-report-',dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor,'w') as output:
            json.dump(report,output,sort_keys=True,indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary,path)
        directory = os.open(path.parent,os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def verify_report(path: Path, root: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('invalid fixture report file')
    report = json.loads(path.read_text())
    if not isinstance(report,dict) or report.get('complete') is not True or report.get('status') != 'passed' or type(report.get('exit_code')) is not int or report['exit_code'] != 0:
        raise ValueError('fixture report is not a complete pass')
    if type(report.get('passed_tests')) is not int or report['passed_tests'] <= 0 or report.get('synthetic_approvals') is not True or report.get('account_credentials_used') is not False or type(report.get('real_model_invocations')) is not int or report['real_model_invocations'] != 0 or report.get('production_contact_allowed') is not False or report.get('source_changed') is not False:
        raise ValueError('fixture report scope mismatch')
    if report.get('phase') not in {'approval','journey','recovery','audit','all'}:
        raise ValueError('unknown fixture phase')
    source = report.get('source')
    current = source_snapshot(root)
    if not isinstance(source,dict) or any(source.get(field) != current[field] for field in ('content_sha256','files','bytes')):
        raise ValueError('fixture source is stale')
    if report.get('log_sha256') != log_digest(path.parent/'fixture.log'):
        raise ValueError('fixture log integrity mismatch')
    return {'valid':True,'content_sha256':current['content_sha256'],'source_commit':source.get('commit'),'approval_authority':False}
