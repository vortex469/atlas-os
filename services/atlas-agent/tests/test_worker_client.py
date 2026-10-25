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
