"""Screenshot, page_source, url, title, console/marionette logs."""

from __future__ import annotations

from typing import Any, cast

from marionette_driver.marionette import WebElement

from tb_marionette_mcp.process import ProcessRegistry, stderr_tail
from tb_marionette_mcp.session import Context, MarionetteSession

_CHROME_SCREENSHOT_SCRIPT = """
let w = Services.wm.getMostRecentWindow(null);
if (!w) return "";
let doc = w.document;
let el = doc.documentElement;
let r = el.getBoundingClientRect();
let width = Math.ceil(r.width) || w.innerWidth || 1024;
let height = Math.ceil(r.height) || w.innerHeight || 768;
let canvas = doc.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
canvas.width = width;
canvas.height = height;
let ctx = canvas.getContext("2d");
ctx.drawWindow(w, 0, 0, width, height, "rgb(255,255,255)");
let uri = canvas.toDataURL("image/png");
return uri.replace(/^data:image\\/png;base64,/, "");
"""

_CONSOLE_SCRIPT = """
const {Services} = ChromeUtils.importESModule("resource://gre/modules/Services.sys.mjs");
const msgs = Services.console.getMessageArray() || [];
return msgs.map(m => ({
  level: (m.logLevel !== undefined) ? String(m.logLevel) :
         ((m.flags & 1) ? "warn" : "info"),
  message: (m.errorMessage || m.message || String(m)),
  timestamp: (m.timeStamp || Date.now()) / 1000,
  source: (m.sourceName || null),
}));
"""


async def screenshot(
    element_id: str | None = None,
    format: str = "png",
    full: bool = False,
) -> dict[str, str]:
    """Take screenshot.

    WebDriver `client.screenshot()` requires a browsing context (content tab)
    and fails on chrome-only XUL windows like TB's messenger.xhtml with
    `NoSuchWindowError: Browsing context has been discarded`. When no
    `element_id` is given and the top-level XUL window is chrome-only, fall
    back to a chrome-context canvas snapshot of the active window's
    `documentElement`.
    """
    session = MarionetteSession.get()

    def _shot() -> str:
        client = session.client
        if element_id:
            target = WebElement(client, element_id)
            return cast(str, client.screenshot(element=target, format=format, full=full))
        try:
            return cast(str, client.screenshot(format=format, full=full))
        except Exception:
            with client.using_context("chrome"):
                return cast(str, client.execute_script(_CHROME_SCREENSHOT_SCRIPT))

    data = await session.call(_shot)
    return {"data_base64": data, "format": format}


async def get_page_source(context: Context = "content") -> dict[str, str]:
    session = MarionetteSession.get()

    def _src() -> str:
        client = session.client
        try:
            return cast(str, client.page_source)
        except Exception:
            # Chrome-only window fallback: serialize documentElement
            return cast(
                str,
                client.execute_script(
                    "let w = Services.wm.getMostRecentWindow(null);"
                    "return w ? new XMLSerializer()."
                    "serializeToString(w.document.documentElement) : '';"
                ),
            )

    return {"source": await session.call(_src, ctx=context)}


async def get_current_url() -> dict[str, str]:
    session = MarionetteSession.get()

    def _url() -> str:
        client = session.client
        try:
            return cast(str, client.get_url())
        except Exception:
            return cast(
                str,
                client.execute_script(
                    "let w = Services.wm.getMostRecentWindow(null);"
                    "return w ? String(w.location.href) : '';"
                ),
            )

    return {"url": await session.call(_url, ctx="chrome")}


async def get_window_title() -> dict[str, str]:
    session = MarionetteSession.get()

    def _title() -> str:
        client = session.client
        try:
            return cast(str, client.title)
        except Exception:
            return cast(
                str,
                client.execute_script(
                    "let w = Services.wm.getMostRecentWindow(null);"
                    "return w ? String(w.document.title || '') : '';"
                ),
            )

    return {"title": await session.call(_title, ctx="chrome")}


async def get_console_logs(
    clear: bool = False, level: str | None = None
) -> list[dict[str, Any]]:
    session = MarionetteSession.get()

    def _logs() -> list[dict[str, Any]]:
        entries = cast(
            list[dict[str, Any]],
            session.client.execute_script(_CONSOLE_SCRIPT, script_args=[]),
        )
        if clear:
            session.client.execute_script(
                'ChromeUtils.importESModule("resource://gre/modules/Services.sys.mjs").'
                'Services.console.reset();'
            )
        return entries

    entries = await session.call(_logs, ctx="chrome")
    if level:
        entries = [e for e in entries if str(e.get("level", "")).lower() == level.lower()]
    return entries


async def get_marionette_log() -> dict[str, Any]:
    pid = ProcessRegistry.any_pid()
    if pid is None:
        return {"log": "", "available": False}
    return {"log": stderr_tail(pid), "available": True}
