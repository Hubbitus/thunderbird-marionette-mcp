from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.script_tools import execute_script


@pytest.mark.asyncio
async def test_execute_script_chrome_returns_appinfo_version(
    session: MarionetteSession,
) -> None:
    result = await execute_script(
        script=(
            'return Components.classes["@mozilla.org/xre/app-info;1"]'
            '.getService(Components.interfaces.nsIXULAppInfo).version;'
        ),
        args=[],
        context="chrome",
    )
    assert result["result"]
    assert result["result"][0].isdigit()
