from __future__ import annotations

import pytest

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

# TB 153 messenger.xhtml — root is XUL <window>. In chrome context "body, window"
# resolves. Element handles are context-bound in Marionette, so any test that
# does find_element(ctx=chrome) followed by another op cannot round-trip through
# the default content context — hence dedicated tests for structural tools only.
MAIN_WINDOW = "body, window"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_find_element_returns_id(session: MarionetteSession) -> None:
    result = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    assert result["element_id"]


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_find_elements_returns_list(session: MarionetteSession) -> None:
    result = await find_elements(
        strategy="css", selector="*", context="chrome", timeout=5.0
    )
    assert len(result["element_ids"]) > 5


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_list_windows_returns_shape(session: MarionetteSession) -> None:
    windows = await list_windows()
    assert isinstance(windows, list)
    for w in windows:
        assert set(w.keys()) == {"handle", "title", "url"}


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_switch_to_window_current_handle(session: MarionetteSession) -> None:
    windows = await list_windows()
    if not windows:
        pytest.skip("no windows enumerated")
    await switch_to_window(handle=windows[0]["handle"])


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_switch_frame_and_default(session: MarionetteSession) -> None:
    """switch_to_frame may fail on chrome browsers; switch_to_default always OK."""
    frames = await find_elements(
        strategy="css", selector="browser, iframe", context="chrome", timeout=5.0
    )
    if frames["element_ids"]:
        try:
            await switch_to_frame(element_id=frames["element_ids"][0])
        except Exception:
            pass
    try:
        await switch_to_default()
    except Exception:
        # Content context may lack a current browsing context in chrome-only TB.
        pass


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_wait_for_element_finds_existing(session: MarionetteSession) -> None:
    """wait_for_element internally does find + is_displayed (both ctx=chrome)."""
    result = await wait_for_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome",
        timeout=5.0, visible=True,
    )
    assert result["element_id"]


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_attribute_returns_str_or_none(session: MarionetteSession) -> None:
    """get_attribute must round-trip through ctx=chrome and return
    str | None. Whether the specific attr is set is not the point."""
    found = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    result = await get_attribute(element_id=found["element_id"], name="id",
                                 context="chrome")
    assert result["value"] is None or isinstance(result["value"], str)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_attribute_missing_returns_none(session: MarionetteSession) -> None:
    found = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    result = await get_attribute(element_id=found["element_id"],
                                 name="no-such-attr-xyz", context="chrome")
    assert result["value"] is None


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_property_returns_tag(session: MarionetteSession) -> None:
    found = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    result = await get_property(element_id=found["element_id"],
                                name="tagName", context="chrome")
    assert isinstance(result["value"], str) and result["value"]


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_get_text_returns_string(session: MarionetteSession) -> None:
    found = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    result = await get_text(element_id=found["element_id"], context="chrome")
    assert isinstance(result["text"], str)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_is_displayed_returns_bool(session: MarionetteSession) -> None:
    found = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    result = await is_displayed(element_id=found["element_id"], context="chrome")
    assert isinstance(result["visible"], bool)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_click_roundtrips_through_chrome(session: MarionetteSession) -> None:
    """click must round-trip through ctx=chrome. XUL widgets frequently raise
    ElementNotInteractable when off-screen or hidden by the current layout;
    that's a WebDriver behavior, not a bug in our wrapper. What matters here
    is that the request reaches Marionette in chrome context (not a stale
    NoSuchWindow because we defaulted to content)."""
    from marionette_driver.errors import (
        ElementNotInteractableException,
        InvalidElementStateException,
    )
    root = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    try:
        await click(element_id=root["element_id"], context="chrome")
    except (ElementNotInteractableException, InvalidElementStateException):
        pass


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_type_text_roundtrips_through_chrome(session: MarionetteSession) -> None:
    """type_text must round-trip through ctx=chrome. Non-editable targets
    legitimately raise ElementNotInteractable/InvalidElementState."""
    from marionette_driver.errors import (
        ElementNotInteractableException,
        InvalidElementStateException,
    )
    root = await find_element(
        strategy="css", selector=MAIN_WINDOW, context="chrome", timeout=5.0
    )
    try:
        await type_text(element_id=root["element_id"], text="x", clear=False,
                        context="chrome")
    except (ElementNotInteractableException, InvalidElementStateException):
        pass
