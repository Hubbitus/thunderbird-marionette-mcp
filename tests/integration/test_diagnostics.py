from __future__ import annotations

import base64

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


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_screenshot_returns_png_base64(session: MarionetteSession) -> None:
    result = await screenshot()
    assert result["data_base64"]
    data = base64.b64decode(result["data_base64"])
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_page_source_returns_xul(session: MarionetteSession) -> None:
    result = await get_page_source(context="chrome")
    assert result["source"]
    assert "window" in result["source"].lower()


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_current_url_returns_string(session: MarionetteSession) -> None:
    result = await get_current_url()
    assert isinstance(result["url"], str)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_window_title_returns_nonempty(session: MarionetteSession) -> None:
    result = await get_window_title()
    assert isinstance(result["title"], str)
    assert result["title"]


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_console_logs_returns_list(session: MarionetteSession) -> None:
    result = await get_console_logs()
    assert isinstance(result, list)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_marionette_log_reads_stderr(session: MarionetteSession) -> None:
    result = await get_marionette_log()
    assert "log" in result
    assert isinstance(result["log"], str)
