from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.process_tools import thunderbird_status


@pytest.mark.asyncio
async def test_status_running(session: MarionetteSession) -> None:
    s = await thunderbird_status()
    assert s["running"] is True or s["connected"] is True
