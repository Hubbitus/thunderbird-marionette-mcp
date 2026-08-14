"""MarionetteSession singleton wrapping marionette_driver."""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from collections.abc import Callable
from typing import Any, Literal, TypeVar

from marionette_driver.marionette import Marionette

from tb_marionette_mcp.errors import MarionetteWireError, NotConnectedError

T = TypeVar("T")

Context = Literal["chrome", "content"]


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class MarionetteSession:
    _instance: MarionetteSession | None = None

    def __init__(self) -> None:
        self.host = os.environ.get("TB_MCP_MARIONETTE_HOST", "127.0.0.1")
        self.port = int(os.environ.get("TB_MCP_MARIONETTE_PORT", "2828"))
        self.session_id = str(uuid.uuid4())
        self._client: Marionette | None = None
        self._connected = False
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> MarionetteSession:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def client(self) -> Marionette:
        if self._client is None:
            raise NotConnectedError("session not initialised")
        return self._client

    async def ensure_connected(self) -> None:
        if self._connected and self._client is not None:
            return
        if not _port_open(self.host, self.port):
            raise NotConnectedError(
                f"Marionette port {self.host}:{self.port} not open; "
                "call thunderbird_launch first or start TB with --marionette"
            )
        client = Marionette(host=self.host, port=self.port)
        await asyncio.to_thread(client.start_session)
        self._client = client
        self._connected = True

    async def _reconnect(self) -> None:
        self._connected = False
        self._client = None
        await self.ensure_connected()

    async def call(
        self,
        fn: Callable[..., T],
        *args: Any,
        ctx: Context | None = None,
        **kwargs: Any,
    ) -> T:
        async with self._lock:
            await self.ensure_connected()
            client = self.client

            def _run() -> T:
                if ctx is None:
                    return fn(*args, **kwargs)
                with client.using_context(ctx):
                    return fn(*args, **kwargs)

            try:
                return await asyncio.to_thread(_run)
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                try:
                    await self._reconnect()
                    return await asyncio.to_thread(_run)
                except Exception as retry_exc:
                    raise MarionetteWireError(
                        f"Marionette wire error: {retry_exc}"
                    ) from retry_exc
