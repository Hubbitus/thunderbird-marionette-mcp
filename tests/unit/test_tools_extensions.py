from unittest.mock import MagicMock, patch

import pytest

from tb_marionette_mcp.errors import ExtensionInstallError
from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.extension_tools import (
    extension_install,
    extension_list,
    extension_reload,
    extension_uninstall,
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
async def test_install():
    fake_addons = MagicMock()
    fake_addons.install.return_value = "ext@example"
    with patch("tb_marionette_mcp.tools.extension_tools.Addons", return_value=fake_addons):
        result = await extension_install(xpi_path="/tmp/x.xpi", temporary=True)
    fake_addons.install.assert_called_once_with("/tmp/x.xpi", temp=True)
    assert result["addon_id"] == "ext@example"


@pytest.mark.asyncio
async def test_install_wraps_error():
    fake_addons = MagicMock()
    fake_addons.install.side_effect = RuntimeError("bad xpi")
    with patch(
        "tb_marionette_mcp.tools.extension_tools.Addons",
        return_value=fake_addons,
    ), pytest.raises(ExtensionInstallError):
        await extension_install(xpi_path="/tmp/x.xpi", temporary=True)


@pytest.mark.asyncio
async def test_uninstall():
    fake_addons = MagicMock()
    with patch("tb_marionette_mcp.tools.extension_tools.Addons", return_value=fake_addons):
        result = await extension_uninstall(addon_id="ext@example")
    fake_addons.uninstall.assert_called_once_with("ext@example")
    assert result["removed"] is True


@pytest.mark.asyncio
async def test_reload():
    fake_addons = MagicMock()
    fake_addons.install.return_value = "ext@example"
    with patch("tb_marionette_mcp.tools.extension_tools.Addons", return_value=fake_addons):
        result = await extension_reload(addon_id="ext@example", xpi_path="/tmp/x.xpi")
    fake_addons.uninstall.assert_called_once_with("ext@example")
    fake_addons.install.assert_called_once_with("/tmp/x.xpi", temp=True)
    assert result["addon_id"] == "ext@example"
    assert result["reloaded"] is True


@pytest.mark.asyncio
async def test_list():
    session = MarionetteSession.get()
    session._client.execute_async_script.return_value = [
        {"id": "a", "name": "A", "version": "1.0", "enabled": True, "temporary": False},
    ]
    result = await extension_list()
    assert result[0]["id"] == "a"
