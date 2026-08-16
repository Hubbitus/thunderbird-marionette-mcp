from __future__ import annotations

import pytest

from tb_marionette_mcp.process import ProcessRegistry
from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.process_tools import (
    thunderbird_launch,
    thunderbird_status,
)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_status_running(session: MarionetteSession) -> None:
    s = await thunderbird_status()
    assert s["running"] is True or s["connected"] is True


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_status_stable_across_calls(session: MarionetteSession) -> None:
    """Repeat status calls return consistent connected=True while TB up."""
    s1 = await thunderbird_status()
    s2 = await thunderbird_status()
    assert s1["connected"] is True
    assert s2["connected"] is True
    assert s1["port"] == s2["port"] == session.port


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_launch_idempotent_when_tb_already_running(
    session: MarionetteSession, tb_process,
) -> None:
    """thunderbird_launch called against a port with a running TB must NOT
    spawn a second TB — it should recognize the port and return the tracked
    pid with already_running=True.

    tb_process (the conftest fixture) starts TB via subprocess.Popen without
    routing through ProcessRegistry, so we register it here to make the
    fixture's TB visible to the idempotency check.
    """
    ProcessRegistry.register(tb_process)
    try:
        result = await thunderbird_launch(
            profile="/nonexistent/profile-should-be-ignored",
            marionette_port=session.port,
            wait_ready=False,
        )
        assert result["already_running"] is True
        assert result["pid"] == tb_process.pid
        assert result["port"] == session.port
        assert result["connected"] is True
    finally:
        # Do NOT unregister — process_registry.unregister also unlinks stderr
        # path (not set here) and would leave fixture teardown OK either way.
        ProcessRegistry.unregister(tb_process.pid)
