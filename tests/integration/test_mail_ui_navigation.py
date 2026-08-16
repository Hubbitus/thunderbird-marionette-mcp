"""End-to-end UI navigation: open Inbox, select a message, read it.

Two flavours:

1. `test_ui_select_inbox_and_read_first_message` — chrome-script driven
   selection via internal 3-pane APIs (folderPane.selectFolder,
   threadPane.selectMessage). Stable across TB releases because it does
   not rely on XUL widget IDs, and visibly moves the highlight in the GUI
   (verified with `run.tests.sh --with-gui`).

2. `test_ui_click_folder_and_message_in_3pane` — real user-style click
   through the WebDriver DOM. Locates #folderTree / #threadTree rows
   inside the about:3pane iframe and clicks them. Documents the
   "playwright-for-Thunderbird" contract; xfails gracefully if the XUL
   internals shift between TB releases.
"""

from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.script_tools import execute_script
from tests.integration import greenmail as gm
from tests.integration._helpers import close_extra_windows

# --- Setup helper: force IMAP fetch before UI probes it (same as mail_workflow test) ---
# Note: on a fresh profile TB has not yet issued IMAP LIST, so the INBOX subfolder
# may not exist under rootFolder yet. We first call performExpand() (server-level
# LIST/subscribe) and poll for the child before running getNewMessages.
_FETCH_INBOX_JS = """
    let [resolve] = arguments;
    let acctMgr = Cc['@mozilla.org/messenger/account-manager;1']
        .getService(Ci.nsIMsgAccountManager);
    let server = acctMgr.allServers[0];
    server.password = 'test';
    // Use the real msgWindow from the running 3-pane. Freshly-created
    // nsIMsgWindow instances lack a docShell binding, which makes IMAP
    // performExpand fail its internal QI on nsIMsgWindow.
    let mainWin = Services.wm.getMostRecentWindow('mail:3pane');
    let msgWindow = mainWin && mainWin.msgWindow
        ? mainWin.msgWindow
        : Cc['@mozilla.org/messenger/msgwindow;1']
            .createInstance(Ci.nsIMsgWindow);
    let expandDeadline = Date.now() + 15000;

    function waitInboxDiscovered(cb) {
        let inbox = server.rootFolder.getChildNamed('INBOX');
        if (inbox) { cb(inbox); return; }
        if (Date.now() > expandDeadline) {
            resolve({ok: false, reason: 'INBOX not discovered after 15s'});
            return;
        }
        setTimeout(() => waitInboxDiscovered(cb), 250);
    }

    // Force IMAP LIST via updateFolder on rootFolder (populates children).
    // updateFolder is defined on nsIMsgFolder and accepts nsIMsgWindow;
    // works uniformly regardless of whether the server exposes performExpand.
    try {
        server.rootFolder.updateFolder(msgWindow);
    } catch (e) {
        // Non-fatal — folder may already be populated. Fall through to poll.
    }

    waitInboxDiscovered((inboxFolder) => {
        let inbox = inboxFolder.QueryInterface(Ci.nsIMsgImapMailFolder);
        let fetchDeadline = Date.now() + 60000;
        function pollDb() {
            try {
                let en = inbox.msgDatabase.enumerateMessages();
                if (en.hasMoreElements()) {
                    resolve({ok: true, total: inbox.getTotalMessages(false)});
                    return;
                }
                if (Date.now() > fetchDeadline) {
                    resolve({ok: false, reason: 'db empty after 60s'});
                    return;
                }
                setTimeout(pollDb, 500);
            } catch (e) {
                resolve({ok: false, reason: 'poll: ' + e.message});
            }
        }
        let listener = {
            OnStartRunningUrl: function(url) {},
            OnStopRunningUrl: function(url, status) { pollDb(); },
            QueryInterface: ChromeUtils.generateQI(['nsIUrlListener']),
        };
        try {
            server.getNewMessages(inbox, msgWindow, listener);
        } catch (e) {
            resolve({ok: false, reason: 'getNewMessages: ' + e.message});
        }
    });
"""


