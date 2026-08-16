"""Non-fixture helpers used by integration tests."""

from __future__ import annotations

from tb_marionette_mcp.session import MarionetteSession


async def close_extra_windows(session: MarionetteSession) -> None:
    """Close any XUL windows opened during a test, keeping the main 3-pane."""

    def _close() -> None:
        client = session.client
        with client.using_context("chrome"):
            client.execute_script(
                """
                let e = Services.wm.getEnumerator(null);
                let toClose = [];
                while (e.hasMoreElements()) {
                    let w = e.getNext();
                    let uri = w.location.href || '';
                    if (uri.includes('messenger.xhtml')) continue;
                    toClose.push(w);
                }
                for (let w of toClose) {
                    try { w.close(); } catch (_) { /* ignore */ }
                }
                """
            )

    await session.call(_close)
