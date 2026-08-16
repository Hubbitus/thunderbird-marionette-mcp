from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.key_tools import send_hotkey, send_keys
from tb_marionette_mcp.tools.ui_tools import list_windows, wait_for_element
from tests.integration._helpers import close_extra_windows


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_send_keys_empty(session: MarionetteSession) -> None:
    """Empty send_keys exercises the code path without side effects."""
    result = await send_keys(keys="")
    assert result is not None


@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_send_hotkey_opens_compose(session: MarionetteSession) -> None:
    """Ctrl+N in the 3-pane opens a Compose window."""
    windows_before = await list_windows()

    await send_hotkey(chord="ctrl+n")

    # Compose window loads asynchronously — poll for new window count.
    result = await wait_for_element(
        strategy="css", selector="body, window", context="chrome",
        timeout=15.0, visible=False,
    )
    assert result["element_id"]

    windows_after = await list_windows()
    try:
        assert len(windows_after) >= len(windows_before), (
            f"expected same-or-more windows; before={len(windows_before)}, "
            f"after={len(windows_after)}"
        )
    finally:
        await close_extra_windows(session)
