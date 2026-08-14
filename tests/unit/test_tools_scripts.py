from unittest.mock import MagicMock

import pytest

from tb_marionette_mcp.errors import TimeoutError as TbTimeoutError
from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.script_tools import execute_script, wait_for_condition


@pytest.fixture(autouse=True)
def reset():
    MarionetteSession._instance = None
    session = MarionetteSession.get()
    session._client = MagicMock()
    session._connected = True
    yield
    MarionetteSession._instance = None


@pytest.mark.asyncio
async def test_execute_sync():
    session = MarionetteSession.get()
    session._client.execute_script.return_value = 42
    result = await execute_script(script="return 42", args=[], context="chrome")
    assert result["result"] == 42
    session._client.execute_script.assert_called_once()


@pytest.mark.asyncio
async def test_execute_async():
    session = MarionetteSession.get()
    session._client.execute_async_script.return_value = "ok"
    result = await execute_script(
        script="cb()", args=[1], context="chrome", async_=True, timeout=5
    )
    assert result["result"] == "ok"
    session._client.execute_async_script.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_condition_success():
    session = MarionetteSession.get()
    responses = iter([None, None, 1])
    session._client.execute_script.side_effect = lambda *a, **k: next(responses)
    result = await wait_for_condition(
        script="return x", args=[], context="chrome", timeout=2, poll_interval=0.01
    )
    assert result["result"] == 1


@pytest.mark.asyncio
async def test_wait_for_condition_timeout():
    session = MarionetteSession.get()
    session._client.execute_script.return_value = None
    with pytest.raises(TbTimeoutError):
        await wait_for_condition(
            script="return false", args=[], context="chrome",
            timeout=0.2, poll_interval=0.05,
        )