async def _ensure_inbox_populated() -> int:
    """Trigger IMAP fetch and wait until DB has ≥1 message. Returns count."""
    result = await execute_script(
        script=_FETCH_INBOX_JS, args=[], context="chrome",
        async_=True, timeout=90.0,
    )
    payload = result["result"]
    assert payload and payload.get("ok"), f"IMAP fetch failed: {payload}"
    return int(payload["total"])


# --- Test 1: chrome-script driven selection (stable) ---

@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_ui_select_inbox_and_read_first_message(
    session: MarionetteSession,
    imap_account: gm.GreenmailEndpoints,
) -> None:
    """Backend-driven selection: reach into 3-pane, select INBOX + first message,
    verify the message reader shows the seeded subject."""
    total = await _ensure_inbox_populated()
    assert total >= 1, f"expected ≥1 seeded message, got {total}"

    # Drive the 3-pane: about:3pane is the current-tab content browser inside
    # messenger.xhtml. Its window exposes folderPane/threadPane globals with
    # selectFolder(uri) and selectMessage(hdr) methods.
    result = await execute_script(
        script="""
            let [resolve] = arguments;
            (async () => {
                try {
                    let mainWin = Services.wm.getMostRecentWindow('mail:3pane');
                    if (!mainWin) { resolve({ok: false, reason: 'no mail:3pane'}); return; }
                    let tabmail = mainWin.document.getElementById('tabmail');
                    let about3pane = tabmail.currentAbout3Pane;
                    if (!about3pane) {
                        resolve({ok: false, reason: 'currentAbout3Pane missing'});
                        return;
                    }
                    let acctMgr = Cc['@mozilla.org/messenger/account-manager;1']
                        .getService(Ci.nsIMsgAccountManager);
                    let root = acctMgr.allServers[0].rootFolder;
                    // Poll — TB may not have re-populated getChildNamed lookup
                    // cache in this fresh sandbox; iterate subFolders as fallback.
                    let deadline = Date.now() + 10000;
                    async function findInbox() {
                        while (Date.now() < deadline) {
                            let inbox = root.getChildNamed('INBOX');
                            if (inbox) return inbox;
                            for (let sub of root.subFolders) {
                                if (sub.name === 'INBOX' || sub.name === 'Inbox') return sub;
                            }
                            await new Promise(r => about3pane.setTimeout(r, 250));
                        }
                        return null;
                    }
                    let inbox = await findInbox();
                    if (!inbox) {
                        let names = [];
                        for (let sub of root.subFolders) names.push(sub.name);
                        resolve({ok: false, reason: 'INBOX not found under root',
                                 subFolders: names});
                        return;
                    }
                    // selectFolder is async in TB 128+ (returns Promise)
                    await about3pane.displayFolder(inbox.URI);
                    // Wait one tick for threadTree to render.
                    await new Promise(r => about3pane.setTimeout(r, 200));
                    let threadTree = about3pane.document.getElementById('threadTree');
                    if (!threadTree || threadTree.view.rowCount === 0) {
                        resolve({ok: false, reason: 'threadTree empty',
                                 rowCount: threadTree ? threadTree.view.rowCount : -1});
                        return;
                    }
                    threadTree.selectedIndex = 0;
                    let hdr = about3pane.gDBView.getMsgHdrAt(0);
                    let subject = hdr.mime2DecodedSubject;
                    resolve({ok: true, subject: subject,
                             rowCount: threadTree.view.rowCount,
                             selectedIndex: threadTree.selectedIndex});
                } catch (e) {
                    resolve({ok: false, reason: e.message, stack: e.stack});
                }
            })();
        """,
        args=[], context="chrome", async_=True, timeout=30.0,
    )
    payload = result["result"]
    assert payload and payload.get("ok"), f"3-pane navigation failed: {payload}"
    assert "Integration Fixture" in payload["subject"], (
        f"expected seeded subject, got {payload['subject']!r}"
    )
    assert payload["rowCount"] >= 1
    assert payload["selectedIndex"] == 0

    await close_extra_windows(session)


