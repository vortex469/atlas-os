"""Network-segmented TCP relay for the Agent-to-worker control plane."""

from __future__ import annotations

import asyncio
import os
import socket

DEFAULT_LISTEN_HOST = "atlas-execution-worker-relay-transport"
DEFAULT_LISTEN_PORT = 8081
DEFAULT_UPSTREAM_HOST = "atlas-execution-worker"
DEFAULT_UPSTREAM_PORT = 8081
CONNECT_TIMEOUT_SECONDS = 5.0
MAX_CONNECTION_SECONDS = 3900.0
CLOSE_TIMEOUT_SECONDS = 1.0


async def _copy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    while data := await reader.read(65_536):
        writer.write(data)
        await writer.drain()
    # Preserve TCP half-close: a finished request may still await its response.
    if writer.can_write_eof():
        writer.write_eof()
        await writer.drain()


async def _wait_closed(writer: asyncio.StreamWriter) -> None:
    try:
        await asyncio.wait_for(writer.wait_closed(), timeout=CLOSE_TIMEOUT_SECONDS)
    except (OSError, TimeoutError):
        pass


async def relay_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    upstream_host: str,
    upstream_port: int,
) -> None:
    """Bound one connection; cancel/join owned copies and close both writers."""

    upstream_writer = None
    tasks = []
    try:
        async with asyncio.timeout(MAX_CONNECTION_SECONDS):
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(upstream_host, upstream_port),
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
            tasks = [asyncio.create_task(_copy(reader, upstream_writer)),
                     asyncio.create_task(_copy(upstream_reader, writer))]
            await asyncio.gather(*tasks)
    except (OSError, TimeoutError):
        pass
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        writers = [writer] + ([upstream_writer] if upstream_writer is not None else [])
        for owned in writers:
            owned.close()
        await asyncio.gather(*(_wait_closed(owned) for owned in writers))


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
