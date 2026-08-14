from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.ui_tools import find_element, list_windows


@pytest.mark.asyncio
async def test_list_windows(session: MarionetteSession) -> None:
    # Headless TB without mail account has no content browser windows,
    # so window_handles (content-scope) may be empty. Just verify shape.
    windows = await list_windows()
    assert isinstance(windows, list)
    for w in windows:
        assert set(w.keys()) == {"handle", "title", "url"}


@pytest.mark.asyncio
async def test_find_main_document(session: MarionetteSession) -> None:
    result = await find_element(
        strategy="css", selector="body, window", context="chrome", timeout=5.0
    )
    assert result["element_id"]