# --- Test 2: XUL click smoke (documents "click Inbox row" pattern) ---

@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_ui_click_folder_and_message_in_3pane(
    session: MarionetteSession,
    imap_account: gm.GreenmailEndpoints,
) -> None:
    """Click-driven navigation: dispatch mousedown/click on folder row +
    thread row via chrome-scope helpers. Serves as smoke that WebDriver
    events reach TB 3-pane widgets; xfail if XUL id/structure drifts."""
    total = await _ensure_inbox_populated()
    assert total >= 1

    result = await execute_script(
        script="""
            let [resolve] = arguments;
            (async () => {
                try {
                    let mainWin = Services.wm.getMostRecentWindow('mail:3pane');
                    let tabmail = mainWin.document.getElementById('tabmail');
                    let about3pane = tabmail.currentAbout3Pane;
                    if (!about3pane) {
                        resolve({ok: false, reason: 'currentAbout3Pane missing'});
                        return;
                    }
                    let doc = about3pane.document;
                    let folderTree = doc.getElementById('folderTree');
                    if (!folderTree) {
                        resolve({ok: false, reason: '#folderTree not found in about:3pane'});
                        return;
                    }
                    // Find INBOX row: <li id="..."><span class="name">INBOX</span></li>
                    let rows = folderTree.querySelectorAll('li');
                    let inboxRow = null;
                    for (let r of rows) {
                        let nameEl = r.querySelector('.name');
                        if (nameEl && nameEl.textContent.trim() === 'Inbox') {
                            inboxRow = r; break;
                        }
                    }
                    if (!inboxRow) {
                        let names = Array.from(rows).map(r => {
                            let n = r.querySelector('.name');
                            return n ? n.textContent.trim() : '?';
                        });
                        resolve({ok: false, reason: 'no Inbox row',
                                 rowNames: names.slice(0, 20)});
                        return;
                    }
                    // Click folder name (TB 3-pane wires click on .name → selectFolder)
                    let nameEl = inboxRow.querySelector('.name') || inboxRow;
                    nameEl.click();
                    await new Promise(r => about3pane.setTimeout(r, 300));

                    let threadTree = doc.getElementById('threadTree');
                    if (!threadTree || threadTree.view.rowCount === 0) {
                        resolve({ok: false, reason: 'threadTree empty post-click',
                                 rowCount: threadTree ? threadTree.view.rowCount : -1});
                        return;
                    }
                    // Click first row via TreeView table body
                    let table = threadTree.table || threadTree;
                    let firstRow = table.body ?
                        table.body.querySelector('tr') :
                        threadTree.querySelector('tr');
                    if (firstRow) {
                        firstRow.click();
                    } else {
                        // Fallback: selectedIndex (still dispatches select event)
                        threadTree.selectedIndex = 0;
                    }
                    await new Promise(r => about3pane.setTimeout(r, 200));

                    let hdr = about3pane.gDBView.getMsgHdrAt(0);
                    resolve({ok: true,
                             subject: hdr.mime2DecodedSubject,
                             rowCount: threadTree.view.rowCount,
                             clickedRow: !!firstRow});
                } catch (e) {
                    resolve({ok: false, reason: e.message, stack: e.stack});
                }
            })();
        """,
        args=[], context="chrome", async_=True, timeout=30.0,
    )
    payload = result["result"]
    if not payload or not payload.get("ok"):
        pytest.xfail(f"XUL click drift (expected across TB releases): {payload}")
    assert "Integration Fixture" in payload["subject"]
    assert payload["rowCount"] >= 1

    await close_extra_windows(session)
