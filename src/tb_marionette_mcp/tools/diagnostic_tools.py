"""Screenshot, page_source, url, title, console/marionette logs."""

from __future__ import annotations

from typing import Any, cast

from marionette_driver.marionette import WebElement

from tb_marionette_mcp.process import ProcessRegistry, stderr_tail
from tb_marionette_mcp.session import Context, MarionetteSession

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
    session = MarionetteSession.get()

    def _shot() -> str:
        client = session.client
        target: WebElement | None = (
            WebElement(client, element_id) if element_id else None
        )
        return cast(str, client.screenshot(element=target, format=format, full=full))

    data = await session.call(_shot)
    return {"data_base64": data, "format": format}


async def get_page_source(context: Context = "content") -> dict[str, str]:
    session = MarionetteSession.get()

    def _src() -> str:
        return cast(str, session.client.page_source)

    return {"source": await session.call(_src, ctx=context)}


async def get_current_url() -> dict[str, str]:
    session = MarionetteSession.get()

    def _url() -> str:
        return cast(str, session.client.get_url())

    return {"url": await session.call(_url)}


async def get_window_title() -> dict[str, str]:
    session = MarionetteSession.get()

    def _title() -> str:
        return cast(str, session.client.title)

    return {"title": await session.call(_title)}


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
