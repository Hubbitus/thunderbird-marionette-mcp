"""thunderbird_terminate — dedicated 2nd short-lived TB on a different port.

The main tb_process fixture must remain alive for other tests. We spawn a
throwaway TB on TB_MCP_TEST_PORT + 1, call the terminate tool, and confirm
the process exits.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from tb_marionette_mcp.process import ProcessRegistry, _probe_port
from tb_marionette_mcp.tools.process_tools import thunderbird_terminate
from tests.integration.profile_prefs import write_imap_account_prefs


def _tb_bin() -> str | None:
    return os.environ.get("TB_MCP_BINARY") or shutil.which("thunderbird")


@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_terminate_kills_pid() -> None:
    binary = _tb_bin()
    if not binary:
        pytest.skip("thunderbird binary not available")
    main_port = int(os.environ.get("TB_MCP_TEST_PORT", "2828"))
    port = main_port + 1
    tmp_profile = Path(tempfile.mkdtemp(prefix="tb-terminate-", dir=".tmp"))
    # TB 153 ignores --marionette-port CLI; write pref instead.
    write_imap_account_prefs(tmp_profile, marionette_port=port)
    args = [
        binary,
        "--marionette", "--remote-allow-system-access",
        "--marionette-port", str(port),
        "--profile", str(tmp_profile),
        "-no-remote", "-headless",
    ]
    popen = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if _probe_port("127.0.0.1", port):
                break
            time.sleep(0.5)
        else:
            popen.kill()
            pytest.fail("2nd TB did not open Marionette port within 60s")

        # Register Popen so terminate() can look it up by pid.
        ProcessRegistry.register(popen)
        result = await thunderbird_terminate(pid=popen.pid)
        assert result["stopped"] is True

        # Confirm process is actually gone.
        for _ in range(40):
            if popen.poll() is not None:
                break
            time.sleep(0.25)
        assert popen.poll() is not None, "TB process did not exit after terminate"
    finally:
        if popen.poll() is None:
            popen.kill()
        shutil.rmtree(tmp_profile, ignore_errors=True)
