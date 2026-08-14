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


def test_port_open_returns_false_on_oserror():
    from tb_marionette_mcp.session import _port_open
    with patch("tb_marionette_mcp.session.socket.create_connection",
               side_effect=OSError):
        assert _port_open("127.0.0.1", 1) is False


def test_port_open_returns_true_when_listener_up():
    import socket as _s

    from tb_marionette_mcp.session import _port_open
    srv = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert _port_open("127.0.0.1", port) is True
    finally:
        srv.close()


def test_client_property_raises_when_none():
    session = MarionetteSession.get()
    session._client = None
    with pytest.raises(NotConnectedError):
        _ = session.client


@pytest.mark.asyncio
async def test_call_retry_after_wire_error_succeeds():
    session = MarionetteSession.get()
    session._client = MagicMock()
    session._connected = True

    calls = {"n": 0}

    def op():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionResetError("dead")
        return "recovered"

    reconnected_client = MagicMock()
    with patch("tb_marionette_mcp.session._port_open", return_value=True), \
         patch("tb_marionette_mcp.session.Marionette", return_value=reconnected_client):
        result = await session.call(op)
    assert result == "recovered"
    assert calls["n"] == 2
