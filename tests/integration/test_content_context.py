"""Verify UI tools work against a real content page (context='content').

Opens a local HTML fixture in a Thunderbird contentTab via
`tabmail.openTab('contentTab', {url})`, then exercises find_element /
click / type_text / get_text / get_attribute / get_property /
is_displayed with `context='content'` and asserts DOM round-trips.

Existing UI tests (test_ui.py) all run against messenger.xhtml (XUL,
chrome-only). This suite is the counterpart proving the same tools
work in the WebDriver-native content browsing context — which was
promoted to a non-default via the v0.2.0 `context` parameter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.script_tools import execute_script
from tb_marionette_mcp.tools.ui_tools import (
    click,
    find_element,
    get_attribute,
    get_property,
    get_text,
    is_displayed,
    type_text,
)

HTML = Path(__file__).parents[1] / "fixtures" / "content_page.html"


_TABMANAGER_SHIM_JS = r"""
    // TB 153 Marionette bug: TabManager.getTabBrowser() (in
    // shared/TabManager.sys.mjs) returns null for anything that is not
    // Firefox or Android — Thunderbird falls through, so WebDriver window
    // handles are empty and switch_to_window never sees tabmail contentTabs.
    //
    // Monkey-patch the singleton to return a fake tabbrowser wrapping
    // mail:3pane's <tabmail>, exposing tabs / selectedTab / getTabForBrowser
    // in the shape Marionette expects. Idempotent — safe to re-run.
    let TabManagerMod = ChromeUtils.importESModule(
        "chrome://remote/content/shared/TabManager.sys.mjs");
    let TabManager = TabManagerMod.TabManager;
    if (TabManager.__tbPatched !== 2) {
        let orig = TabManager.getTabBrowser.bind(TabManager);
        TabManager.getTabBrowser = function (win) {
            let r = orig(win);
            if (r) return r;
            if (!win || !win.document) return null;
            let wt = win.document.documentElement.getAttribute("windowtype");
            if (wt !== "mail:3pane") return null;
            let tabmail = win.document.getElementById("tabmail");
            if (!tabmail) return null;
            return {
                get tabs() {
                    return tabmail.tabInfo.filter(t =>
                        t.browser &&
                        t.browser.getAttribute("type") === "content");
                },
                get selectedTab() { return tabmail.selectedTab; },
                set selectedTab(t) { tabmail.switchToTab(t); },
                getTabForBrowser(browser) {
                    for (let t of tabmail.tabInfo) {
                        if (t.browser === browser) return t;
                    }
                    return null;
                },
                addTab(url, opts) {
                    return tabmail.openTab("contentTab",
                        {url: url || "about:blank"});
                },
                removeTab(t, opts) { tabmail.closeTab(t); },
                // Marionette driver.sys.mjs (#startObservingWindow /
                // #stopObservingWindow) calls addEventListener /
                // removeEventListener("XULFrameLoaderCreated") on the
                // tabbrowser. Real Firefox <tabbrowser> is an EventTarget;
                // our shim is a plain object, so provide no-op stubs to
                // avoid TypeError that crashes TB on session teardown.
                addEventListener() {},
                removeEventListener() {},
            };
        };
        TabManager.__tbPatched = 2;
    }
    return {patched: true};
