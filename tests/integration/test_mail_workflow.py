"""End-to-end mail workflow test — depends on greenmail IMAP + seeded messages.

Verifies TB actually connects to greenmail, downloads messages, and the MCP
tools can drive selection + reading. This is the acceptance test for the
whole integration fixture stack.
"""

from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.script_tools import execute_script
from tests.integration import greenmail as gm
from tests.integration._helpers import close_extra_windows


@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_imap_account_visible_and_message_readable(
    session: MarionetteSession,
    imap_account: gm.GreenmailEndpoints,
) -> None:
    """Force new-mail check, wait for messages to appear, then read subject."""
    # Fetch IMAP headers + read first subject in a single async script (one sandbox).
    # updateFolderWithListener requires nsIMsgImapMailFolder; OnStopRunningUrl signals fetch done.
    result = await execute_script(
        script="""
            let [resolve] = arguments;
            let acctMgr = Cc['@mozilla.org/messenger/account-manager;1']
                .getService(Ci.nsIMsgAccountManager);
            let server = acctMgr.allServers[0];
            server.password = 'test';
            let inbox = server.rootFolder.getChildNamed('INBOX')
                .QueryInterface(Ci.nsIMsgImapMailFolder);
            let msgWindow = Cc['@mozilla.org/messenger/msgwindow;1']
                .createInstance(Ci.nsIMsgWindow);
            let deadline = Date.now() + 30000;
            function poll(status) {
                try {
                    let total = inbox.getTotalMessages(false);
                    let en = inbox.msgDatabase.enumerateMessages();
                    if (en.hasMoreElements()) {
                        let hdr = en.getNext().QueryInterface(Ci.nsIMsgDBHdr);
                        resolve({ok: true, subject: hdr.mime2DecodedSubject,
                                 status: status, total: total});
                        return;
                    }
                    if (Date.now() > deadline) {
                        resolve({ok: false, reason: 'db still empty',
                                 status: status, total: total});
                        return;
                    }
                    setTimeout(() => poll(status), 500);
                } catch (e) {
                    resolve({ok: false, reason: e.message, status: status});
                }
            }
            let listener = {
                OnStartRunningUrl: function(url) {},
                OnStopRunningUrl: function(url, status) { poll(status); },
                QueryInterface: ChromeUtils.generateQI(['nsIUrlListener']),
            };
            server.getNewMessages(inbox, msgWindow, listener);
        """,
        args=[],
        context="chrome",
        async_=True,
        timeout=60.0,
    )
    payload = result["result"]
    assert payload and payload.get("ok"), f"fetch failed: {payload}"
    assert "Integration Fixture" in payload["subject"], f"subject={payload['subject']!r}"

    await close_extra_windows(session)
