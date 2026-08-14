from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tb_marionette_mcp.errors import MarionetteWireError, NotConnectedError
from tb_marionette_mcp.session import MarionetteSession


@pytest.fixture(autouse=True)
def reset_singleton():
    MarionetteSession._instance = None
    yield
    MarionetteSession._instance = None


@pytest.mark.asyncio
async def test_ensure_connected_raises_when_port_closed():
    session = MarionetteSession.get()
    with patch("tb_marionette_mcp.session._port_open", return_value=False), pytest.raises(NotConnectedError):
        await session.ensure_connected()


@pytest.mark.asyncio
async def test_ensure_connected_starts_marionette_when_port_open():
    session = MarionetteSession.get()
    fake = MagicMock()
    with patch("tb_marionette_mcp.session._port_open", return_value=True), \
         patch("tb_marionette_mcp.session.Marionette", return_value=fake):
        await session.ensure_connected()
    fake.start_session.assert_called_once()


@pytest.mark.asyncio
async def test_call_wraps_wire_error():
    session = MarionetteSession.get()
    session._client = MagicMock()
    session._connected = True

    def blow():
        raise ConnectionResetError("dead")

    with patch("tb_marionette_mcp.session._port_open", return_value=False), pytest.raises(MarionetteWireError):
        await session.call(blow)


@pytest.mark.asyncio
async def test_call_with_context_switches_and_restores():
    session = MarionetteSession.get()
    client = MagicMock()
    client.current_context = "content"
    session._client = client
    session._connected = True

    def op():
        return "ok"

    result = await session.call(op, ctx="chrome")
    assert result == "ok"
    assert client.set_context.call_args_list[0].args[0] == "chrome"
    assert client.set_context.call_args_list[-1].args[0] == "content"