"""


async def _apply_tabmanager_shim() -> None:
    """Install monkey-patch on Marionette's TabManager so tabmail contentTabs
    become visible as WebDriver window handles. Idempotent."""
    await execute_script(
        script=_TABMANAGER_SHIM_JS, args=[], context="chrome",
        async_=False, timeout=10.0,
    )


async def _open_content_fixture() -> None:
    """Load the HTML fixture into a tabmail contentTab and switch WebDriver
    to it. Requires `_apply_tabmanager_shim()` first — otherwise the tab
    stays invisible to `client.window_handles`.

    Idempotent — activates the existing tab if one is already open.
    """
    import asyncio as _asyncio

    url = HTML.resolve().as_uri()
    session = MarionetteSession.get()

    await _apply_tabmanager_shim()

    await execute_script(
        script=r"""
            let [url] = arguments;
            let mainWin = Services.wm.getMostRecentWindow('mail:3pane');
            let tabmail = mainWin.document.getElementById('tabmail');
            let info;
            let reused = false;
            for (let tab of tabmail.tabInfo) {
                if (tab.browser && tab.browser.currentURI &&
                    tab.browser.currentURI.spec === url) {
                    tabmail.switchToTab(tab);
                    info = tab;
                    reused = true;
                    break;
                }
            }
            if (!info) {
                info = tabmail.openTab('contentTab', {url});
            }
            // Marionette's NavigableManager.getIdForBrowser requires
            // browser.permanentKey; TB's specialTabs.js does not set one.
            // Attach a stable object so the WebDriver window handle is
            // deterministic across queries.
            if (info && info.browser && !info.browser.permanentKey) {
                info.browser.permanentKey =
                    new (Cu.getGlobalForObject(Services).Object)();
            }
            return {reused};
        """,
        args=[url], context="chrome", async_=False, timeout=10.0,
    )

    # Poll until the currently-selected tab's browser has the fixture URL
    # loaded (readyState === 'complete').
    deadline_iter = 50
    last_state = None
    for _ in range(deadline_iter):
        state = await execute_script(
            script=r"""
                let [url] = arguments;
                let mainWin = Services.wm.getMostRecentWindow('mail:3pane');
                let tabmail = mainWin.document.getElementById('tabmail');
                let tab = tabmail.selectedTab;
                if (!tab || !tab.browser) return {stage: 'no-tab'};
                let b = tab.browser;
                let uri = b.currentURI ? b.currentURI.spec : null;
                if (uri !== url) return {stage: 'wrong-uri', uri};
                // Remote browsers: use webProgress.isLoadingDocument
                // (contentDocument is null on e10s).
                let loading = b.webProgress && b.webProgress.isLoadingDocument;
                return {stage: loading ? 'loading' : 'ready', uri};
            """,
            args=[url], context="chrome", async_=False, timeout=5.0,
        )
        last_state = state.get("result")
        if last_state and last_state.get("stage") == "ready":
            await _switch_webdriver_to_content_tab(session, url)
            return
        await _asyncio.sleep(0.2)
    raise RuntimeError(f"content page never became ready; last={last_state}")


async def _switch_webdriver_to_content_tab(
    session: MarionetteSession, url: str,
) -> None:
    """After the shim + tab open, find the WebDriver window handle whose
    browser has our URL and switch to it, so `context='content'` ops target
    that browsing context.
    """
    client = session.client
    handles = await session.call(lambda: client.window_handles)
    for h in handles:
        try:
            await session.call(lambda h=h: client.switch_to_window(h))
        except Exception:
            continue
        try:
            cur = await session.call(client.get_url, ctx="content")
        except Exception:
            continue
        if cur == url:
            return
    raise RuntimeError(
        f"no WebDriver handle matched fixture URL {url}; "
        f"handles={handles}"
    )


@pytest.fixture(scope="module", autouse=True)
async def _content_context_cleanup():
    """After all content-context tests, close leftover contentTab(s) and
    reselect the mailTab so subsequent test modules (mail_ui_navigation,
    mail_workflow) get a mainWin.msgWindow with a docShell bound to the
    3-pane, not our fixture contentTab.

    Runs once per module (not per test) — avoids the per-test WebDriver
    session hang seen when execute_script is invoked from a function-scope
    fixture teardown while the current window handle is a contentTab.
    """
    yield
    try:
        await execute_script(
            script=r"""
                let mainWin = Services.wm.getMostRecentWindow('mail:3pane');
                if (!mainWin) return {ok: false, reason: 'no mainWin'};
                let tabmail = mainWin.document.getElementById('tabmail');
                if (!tabmail) return {ok: false, reason: 'no tabmail'};
                // Close every contentTab we opened, keep the mailTab (index 0).
                let closed = 0;
                for (let i = tabmail.tabInfo.length - 1; i > 0; i--) {
                    let t = tabmail.tabInfo[i];
                    if (t.browser && t.browser.getAttribute('type') === 'content') {
                        tabmail.closeTab(t);
                        closed++;
                    }
                }
                if (tabmail.tabInfo.length > 0) {
                    tabmail.switchToTab(tabmail.tabInfo[0]);
                }
                return {ok: true, closed};
            """,
            args=[], context="chrome", async_=False, timeout=5.0,
        )
    except Exception:
        pass


@pytest.fixture
async def content_page(session: MarionetteSession):
    """Open the HTML fixture in a contentTab. The tab's browser becomes
    the top-level browsing context for `context='content'` ops on the
    mail:3pane, so no `switch_to_window` is needed.
    """
    await _open_content_fixture()
    yield
    # Leave the tab open for reuse across parametrised tests; test order
    # is independent since each test picks its own selector.


# TB 153 Marionette bug workaround: content-tab browsing contexts are only
# visible after we monkey-patch shared/TabManager.sys.mjs::getTabBrowser to
# return a tabmail-backed shim (default returns null for anything that isn't
# Firefox/Android). Applied inside `_open_content_fixture` before each test.


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_content_find_and_get_text(content_page) -> None:
    found = await find_element(
        strategy="id", selector="static-text", context="content", timeout=5.0,
    )
    result = await get_text(element_id=found["element_id"], context="content")
    assert result["text"] == "hello content"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_content_click_updates_dom(content_page) -> None:
    btn = await find_element(
        strategy="id", selector="click-btn", context="content", timeout=5.0,
    )
    await click(element_id=btn["element_id"], context="content")
    result_el = await find_element(
        strategy="id", selector="click-result", context="content", timeout=5.0,
    )
    result = await get_text(element_id=result_el["element_id"], context="content")
    assert result["text"] == "clicked"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_content_type_text_echoes(content_page) -> None:
    inp = await find_element(
        strategy="id", selector="text-input", context="content", timeout=5.0,
    )
    await type_text(
        element_id=inp["element_id"], text="hello", clear=True, context="content",
    )
    echo = await find_element(
        strategy="id", selector="input-echo", context="content", timeout=5.0,
    )
    result = await get_text(element_id=echo["element_id"], context="content")
    assert result["text"] == "hello"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_content_get_attribute(content_page) -> None:
    inp = await find_element(
        strategy="id", selector="text-input", context="content", timeout=5.0,
    )
    result = await get_attribute(
        element_id=inp["element_id"], name="type", context="content",
    )
    assert result["value"] == "text"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_content_get_property(content_page) -> None:
    title = await find_element(
        strategy="id", selector="title", context="content", timeout=5.0,
    )
    result = await get_property(
        element_id=title["element_id"], name="tagName", context="content",
    )
    assert result["value"] == "H1"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_content_is_displayed_true(content_page) -> None:
    btn = await find_element(
        strategy="id", selector="click-btn", context="content", timeout=5.0,
    )
    result = await is_displayed(element_id=btn["element_id"], context="content")
    assert result["visible"] is True
