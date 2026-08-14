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
    from unittest.mock import patch

    session = MarionetteSession.get()
    seq = MagicMock()
    seq.key_down.return_value = seq
    seq.key_up.return_value = seq
    with patch("tb_marionette_mcp.tools.key_tools.ActionSequence",
               return_value=seq) as ctor:
        await send_keys(keys="hi")
    ctor.assert_called_once_with(session._client, "key", "keyboard1")
    assert seq.key_down.call_count == 2
    assert seq.key_up.call_count == 2
    seq.perform.assert_called_once()


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
    from unittest.mock import patch

    seq = MagicMock()
    seq.key_down.return_value = seq
    seq.key_up.return_value = seq
    with patch("tb_marionette_mcp.tools.key_tools.ActionSequence",
               return_value=seq):
        await send_hotkey(chord="Ctrl+Shift+N")
    seq.perform.assert_called_once()
    # 2 mods down + 1 key down = 3 key_down calls
    assert seq.key_down.call_count == 3
    # 1 key up + 2 mods up = 3 key_up calls
    assert seq.key_up.call_count == 3


@pytest.mark.asyncio
async def test_send_keys_falls_back_to_chrome_when_actions_fail():
    from contextlib import contextmanager
    from unittest.mock import patch

    session = MarionetteSession.get()
    used: list[str] = []

    @contextmanager
    def _using_context(name: str):
        used.append(name)
        yield

    session._client.using_context = _using_context
    with patch("tb_marionette_mcp.tools.key_tools.ActionSequence",
               side_effect=Exception("Browsing context discarded")):
        await send_keys(keys="ab")
    assert used == ["chrome"]
    assert session._client.execute_script.call_count == 2
    call = session._client.execute_script.call_args_list[0]
    assert call.kwargs["script_args"][0] == "a"
    assert call.kwargs["script_args"][1] == {
        "ctrl": False, "shift": False, "alt": False, "meta": False,
    }


@pytest.mark.asyncio
async def test_send_hotkey_falls_back_to_chrome_when_actions_fail():
    from contextlib import contextmanager
    from unittest.mock import patch

    session = MarionetteSession.get()
    used: list[str] = []

    @contextmanager
    def _using_context(name: str):
        used.append(name)
        yield

    session._client.using_context = _using_context
    with patch("tb_marionette_mcp.tools.key_tools.ActionSequence",
               side_effect=Exception("Browsing context discarded")):
        await send_hotkey(chord="Ctrl+Shift+N")
    assert used == ["chrome"]
    session._client.execute_script.assert_called_once()
    call = session._client.execute_script.call_args
    assert call.kwargs["script_args"][0] == "n"
    flags = call.kwargs["script_args"][1]
    assert flags["ctrl"] is True
    assert flags["shift"] is True
    assert flags["alt"] is False


def test_parse_chord_unknown_modifier():
    with pytest.raises(InvalidArgumentError, match="unknown modifier"):
        parse_chord("Nope+A")


def test_parse_chord_unknown_multichar_key():
    with pytest.raises(InvalidArgumentError, match="unknown key"):
        parse_chord("foobar")


def test_element_helper_constructs_webelement():
    from marionette_driver.marionette import WebElement

    from tb_marionette_mcp.tools.key_tools import _element
    client = MagicMock()
    el = _element(client, "elem-99")
    assert isinstance(el, WebElement)
    assert el.id == "elem-99"
