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
