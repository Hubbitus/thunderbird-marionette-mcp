"""Process management tools."""

from __future__ import annotations

from typing import Any

from tb_marionette_mcp.errors import InvalidArgumentError
from tb_marionette_mcp.process import (
    ProcessRegistry,
    _probe_port,
    spawn,
    status,
    terminate,
    wait_port_open,
)
from tb_marionette_mcp.session import MarionetteSession


async def thunderbird_launch(
    profile: str,
    marionette_port: int = 2828,
    wait_ready: bool = True,
    ready_timeout: float = 30.0,
) -> dict[str, Any]:
    # Idempotency: if the Marionette port is already reachable and a pid is
    # tracked, reuse that TB rather than spawning a second one on the same port.
    if _probe_port("127.0.0.1", marionette_port):
        existing = ProcessRegistry.any_pid()
        if existing is not None:
            session = MarionetteSession.get()
            session.port = marionette_port
            return {
                "pid": existing,
                "port": marionette_port,
                "connected": True,
                "already_running": True,
            }
    pid = spawn(profile, marionette_port)
    connected = False
    if wait_ready:
        wait_port_open("127.0.0.1", marionette_port, ready_timeout)
        connected = True
    session = MarionetteSession.get()
    session.port = marionette_port
    return {
        "pid": pid,
        "port": marionette_port,
        "connected": connected,
        "already_running": False,
    }


async def thunderbird_terminate(pid: int | None = None) -> dict[str, bool]:
    target = pid if pid is not None else ProcessRegistry.any_pid()
    if target is None:
        raise InvalidArgumentError("no tracked pid and none supplied")
    stopped = terminate(target)
    session = MarionetteSession.get()
    session._connected = False
    session._client = None
    return {"stopped": stopped}


async def thunderbird_status() -> dict[str, Any]:
    session = MarionetteSession.get()
    return status(session.port, host=session.host)
