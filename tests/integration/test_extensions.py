from __future__ import annotations

from pathlib import Path

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.extension_tools import (
    extension_install,
    extension_list,
    extension_uninstall,
)

XPI = Path(__file__).parents[1] / "fixtures" / "ext_hello.xpi"


@pytest.mark.asyncio
async def test_install_and_uninstall_temporary(session: MarionetteSession) -> None:
    result = await extension_install(xpi_path=str(XPI), temporary=True)
    assert result["addon_id"]
    listing = await extension_list()
    ids = {a["id"] for a in listing}
    assert result["addon_id"] in ids
    removed = await extension_uninstall(addon_id=result["addon_id"])
    assert removed["removed"] is True
