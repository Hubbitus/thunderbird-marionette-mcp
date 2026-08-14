"""UI interaction tools."""

from __future__ import annotations

import contextlib
import time
from typing import Any

from marionette_driver.by import By
from marionette_driver.errors import NoSuchElementException
from marionette_driver.marionette import Marionette, WebElement

from tb_marionette_mcp.errors import ElementNotFoundError
from tb_marionette_mcp.errors import TimeoutError as TbTimeoutError
from tb_marionette_mcp.session import Context, MarionetteSession

_STRATEGY_MAP = {
    "id": By.ID,
    "css": By.CSS_SELECTOR,
    "xpath": By.XPATH,
    "link_text": By.LINK_TEXT,
    "partial_link_text": By.PARTIAL_LINK_TEXT,
    "tag_name": By.TAG_NAME,
    "class_name": By.CLASS_NAME,
    "name": By.NAME,
}


def _element(client: Marionette, element_id: str) -> WebElement:
    return WebElement(client, element_id)


async def find_element(
    strategy: str, selector: str, context: Context = "chrome", timeout: float = 5.0
) -> dict[str, str]:
    session = MarionetteSession.get()

    def _find() -> str:
        session.client.timeout.implicit = timeout
        by = _STRATEGY_MAP[strategy]
        try:
            el = session.client.find_element(by, selector)
        except NoSuchElementException as exc:
            raise ElementNotFoundError(
                f"element not found by {strategy}={selector!r}"
            ) from exc
        return str(el.id)

    element_id = await session.call(_find, ctx=context)
    return {"element_id": element_id}


async def find_elements(
    strategy: str, selector: str, context: Context = "chrome", timeout: float = 5.0
) -> dict[str, list[str]]:
    session = MarionetteSession.get()

    def _find() -> list[str]:
        session.client.timeout.implicit = timeout
        by = _STRATEGY_MAP[strategy]
        return [str(el.id) for el in session.client.find_elements(by, selector)]

    ids = await session.call(_find, ctx=context)
    return {"element_ids": ids}


async def click(element_id: str) -> dict[str, Any]:
    session = MarionetteSession.get()

    def _click() -> None:
        _element(session.client, element_id).click()

    await session.call(_click)
    return {}


async def type_text(element_id: str, text: str, clear: bool = False) -> dict[str, Any]:
    session = MarionetteSession.get()

    def _type() -> None:
        el = _element(session.client, element_id)
        if clear:
            el.clear()
        el.send_keys(text)

    await session.call(_type)
    return {}


async def get_text(element_id: str) -> dict[str, str]:
    session = MarionetteSession.get()

    def _get() -> str:
        return str(_element(session.client, element_id).text)

    return {"text": await session.call(_get)}


async def get_attribute(element_id: str, name: str) -> dict[str, str | None]:
    session = MarionetteSession.get()

    def _get() -> str | None:
        val = _element(session.client, element_id).get_attribute(name)
        return None if val is None else str(val)

    return {"value": await session.call(_get)}


async def get_property(element_id: str, name: str) -> dict[str, Any]:
    session = MarionetteSession.get()

    def _get() -> Any:
        return _element(session.client, element_id).get_property(name)

    return {"value": await session.call(_get)}


async def is_displayed(element_id: str) -> dict[str, bool]:
    session = MarionetteSession.get()

    def _check() -> bool:
        return bool(_element(session.client, element_id).is_displayed())

    return {"visible": await session.call(_check)}


async def list_windows() -> list[dict[str, str]]:
    """List all TB windows.

    For chrome-only apps like Thunderbird (messenger.xhtml), the WebDriver
    `window_handles` API returns `[]` because there are no content browser
    tabs. Fall back to enumerating `Services.wm` in chrome context, which
    returns actual XUL windows (messenger, compose, etc.).
    """
    session = MarionetteSession.get()

    def _list() -> list[dict[str, str]]:
        client = session.client
        out: list[dict[str, str]] = []
        try:
            original = client.current_window_handle
        except Exception:
            original = None
        for h in client.window_handles:
            try:
                client.switch_to_window(h)
                out.append(
                    {"handle": h, "title": client.title, "url": client.get_url()}
                )
            except Exception:
                out.append({"handle": h, "title": "", "url": ""})
        if original is not None:
            with contextlib.suppress(Exception):
                client.switch_to_window(original)
        if out:
            return out
        # Fallback: enumerate chrome windows via Services.wm
        wins = client.execute_script(
            "let out = [];"
            "let e = Services.wm.getEnumerator(null);"
            "while (e.hasMoreElements()) {"
            "  let w = e.getNext();"
            "  out.push({"
            "    handle: String(w.docShell.browsingContext.id),"
            "    title: String(w.document.title || ''),"
            "    url: String(w.location.href || '')"
            "  });"
            "} return out;"
        )
        return [
            {"handle": str(w["handle"]), "title": str(w["title"]), "url": str(w["url"])}
            for w in (wins or [])
        ]

    return await session.call(_list, ctx="chrome")


async def switch_to_window(handle: str) -> dict[str, Any]:
    """Switch to a window by handle.

    WebDriver `switch_to_window` accepts only handles from `window_handles`,
    which is empty for chrome-only apps like TB. `list_windows` falls back to
    `Services.wm` and returns `docShell.browsingContext.id` as handle. For
    those, focus the corresponding XUL window via chrome-context JS.
    """
    session = MarionetteSession.get()

    def _switch() -> None:
        client = session.client
        try:
            if handle in client.window_handles:
                client.switch_to_window(handle)
                return
        except Exception:
            pass
        with client.using_context("chrome"):
            client.execute_script(
                "let target = arguments[0];"
                "let e = Services.wm.getEnumerator(null);"
                "while (e.hasMoreElements()) {"
                "  let w = e.getNext();"
                "  if (String(w.docShell.browsingContext.id) === target) {"
                "    w.focus(); return true;"
                "  }"
                "} return false;",
                script_args=[handle],
            )

    await session.call(_switch)
    return {}


async def switch_to_frame(element_id: str) -> dict[str, Any]:
    session = MarionetteSession.get()

    def _switch() -> None:
        session.client.switch_to_frame(_element(session.client, element_id))

    await session.call(_switch)
    return {}


async def switch_to_default() -> dict[str, Any]:
    session = MarionetteSession.get()

    def _switch() -> None:
        session.client.switch_to_default_content()

    await session.call(_switch)
    return {}


async def wait_for_element(
    strategy: str,
    selector: str,
    context: Context = "chrome",
    timeout: float = 10.0,
    visible: bool = True,
) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            found = await find_element(strategy, selector, context, timeout=0.5)
        except ElementNotFoundError as exc:
            last_exc = exc
            time.sleep(0.2)
            continue
        if not visible:
            return found
        vis = await is_displayed(found["element_id"])
        if vis["visible"]:
            return found
        time.sleep(0.2)
    raise TbTimeoutError(
        f"wait_for_element timeout for {strategy}={selector!r}",
        details={"last_error": str(last_exc) if last_exc else None},
    )
