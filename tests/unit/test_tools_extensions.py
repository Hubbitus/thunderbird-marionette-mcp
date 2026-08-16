from unittest.mock import MagicMock, patch

import pytest

from tb_marionette_mcp.errors import ExtensionInstallError
from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.extension_tools import (
    extension_install,
    extension_list,
    extension_reload,
    extension_trigger_command,
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


@pytest.mark.asyncio
async def test_trigger_command_success():
    """extension_trigger_command must call execute_async_script in chrome
    context, passing addon_id + command_name, and return {"triggered": True}
    when the JS payload reports success."""
    session = MarionetteSession.get()
    session._client.execute_async_script.return_value = {"ok": True}
    result = await extension_trigger_command(
        addon_id="ext@example", command_name="open-note-editor"
    )
    session._client.execute_async_script.assert_called_once()
    call = session._client.execute_async_script.call_args
    assert call.kwargs["script_args"] == ["ext@example", "open-note-editor"]
    assert result == {"triggered": True}


@pytest.mark.asyncio
async def test_trigger_command_extension_not_found():
    """If the JS payload reports the extension is not registered, raise."""
    from tb_marionette_mcp.errors import InvalidArgumentError

    session = MarionetteSession.get()
    session._client.execute_async_script.return_value = {
        "ok": False,
        "error": "extension not found",
    }
    with pytest.raises(InvalidArgumentError):
        await extension_trigger_command(
            addon_id="missing@example", command_name="foo"
        )


@pytest.mark.asyncio
async def test_trigger_command_api_not_loaded():
    from tb_marionette_mcp.errors import InvalidArgumentError

    session = MarionetteSession.get()
    session._client.execute_async_script.return_value = {
        "ok": False,
        "error": "commands API not loaded",
    }
    with pytest.raises(InvalidArgumentError):
        await extension_trigger_command(
            addon_id="ext@example", command_name="foo"
        )
