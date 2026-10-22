"""Private, bounded, integrity-checked worker diagnostic export."""
import base64
import hashlib
import json
import runpy
import sqlite3
from pathlib import Path

import pytest

MODULE = Path(__file__).with_name('atlas-worker-ledger-export')


def exporter(tmp_path, monkeypatch, *, corrupt=None):
    functions = runpy.run_path(str(MODULE))
    export = functions['export_ledger']
    source = tmp_path / 'fixture.sqlite3'
    with sqlite3.connect(source) as database:
        database.execute('CREATE TABLE audit (value TEXT)')
        database.execute('INSERT INTO audit VALUES (?)', ('fixture' * 4000,))
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
