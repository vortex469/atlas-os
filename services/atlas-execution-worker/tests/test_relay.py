from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from atlas_execution_worker.relay import relay_connection


def test_relay_closes_client_when_upstream_is_unavailable() -> None:
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)
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
    upstream_reader = AsyncMock(spec=asyncio.StreamReader)
    upstream_reader.read.side_effect = [b"response", b""]
    upstream_writer = AsyncMock(spec=asyncio.StreamWriter)

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
