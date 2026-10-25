"""Bounded private worker transport, without model or external network access."""
import json

import pytest
from app.execution import worker_client
from app.execution.worker_client import TcpWorkerClient, WorkerTransportError


class Connection:
    def __init__(self, response):
        self.response = response
        self.offset = 0
        self.sent = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def settimeout(self, timeout):
        pass

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, count):
        chunk = self.response[self.offset:self.offset + count]
        self.offset += len(chunk)
        return chunk


def client(monkeypatch, response):
    connection = Connection(response)
    calls = []
    def connect(*args, **kwargs):
        calls.append((args, kwargs))
        return connection
    monkeypatch.setattr(worker_client.socket, 'create_connection', connect)
    return TcpWorkerClient('worker.invalid', 8081), connection, calls


def response(payload):
    body = json.dumps(payload).encode()
    return b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body


def test_header_overflow_closes_one_connection_without_retry(monkeypatch):
    subject, connection, calls = client(monkeypatch, b'HTTP/1.1 200 OK\r\nX: ' + b'x' * 20_000)
    with pytest.raises(WorkerTransportError, match='headers exceed'):
        subject.health()
    assert connection.closed
    assert len(calls) == len(connection.sent) == 1


def test_body_overflow_closes_one_connection_without_retry(monkeypatch):
    monkeypatch.setattr(worker_client, 'MAX_RESPONSE_BODY_BYTES', 128)
    subject, connection, calls = client(monkeypatch, response({'value': 'x' * 129}))
    with pytest.raises(WorkerTransportError, match='body exceeds'):
        subject.health()
    assert connection.closed
    assert len(calls) == len(connection.sent) == 1


def test_maximum_contract_texts_with_json_escaping_fit_transport_bound(monkeypatch):
    text = '\x00' * 1_048_576
    payload = {'result': {field: {'text': text} for field in ('stdout', 'stderr', 'patch')}}
    raw = response(payload)
    assert len(raw) < worker_client.MAX_RESPONSE_BODY_BYTES
    subject, connection, calls = client(monkeypatch, raw)
    assert subject.health() == payload
    assert connection.closed
    assert len(calls) == 1


@pytest.mark.parametrize('raw', [
    b'HTTP/1.1 200 OK\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\ncontent-length: 2\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: -2\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: +2\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n X: folded\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nX: \x00\r\n\r\n{}',
    b'not-http\r\nContent-Length: 2\r\n\r\n{}',
    b'HTTP/2 200 OK\r\nContent-Length: 2\r\n\r\n{}',
    b'HTTP/1.1 100 Continue\r\nContent-Length: 2\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n',
])
def test_ambiguous_or_incomplete_framing_fails_without_retry(monkeypatch, raw):
    subject, connection, calls = client(monkeypatch, raw)
    with pytest.raises(WorkerTransportError):
        subject.health()
    assert connection.closed
    assert len(calls) == len(connection.sent) == 1


@pytest.mark.parametrize('body', [b'[]', b'null', b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":"\xff"}'])
def test_invalid_or_ambiguous_json_is_controlled(monkeypatch, body):
    raw = b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body
    subject, _, calls = client(monkeypatch, raw)
    with pytest.raises(WorkerTransportError, match='malformed JSON'):
        subject.health()
    assert len(calls) == 1


def test_complete_framed_response_does_not_wait_for_connection_close(monkeypatch):
    subject, connection, _ = client(monkeypatch, response({'status': 'healthy'}))
    original = connection.recv
    def recv(count):
        if connection.offset == len(connection.response):
            pytest.fail('client waited for EOF after complete framed response')
        return original(count)
    monkeypatch.setattr(connection, 'recv', recv)
    assert subject.health() == {'status': 'healthy'}


def test_trickling_data_cannot_reset_total_deadline(monkeypatch):
    subject, connection, calls = client(monkeypatch, response({'status': 'healthy'}))
    elapsed = [0.0]
    monkeypatch.setattr(worker_client.time, 'monotonic', lambda: elapsed[0])
    original = connection.recv
    def recv(count):
        elapsed[0] += 0.4
        return original(1)
    monkeypatch.setattr(connection, 'recv', recv)
    subject._timeout_seconds = 1
    with pytest.raises(WorkerTransportError, match='deadline exceeded'):
        subject.health()
    assert elapsed[0] < 1.5
    assert len(calls) == len(connection.sent) == 1
    assert connection.closed


@pytest.mark.parametrize('body, expected', [(b'{"error":[]}', 'worker_error'), (b'{"error":{"code":"authentication_required"}}', 'authentication_required'), (b'{"error":{"code":"private text with spaces"}}', 'worker_error')])
def test_error_envelopes_return_only_controlled_codes(monkeypatch, body, expected):
    raw = b'HTTP/1.1 401 Unauthorized\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body
    subject, _, _ = client(monkeypatch, raw)
    with pytest.raises(WorkerTransportError, match=f'^{expected}$'):
        subject.health()


@pytest.mark.parametrize('timeout', [0, -1, float('inf'), float('nan'), True])
def test_invalid_deadline_is_rejected(timeout):
    with pytest.raises(ValueError):
        TcpWorkerClient('worker.invalid', 8081, timeout_seconds=timeout)


def test_request_header_and_path_injection_are_rejected_before_contact(monkeypatch):
    subject, _, calls = client(monkeypatch, b'')
    with pytest.raises(WorkerTransportError):
        subject.get_result('execution\r\nX: injected')
    with pytest.raises(ValueError):
        TcpWorkerClient('worker.invalid', 8081, authentication_token='credential\r\nX: injected')
    assert calls == []


def test_fragmented_headers_and_body_are_accepted(monkeypatch):
    subject, connection, _ = client(monkeypatch, response({'status': 'healthy'}))
    original = connection.recv
    monkeypatch.setattr(connection, 'recv', lambda count: original(1))
    assert subject.health() == {'status': 'healthy'}


def test_real_slow_response_has_one_total_deadline():
    import socket
    import threading
    import time

    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(2)
    port = listener.getsockname()[1]
    stop = threading.Event()
    body = json.dumps({'status': 'healthy'}).encode()

    def serve():
        try:
            with listener, listener.accept()[0] as connection:
                connection.settimeout(1)
                connection.recv(4096)
                connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n')
                for byte in body:
                    if stop.wait(0.04):
                        break
                    connection.sendall(bytes([byte]))
        except OSError:
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        with pytest.raises(WorkerTransportError):
            TcpWorkerClient('127.0.0.1', port, timeout_seconds=0.15).health()
        assert time.monotonic() - started < 0.9
    finally:
        stop.set()
        thread.join(timeout=3)
        listener.close()
    assert not thread.is_alive()
