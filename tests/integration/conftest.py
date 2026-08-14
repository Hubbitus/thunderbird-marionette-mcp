from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from tb_marionette_mcp.process import _probe_port
from tb_marionette_mcp.session import MarionetteSession

# Absolute path so --CreateProfile works regardless of cwd
PROFILE_DIR = Path(__file__).parents[2] / ".tmp" / "tb-profile"
PORT = int(os.environ.get("TB_MCP_TEST_PORT", "2828"))


def _tb_bin() -> str | None:
    return os.environ.get("TB_MCP_BINARY") or shutil.which("thunderbird")


def _ensure_profile() -> None:
    if PROFILE_DIR.exists():
        return
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_tb_bin() or "thunderbird",
         "--CreateProfile", f"tbmcp-test {PROFILE_DIR}"],
        check=True,
    )


@pytest.fixture(scope="session")
def tb_process() -> Iterator[subprocess.Popen[bytes]]:
    binary = _tb_bin()
    if not binary:
        pytest.fail("thunderbird binary not found; install it or set TB_MCP_BINARY")
    _ensure_profile()
    args = [binary, "--marionette", "--remote-allow-system-access",
            "--marionette-port", str(PORT),
            "--profile", str(PROFILE_DIR), "-no-remote"]
    if os.environ.get("TB_TEST_HEADLESS", "1") != "0":
        args.append("-headless")
    popen = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if _probe_port("127.0.0.1", PORT):
            break
        time.sleep(0.5)
    else:
        popen.kill()
        pytest.fail("Thunderbird did not open Marionette port within 45s")
    yield popen
    popen.terminate()
    try:
        popen.wait(timeout=10)
    except subprocess.TimeoutExpired:
        popen.kill()


@pytest.fixture
async def session(tb_process: subprocess.Popen[bytes]) -> AsyncIterator[MarionetteSession]:
    # Reuse singleton across tests: TB process is session-scoped and Marionette
    # allows only one client session per process. Resetting _instance between
    # tests would drop the wire connection.
    s = MarionetteSession.get()
    s.port = PORT
    await s.ensure_connected()
    yield s
