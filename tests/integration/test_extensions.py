from __future__ import annotations

from pathlib import Path

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.extension_tools import (
    extension_install,
    extension_list,
    extension_reload,
    extension_uninstall,
)

XPI = Path(__file__).parents[1] / "fixtures" / "ext_hello.xpi"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_install_and_uninstall_temporary(session: MarionetteSession) -> None:
    result = await extension_install(xpi_path=str(XPI), temporary=True)
    assert result["addon_id"]
    listing = await extension_list()
    ids = {a["id"] for a in listing}
    assert result["addon_id"] in ids
    removed = await extension_uninstall(addon_id=result["addon_id"])
    assert removed["removed"] is True


@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_reload_preserves_addon_id(session: MarionetteSession) -> None:
    installed = await extension_install(xpi_path=str(XPI), temporary=True)
    addon_id = installed["addon_id"]
    try:
        reloaded = await extension_reload(addon_id=addon_id, xpi_path=str(XPI))
        assert reloaded["reloaded"] is True
        assert reloaded["addon_id"] == addon_id
        listing = await extension_list()
        assert any(a["id"] == addon_id for a in listing)
    finally:
        await extension_uninstall(addon_id=addon_id)
