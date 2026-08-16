from unittest.mock import patch

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.process_tools import (
    thunderbird_launch,
    thunderbird_status,
    thunderbird_terminate,
)


@pytest.fixture(autouse=True)
def reset_session():
    MarionetteSession._instance = None
    yield
    MarionetteSession._instance = None


@pytest.mark.asyncio
async def test_launch_success():
    with patch("tb_marionette_mcp.tools.process_tools.spawn", return_value=42) as spawn_m, \
         patch("tb_marionette_mcp.tools.process_tools.wait_port_open") as wait_m:
        result = await thunderbird_launch(profile="test", marionette_port=2828,
                                          wait_ready=True, ready_timeout=5)
    spawn_m.assert_called_once()
    wait_m.assert_called_once()
    assert result["pid"] == 42
    assert result["port"] == 2828
    assert result["connected"] is True


@pytest.mark.asyncio
async def test_launch_no_wait():
    with patch("tb_marionette_mcp.tools.process_tools.spawn", return_value=42), \
         patch("tb_marionette_mcp.tools.process_tools.wait_port_open") as wait_m:
        result = await thunderbird_launch(profile="test", marionette_port=2828,
                                          wait_ready=False, ready_timeout=5)
    wait_m.assert_not_called()
    assert result["connected"] is False


@pytest.mark.asyncio
async def test_launch_idempotent_when_port_open():
    """If Marionette port already reachable and a pid is tracked, do NOT spawn
    a second TB — return the existing pid with already_running=True."""
    with patch("tb_marionette_mcp.tools.process_tools._probe_port", return_value=True), \
         patch("tb_marionette_mcp.tools.process_tools.ProcessRegistry.any_pid",
               return_value=99), \
         patch("tb_marionette_mcp.tools.process_tools.spawn") as spawn_m:
        result = await thunderbird_launch(profile="test", marionette_port=2828,
                                          wait_ready=True, ready_timeout=5)
    spawn_m.assert_not_called()
    assert result["pid"] == 99
    assert result["already_running"] is True


@pytest.mark.asyncio
async def test_launch_spawns_when_port_closed():
    with patch("tb_marionette_mcp.tools.process_tools._probe_port", return_value=False), \
         patch("tb_marionette_mcp.tools.process_tools.spawn", return_value=42) as spawn_m, \
         patch("tb_marionette_mcp.tools.process_tools.wait_port_open"):
        result = await thunderbird_launch(profile="test", marionette_port=2828,
                                          wait_ready=True, ready_timeout=5)
    spawn_m.assert_called_once()
    assert result["pid"] == 42
    assert result.get("already_running", False) is False


@pytest.mark.asyncio
async def test_terminate_none_uses_registry():
    with patch("tb_marionette_mcp.tools.process_tools.ProcessRegistry.any_pid",
               return_value=42), \
         patch("tb_marionette_mcp.tools.process_tools.terminate", return_value=True) as term:
        result = await thunderbird_terminate(pid=None)
    term.assert_called_once_with(42)
    assert result["stopped"] is True


@pytest.mark.asyncio
async def test_status():
    with patch("tb_marionette_mcp.tools.process_tools.status",
               return_value={"running": True, "pid": 42, "port": 2828, "connected": True}):
        result = await thunderbird_status()
    assert result["running"] is True


@pytest.mark.asyncio
async def test_terminate_no_pid_raises():
    from tb_marionette_mcp.errors import InvalidArgumentError
    with patch("tb_marionette_mcp.tools.process_tools.ProcessRegistry.any_pid",
               return_value=None), \
         pytest.raises(InvalidArgumentError):
        await thunderbird_terminate(pid=None)
