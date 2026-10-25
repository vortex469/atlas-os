"""Private, bounded, integrity-checked worker diagnostic export."""
import base64
import hashlib
import json
import runpy
import sqlite3
from pathlib import Path

import pytest

MODULE = Path(__file__).with_name('atlas-worker-ledger-export')


def exporter(tmp_path, monkeypatch, *, corrupt=None, invalid=None):
    functions = runpy.run_path(str(MODULE))
    export = functions['export_ledger']
    source = tmp_path / 'fixture.sqlite3'
    with sqlite3.connect(source) as database:
        database.execute('CREATE TABLE executions (execution_request_id TEXT PRIMARY KEY, request_digest TEXT, schema_version INTEGER, state TEXT, created_at TEXT, updated_at TEXT, attempt INTEGER, execution_started_at TEXT, workspace_token TEXT, result_json TEXT)')
        for index in range(100):
            database.execute('INSERT INTO executions VALUES (?,?,1,?,?,?,1,NULL,NULL,NULL)', (f'execution-{index}', 'execution-request-digest-v1:'+'0'*64, 'claimed', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'))
        if invalid == 'schema':
            database.execute('DROP TABLE executions')
            database.execute('CREATE TABLE unrelated (value TEXT)')
        elif invalid == 'terminal':
            database.execute("UPDATE executions SET state='completed'")
        elif invalid == 'attempt':
            database.execute('UPDATE executions SET attempt=2')
        elif invalid == 'digest':
            database.execute("UPDATE executions SET request_digest='invalid'")
    data = source.read_bytes()
    calls = []

    def docker(container, code, *args):
        assert container == 'isolated-worker'
        calls.append((code, args))
        if code == functions['BACKUP_CODE']:
            return json.dumps({'path': '/tmp/atlas-ledger-export-fixture/ledger.sqlite3', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        if 'shutil.rmtree' in code:
            return ''
        _, offset, count = args
        assert 0 < int(count) <= functions['CHUNK_BYTES']
        chunk = data[int(offset):int(offset) + int(count)]
        if corrupt == 'short':
            chunk = chunk[:-1]
        if corrupt == 'digest':
            chunk = b'x' * len(chunk)
        return base64.b64encode(chunk).decode()

    monkeypatch.setitem(export.__globals__, 'docker_python', docker)
    return export, data, calls


def test_large_export_uses_private_chunks_and_checks_database(tmp_path, monkeypatch):
    export, expected, calls = exporter(tmp_path, monkeypatch)
    target = tmp_path / 'retained.sqlite3'

    result = export('isolated-worker', target)

    assert len(expected) > 8192
    assert target.read_bytes() == expected
    assert target.stat().st_mode & 0o777 == 0o600
    assert result['integrity'] == 'ok'
    assert result['ledger_entries'] == 100
    assert result['sha256'] == hashlib.sha256(expected).hexdigest()
    assert len(calls) > 3
    assert 'shutil.rmtree' in calls[-1][0]
    assert not list(tmp_path.glob('.atlas-ledger-*'))


@pytest.mark.parametrize('corrupt', ['short', 'digest'])
def test_incomplete_or_corrupt_export_never_publishes_file(tmp_path, monkeypatch, corrupt):
    export, _, calls = exporter(tmp_path, monkeypatch, corrupt=corrupt)
    target = tmp_path / 'retained.sqlite3'

    with pytest.raises(ValueError):
        export('isolated-worker', target)

    assert not target.exists()
    assert not list(tmp_path.glob('.atlas-ledger-*'))
    assert 'shutil.rmtree' in calls[-1][0]


def test_existing_destination_is_never_overwritten(tmp_path, monkeypatch):
    export, _, calls = exporter(tmp_path, monkeypatch)
    target = tmp_path / 'retained.sqlite3'
    target.write_text('keep')

    with pytest.raises(ValueError, match='already exists'):
        export('isolated-worker', target)

    assert target.read_text() == 'keep'
    assert calls == []


@pytest.mark.parametrize('invalid', ['schema', 'terminal', 'attempt', 'digest'])
def test_wrong_domain_database_is_not_published(tmp_path, monkeypatch, invalid):
    export, original, calls = exporter(tmp_path, monkeypatch, invalid=invalid)
    target = tmp_path/'retained.sqlite3'
    with pytest.raises(ValueError):
        export('isolated-worker', target)
    assert not target.exists()
    assert (tmp_path/'fixture.sqlite3').read_bytes() == original
    assert 'shutil.rmtree' in calls[-1][0]


def test_terminal_result_contract_and_identity_are_checked(tmp_path, monkeypatch):
    exporter(tmp_path, monkeypatch)
    from app.execution.worker_contracts import (
        BoundedOutput,
        WorkerAttestation,
        WorkerExecutionResult,
        WorkerExecutionStatus,
        WorkerFailureCode,
    )
    result = WorkerExecutionResult(schema_version=1,execution_request_id='execution-0',status=WorkerExecutionStatus.BLOCKED,return_code=None,stdout=BoundedOutput(''),stderr=BoundedOutput(''),changed_files=(),patch_digest=None,patch_size_bytes=None,patch_truncated=False,duration_seconds=0,failure_code=WorkerFailureCode.WORKER_UNAVAILABLE,workspace_head=None,worker_attestation=WorkerAttestation(10001,True,True,'0000000000000000','execution-disabled'))
    validate = runpy.run_path(str(MODULE))['validate_ledger']
    with sqlite3.connect(tmp_path/'fixture.sqlite3') as database:
        database.execute("UPDATE executions SET state='failed_terminal',result_json=? WHERE execution_request_id='execution-0'", (json.dumps(result.to_dict()),))
        assert validate(database) == 100
        payload = result.to_dict()
        payload['execution_request_id'] = 'different-id'
        database.execute("UPDATE executions SET result_json=? WHERE execution_request_id='execution-0'", (json.dumps(payload),))
        with pytest.raises(ValueError, match='identity mismatch'):
            validate(database)
