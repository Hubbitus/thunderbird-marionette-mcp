"""execute_script and wait_for_condition."""

from __future__ import annotations

import time
from typing import Any

from tb_marionette_mcp.errors import TimeoutError as TbTimeoutError
from tb_marionette_mcp.session import Context, MarionetteSession


async def execute_script(
    script: str,
    args: list[Any] | None = None,
    context: Context = "chrome",
    async_: bool = False,
    timeout: float = 30.0,
) -> dict[str, Any]:
    args = args or []
    session = MarionetteSession.get()

    def _exec() -> Any:
        session.client.set_script_timeout(int(timeout * 1000))
        if async_:
            return session.client.execute_async_script(script, script_args=args)
        return session.client.execute_script(script, script_args=args)

    return {"result": await session.call(_exec, ctx=context)}


async def wait_for_condition(
    script: str,
    args: list[Any] | None = None,
    context: Context = "chrome",
    timeout: float = 30.0,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    args = args or []
    session = MarionetteSession.get()
    deadline = time.monotonic() + timeout

    def _once() -> Any:
        return session.client.execute_script(script, script_args=args)

    while time.monotonic() < deadline:
        value = await session.call(_once, ctx=context)
        if value:
            return {"result": value}
        time.sleep(poll_interval)
    raise TbTimeoutError(f"wait_for_condition timeout after {timeout}s")
