from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from atlas_execution_worker.relay import relay_connection


def test_relay_closes_client_when_upstream_is_unavailable() -> None:
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.can_write_eof.return_value = False
    with patch("atlas_execution_worker.relay.asyncio.open_connection", side_effect=OSError):
        asyncio.run(
            relay_connection(
                reader,
                writer,
                upstream_host="worker",
                upstream_port=8081,
            )
        )
    writer.close.assert_called_once_with()
    writer.wait_closed.assert_awaited_once_with()


def test_relay_copies_both_directions() -> None:
    client_reader = AsyncMock(spec=asyncio.StreamReader)
    client_reader.read.side_effect = [b"request", b""]
    client_writer = AsyncMock(spec=asyncio.StreamWriter)
    client_writer.can_write_eof.return_value = False
    upstream_reader = AsyncMock(spec=asyncio.StreamReader)
    upstream_reader.read.side_effect = [b"response", b""]
    upstream_writer = AsyncMock(spec=asyncio.StreamWriter)
    upstream_writer.can_write_eof.return_value = False

    with patch(
        "atlas_execution_worker.relay.asyncio.open_connection",
        return_value=(upstream_reader, upstream_writer),
    ):
        asyncio.run(
            relay_connection(
                client_reader,
                client_writer,
                upstream_host="worker",
                upstream_port=8081,
            )
        )

    upstream_writer.write.assert_called_once_with(b"request")
    client_writer.write.assert_called_once_with(b"response")
    upstream_writer.close.assert_called_once_with()
    client_writer.close.assert_called_once_with()


def test_upstream_connect_deadline_closes_client(monkeypatch):
    from atlas_execution_worker import relay

    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.can_write_eof.return_value = False
    monkeypatch.setattr(relay, 'CONNECT_TIMEOUT_SECONDS', 0.01)
    cancelled = []

    async def stalled(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    with patch.object(relay.asyncio, 'open_connection', side_effect=stalled):
        asyncio.run(relay_connection(reader, writer, upstream_host='worker', upstream_port=8081))
    assert cancelled == [True]
    writer.close.assert_called_once()


def test_total_lifetime_cancels_both_copy_directions(monkeypatch):
    from atlas_execution_worker import relay

    monkeypatch.setattr(relay, 'MAX_CONNECTION_SECONDS', 0.01)
    readers = [AsyncMock(spec=asyncio.StreamReader) for _ in range(2)]
    writers = [AsyncMock(spec=asyncio.StreamWriter) for _ in range(2)]
    cancelled = []

    async def stalled(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    for reader in readers:
        reader.read.side_effect = stalled
    with patch.object(relay.asyncio, 'open_connection', return_value=(readers[1], writers[1])):
        asyncio.run(relay_connection(readers[0], writers[0], upstream_host='worker', upstream_port=8081))
    assert len(cancelled) == 2
    assert all(writer.close.called for writer in writers)


def test_copy_failure_joins_sibling_and_bounds_writer_cleanup(monkeypatch):
    from atlas_execution_worker import relay

    monkeypatch.setattr(relay, 'CLOSE_TIMEOUT_SECONDS', 0.01)
    readers = [AsyncMock(spec=asyncio.StreamReader) for _ in range(2)]
    writers = [AsyncMock(spec=asyncio.StreamWriter) for _ in range(2)]
    stopped = []

    async def stalled(*args):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(True)

    readers[0].read.side_effect = ConnectionResetError('synthetic disconnect')
    readers[1].read.side_effect = stalled
    writers[0].wait_closed.side_effect = stalled
    with patch.object(relay.asyncio, 'open_connection', return_value=(readers[1], writers[1])):
        asyncio.run(asyncio.wait_for(relay_connection(readers[0], writers[0],
                    upstream_host='worker', upstream_port=8081), timeout=0.5))
    assert stopped  # blocked sibling and/or close waiter were cancelled and joined
    assert all(writer.close.call_count == 1 for writer in writers)


def test_external_cancellation_closes_both_writers():
    from atlas_execution_worker import relay

    async def exercise():
        readers = [AsyncMock(spec=asyncio.StreamReader) for _ in range(2)]
        writers = [AsyncMock(spec=asyncio.StreamWriter) for _ in range(2)]
        entered = asyncio.Event()
        stopped = []

        async def stalled(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.append(True)

        for reader in readers:
            reader.read.side_effect = stalled
        with patch.object(relay.asyncio, 'open_connection', return_value=(readers[1], writers[1])):
            task = asyncio.create_task(relay_connection(readers[0], writers[0],
                                       upstream_host='worker', upstream_port=8081))
            await entered.wait()
            task.cancel()
            import pytest
            with pytest.raises(asyncio.CancelledError):
                await task
        assert len(stopped) == 2
        assert all(writer.close.call_count == 1 for writer in writers)

    asyncio.run(exercise())


def test_real_tcp_half_close_preserves_response():
    async def exercise():
        finished = asyncio.Event()

        async def upstream(reader, writer):
            try:
                request = await reader.read()
                writer.write(b'response:' + request)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        source = await asyncio.start_server(upstream, '127.0.0.1', 0)
        source_port = source.sockets[0].getsockname()[1]

        async def forward(reader, writer):
            try:
                await relay_connection(reader, writer, upstream_host='127.0.0.1',
                                       upstream_port=source_port)
            finally:
                finished.set()

        server = await asyncio.start_server(forward, '127.0.0.1', 0)
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', server.sockets[0].getsockname()[1])
            writer.write(b'fixture')
            await writer.drain()
            writer.write_eof()
            assert await asyncio.wait_for(reader.read(), timeout=2) == b'response:fixture'
            writer.close()
            await writer.wait_closed()
            await asyncio.wait_for(finished.wait(), timeout=2)
        finally:
            server.close()
            source.close()
            await server.wait_closed()
            await source.wait_closed()

    asyncio.run(exercise())
