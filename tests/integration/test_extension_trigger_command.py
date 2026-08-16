"""End-to-end verification that extension_trigger_command fires the
WebExtension `commands.onCommand` listener.

Issue: https://github.com/Hubbitus/thunderbird-marionette-mcp/issues/1

Test flow:
1. Install temporary MV2 extension with a `commands` entry and a
   background listener that throws an Error with a unique marker
   (`tbmm-cmd-test fired:`). The throw routes via reportError() into
   Services.console — plain console.log() from ext background goes to
   ConsoleAPI (dev-tools only), which Services.console cannot see.
2. Clear Services.console.
3. Call extension_trigger_command(addon_id, command_name).
4. Poll get_console_logs until the marker appears (or timeout).

If the marker never shows, the tool did NOT actually reach the listener.
"""

from __future__ import annotations

import time

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.diagnostic_tools import get_console_logs
from tb_marionette_mcp.tools.extension_tools import (
    extension_install,
    extension_trigger_command,
    extension_uninstall,
)
from tests.fixtures.build_cmd_xpi import xpi_path

MARKER = "tbmm-cmd-test fired:"


@pytest.mark.timeout(60)
@pytest.mark.asyncio
@pytest.mark.parametrize("manifest_version", [2, 3])
async def test_trigger_command_fires_listener(
    session: MarionetteSession, manifest_version: int,
) -> None:
    """Verify trigger works for both MV2 and MV3 event pages. TB uses
    Firefox-style `background.scripts` for both (no service_worker)."""
    xpi = xpi_path(manifest_version)
    installed = await extension_install(xpi_path=str(xpi.resolve()), temporary=True)
    addon_id = installed["addon_id"]
    try:
        # Clear stale entries so we only see logs from this test.
        await get_console_logs(clear=True)

        await extension_trigger_command(
            addon_id=addon_id, command_name="fire-test"
        )

        # Background page may be dormant on first fire; wakeupBackground()
        # inside the tool awaits it, but the listener callback + console
        # flush still races with our read. Poll up to 10s (CI needs
        # headroom over local dev).
        deadline = time.monotonic() + 10.0
        found = False
        while time.monotonic() < deadline:
            entries = await get_console_logs()
            for e in entries:
                msg = str(e.get("message", ""))
                if MARKER in msg and "fire-test" in msg:
                    found = True
                    break
            if found:
                break
            time.sleep(0.2)
        assert found, (
            f"Listener never fired — marker {MARKER!r} with 'fire-test' "
            f"never appeared in console.log entries. Last entries: "
            f"{[e.get('message', '') for e in entries[-10:]]}"
        )
    finally:
        await extension_uninstall(addon_id=addon_id)


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_trigger_command_unknown_extension_raises(
    session: MarionetteSession,
) -> None:
    from tb_marionette_mcp.errors import InvalidArgumentError

    with pytest.raises(InvalidArgumentError):
        await extension_trigger_command(
            addon_id="does-not-exist@nowhere", command_name="anything"
        )
