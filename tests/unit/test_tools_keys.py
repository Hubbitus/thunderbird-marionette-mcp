from unittest.mock import MagicMock

import pytest
from marionette_driver.keys import Keys

from tb_marionette_mcp.errors import InvalidArgumentError
from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.key_tools import parse_chord, send_hotkey, send_keys


@pytest.fixture(autouse=True)
def reset():
    MarionetteSession._instance = None
    session = MarionetteSession.get()
    session._client = MagicMock()
    session._connected = True
    yield
    MarionetteSession._instance = None


def test_parse_chord_single_key():
    mods, key = parse_chord("Enter")
    assert mods == []
    assert key == Keys.ENTER


def test_parse_chord_ctrl_shift_n():
    mods, key = parse_chord("Ctrl+Shift+N")
    assert set(mods) == {Keys.CONTROL, Keys.SHIFT}
    assert key == "n"


def test_parse_chord_case_insensitive():
    mods, key = parse_chord("ctrl+alt+f4")
    assert set(mods) == {Keys.CONTROL, Keys.ALT}
    assert key == Keys.F4


def test_parse_chord_cmd_alias_for_meta():
    mods, _ = parse_chord("Cmd+K")
    assert mods == [Keys.META]


def test_parse_chord_invalid_key():
    with pytest.raises(InvalidArgumentError):
        parse_chord("Ctrl+Nonsense")


def test_parse_chord_empty():
    with pytest.raises(InvalidArgumentError):
        parse_chord("")


@pytest.mark.asyncio
async def test_send_keys_global():
    session = MarionetteSession.get()
    actions_ctx = MagicMock()
    session._client.actions.key_action.return_value = actions_ctx
    actions_ctx.key_down.return_value = actions_ctx
    actions_ctx.key_up.return_value = actions_ctx
    await send_keys(keys="hi")
    session._client.actions.key_action.assert_called_once()
    actions_ctx.perform.assert_called_once()


@pytest.mark.asyncio
async def test_send_keys_to_element():
    from unittest.mock import patch

    from tb_marionette_mcp.tools import key_tools

    el = MagicMock()
    with patch.object(key_tools, "_element", return_value=el):
        await send_keys(keys="x", element_id="e1")
    el.send_keys.assert_called_once_with("x")


@pytest.mark.asyncio
async def test_send_hotkey_dispatches_actions():
    session = MarionetteSession.get()
    actions_ctx = MagicMock()
    session._client.actions.key_action.return_value = actions_ctx
    actions_ctx.key_down.return_value = actions_ctx
    actions_ctx.key_up.return_value = actions_ctx
    await send_hotkey(chord="Ctrl+Shift+N")
    actions_ctx.perform.assert_called_once()
