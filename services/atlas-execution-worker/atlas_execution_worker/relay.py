"""Network-segmented TCP relay for the Agent-to-worker control plane."""

from __future__ import annotations

import asyncio
import os
import socket

DEFAULT_LISTEN_HOST = "atlas-execution-worker-relay-transport"
DEFAULT_LISTEN_PORT = 8081
DEFAULT_UPSTREAM_HOST = "atlas-execution-worker"
DEFAULT_UPSTREAM_PORT = 8081


async def _copy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65_536):
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def relay_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    upstream_host: str,
    upstream_port: int,
) -> None:
    """Relay one connection and close both directions deterministically."""

    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(
            upstream_host, upstream_port
        )
    except OSError:
        writer.close()
        await writer.wait_closed()
        return
    await asyncio.gather(
        _copy(reader, upstream_writer),
        _copy(upstream_reader, writer),
    )


async def serve() -> None:
    """Bind only the transport-network address, never the worker-side interface."""

    listen_host = os.getenv("ATLAS_EXECUTION_RELAY_HOST", DEFAULT_LISTEN_HOST)
    listen_address = socket.gethostbyname(listen_host)
    listen_port = int(os.getenv("ATLAS_EXECUTION_RELAY_PORT", str(DEFAULT_LISTEN_PORT)))
    upstream_host = os.getenv("ATLAS_EXECUTION_RELAY_UPSTREAM_HOST", DEFAULT_UPSTREAM_HOST)
    upstream_port = int(
        os.getenv("ATLAS_EXECUTION_RELAY_UPSTREAM_PORT", str(DEFAULT_UPSTREAM_PORT))
    )

    server = await asyncio.start_server(
        lambda reader, writer: relay_connection(
            reader,
            writer,
            upstream_host=upstream_host,
            upstream_port=upstream_port,
        ),
        listen_address,
        listen_port,
    )
    async with server:
        await server.serve_forever()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
