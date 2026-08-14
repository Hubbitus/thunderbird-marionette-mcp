import base64
from unittest.mock import MagicMock, patch

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.diagnostic_tools import (
    get_console_logs,
    get_current_url,
    get_marionette_log,
    get_page_source,
    get_window_title,
    screenshot,
)


@pytest.fixture(autouse=True)
def reset():
    MarionetteSession._instance = None
    session = MarionetteSession.get()
    session._client = MagicMock()
    session._connected = True
    yield
    MarionetteSession._instance = None


@pytest.mark.asyncio
async def test_screenshot_full():
    session = MarionetteSession.get()
    session._client.screenshot.return_value = base64.b64encode(b"data").decode()
    result = await screenshot(element_id=None, format="png", full=True)
    assert result["data_base64"]
    assert result["format"] == "png"


@pytest.mark.asyncio
async def test_page_source():
    session = MarionetteSession.get()
    session._client.page_source = "<html/>"
    result = await get_page_source(context="content")
    assert result["source"] == "<html/>"


@pytest.mark.asyncio
async def test_current_url():
    session = MarionetteSession.get()
    session._client.get_url.return_value = "https://x"
    result = await get_current_url()
    assert result["url"] == "https://x"


@pytest.mark.asyncio
async def test_window_title():
    session = MarionetteSession.get()
    session._client.title = "Inbox"
    result = await get_window_title()
    assert result["title"] == "Inbox"


@pytest.mark.asyncio
async def test_console_logs_filter():
    session = MarionetteSession.get()
    session._client.execute_script.return_value = [
        {"level": "info", "message": "a", "timestamp": 1.0, "source": None},
        {"level": "error", "message": "b", "timestamp": 2.0, "source": None},
    ]
    result = await get_console_logs(clear=False, level="error")
    assert len(result) == 1
    assert result[0]["level"] == "error"


@pytest.mark.asyncio
async def test_marionette_log_unavailable():
    with patch("tb_marionette_mcp.tools.diagnostic_tools.ProcessRegistry.any_pid",
               return_value=None):
        result = await get_marionette_log()
    assert result["available"] is False
    assert result["log"] == ""


@pytest.mark.asyncio
async def test_console_logs_clear_calls_reset():
    session = MarionetteSession.get()
    session._client.execute_script.return_value = []
    await get_console_logs(clear=True, level=None)
    # execute_script called twice: fetch + Services.console.reset()
    assert session._client.execute_script.call_count == 2
    reset_call = session._client.execute_script.call_args_list[1]
    assert "Services.console.reset" in reset_call.args[0]


@pytest.mark.asyncio
async def test_marionette_log_available():
    with patch("tb_marionette_mcp.tools.diagnostic_tools.ProcessRegistry.any_pid",
               return_value=1234), \
         patch("tb_marionette_mcp.tools.diagnostic_tools.stderr_tail",
               return_value="stderr content"):
        result = await get_marionette_log()
    assert result["available"] is True
    assert result["log"] == "stderr content"


@pytest.mark.asyncio
async def test_screenshot_of_element():
    session = MarionetteSession.get()
    session._client.screenshot.return_value = "b64data"
    result = await screenshot(element_id="elem-1", format="png", full=False)
    assert result["data_base64"] == "b64data"
    call = session._client.screenshot.call_args
    assert call.kwargs["element"] is not None
