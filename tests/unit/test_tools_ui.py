from unittest.mock import MagicMock

import pytest

from tb_marionette_mcp.errors import ElementNotFoundError
from tb_marionette_mcp.errors import TimeoutError as TbTimeoutError
from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.ui_tools import (
    click,
    find_element,
    find_elements,
    get_attribute,
    get_property,
    get_text,
    is_displayed,
    list_windows,
    switch_to_default,
    switch_to_frame,
    switch_to_window,
    type_text,
    wait_for_element,
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
async def test_find_element_success():
    session = MarionetteSession.get()
    el = MagicMock()
    el.id = "elem-1"
    session._client.find_element.return_value = el
    result = await find_element(strategy="id", selector="foo", context="chrome", timeout=5)
    assert result["element_id"] == "elem-1"
    assert session._client.timeout.implicit == 5


@pytest.mark.asyncio
async def test_find_element_not_found():
    from marionette_driver.errors import NoSuchElementException

    session = MarionetteSession.get()
    session._client.find_element.side_effect = NoSuchElementException("no")
    with pytest.raises(ElementNotFoundError):
        await find_element(strategy="css", selector="#x", context="chrome", timeout=1)


@pytest.mark.asyncio
async def test_find_elements():
    session = MarionetteSession.get()
    e1, e2 = MagicMock(), MagicMock()
    e1.id, e2.id = "a", "b"
    session._client.find_elements.return_value = [e1, e2]
    result = await find_elements(strategy="css", selector=".x", context="chrome", timeout=1)
    assert result["element_ids"] == ["a", "b"]


@pytest.mark.asyncio
async def test_click_calls_element_click():
    el = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        await click(element_id="x")
    el.click.assert_called_once()


@pytest.mark.asyncio
async def test_type_text_clear():
    el = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        await type_text(element_id="x", text="hi", clear=True)
    el.clear.assert_called_once()
    el.send_keys.assert_called_once_with("hi")


@pytest.mark.asyncio
async def test_get_text():
    el = MagicMock()
    el.text = "hello"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        result = await get_text(element_id="x")
    assert result["text"] == "hello"


@pytest.mark.asyncio
async def test_get_attribute():
    el = MagicMock()
    el.get_attribute.return_value = "val"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        result = await get_attribute(element_id="x", name="href")
    assert result["value"] == "val"


@pytest.mark.asyncio
async def test_is_displayed():
    el = MagicMock()
    el.is_displayed.return_value = True
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        result = await is_displayed(element_id="x")
    assert result["visible"] is True


@pytest.mark.asyncio
async def test_list_windows():
    session = MarionetteSession.get()
    session._client.window_handles = ["h1", "h2"]
    session._client.current_window_handle = "h1"

    def switch(h):
        session._client.current_window_handle = h

    session._client.switch_to_window.side_effect = switch
    session._client.title = "T"
    session._client.get_url.return_value = "https://x"
    result = await list_windows()
    assert len(result) == 2
    assert result[0]["handle"] == "h1"


@pytest.mark.asyncio
async def test_switch_to_window():
    session = MarionetteSession.get()
    await switch_to_window(handle="abc")
    session._client.switch_to_window.assert_called_once_with("abc")


@pytest.mark.asyncio
async def test_switch_to_frame():
    session = MarionetteSession.get()
    el = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        await switch_to_frame(element_id="x")
    session._client.switch_to_frame.assert_called_once_with(el)


@pytest.mark.asyncio
async def test_switch_to_default():
    session = MarionetteSession.get()
    await switch_to_default()
    session._client.switch_to_default_content.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_element_returns_id():
    session = MarionetteSession.get()
    el = MagicMock()
    el.id = "z"
    session._client.find_element.return_value = el
    el.is_displayed.return_value = True
    result = await wait_for_element(
        strategy="css", selector="#z", context="chrome", timeout=1, visible=True
    )
    assert result["element_id"] == "z"


@pytest.mark.asyncio
async def test_get_property():
    el = MagicMock()
    el.get_property.return_value = {"nested": 1}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        result = await get_property(element_id="x", name="dataset")
    assert result["value"] == {"nested": 1}


@pytest.mark.asyncio
async def test_list_windows_current_handle_raises():
    session = MarionetteSession.get()
    type(session._client).current_window_handle = property(
        lambda self: (_ for _ in ()).throw(Exception("no window"))
    )
    session._client.window_handles = []
    result = await list_windows()
    assert result == []


@pytest.mark.asyncio
async def test_list_windows_switch_fails_returns_empty_meta():
    session = MarionetteSession.get()
    session._client.window_handles = ["h1"]
    session._client.current_window_handle = "h1"
    session._client.switch_to_window.side_effect = Exception("dead window")
    result = await list_windows()
    assert result == [{"handle": "h1", "title": "", "url": ""}]


@pytest.mark.asyncio
async def test_wait_for_element_invisible_returns_when_visible_false():
    session = MarionetteSession.get()
    el = MagicMock()
    el.id = "inv"
    session._client.find_element.return_value = el
    el.is_displayed.return_value = False
    result = await wait_for_element(
        strategy="css", selector="#inv", context="chrome", timeout=1, visible=False
    )
    assert result["element_id"] == "inv"


@pytest.mark.asyncio
async def test_wait_for_element_retries_then_times_out():
    from marionette_driver.errors import NoSuchElementException

    session = MarionetteSession.get()
    session._client.find_element.side_effect = NoSuchElementException("no")
    with pytest.raises(TbTimeoutError):
        await wait_for_element(
            strategy="css", selector="#gone", context="chrome",
            timeout=0.4, visible=True,
        )


@pytest.mark.asyncio
async def test_wait_for_element_invisible_loops_then_times_out():
    session = MarionetteSession.get()
    el = MagicMock()
    el.id = "hidden"
    el.is_displayed.return_value = False
    session._client.find_element.return_value = el
    # _element is used by both find (implicit via client) and is_displayed;
    # patch it so is_displayed sees an element that reports invisible.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tb_marionette_mcp.tools.ui_tools._element",
            lambda _client, _id: el,
        )
        with pytest.raises(TbTimeoutError):
            await wait_for_element(
                strategy="css", selector="#hidden", context="chrome",
                timeout=0.4, visible=True,
            )
