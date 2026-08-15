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

# Absolute path so `--profile` works regardless of cwd
PROFILE_DIR = Path(
    os.environ.get("TB_MCP_TEST_PROFILE")
    or (Path(__file__).parents[2] / ".tmp" / "tb-profile")
).resolve()
PORT = int(os.environ.get("TB_MCP_TEST_PORT", "2828"))


def _tb_bin() -> str | None:
    return os.environ.get("TB_MCP_BINARY") or shutil.which("thunderbird")


def _ensure_profile() -> None:
    # TB 153 removed `--CreateProfile`. Instead we just create an empty
    # directory and pass it via `--profile`; TB initializes it on first run.
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


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
    import tempfile
    stderr_fd, stderr_path = tempfile.mkstemp(prefix="tb-integ-stderr-", suffix=".log")
    popen = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL, stderr=stderr_fd,
    )
    os.close(stderr_fd)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if _probe_port("127.0.0.1", PORT):
            break
        time.sleep(0.5)
    else:
        popen.kill()
        try:
            with open(stderr_path) as f:
                tail = f.read()[-4000:]
        except OSError:
            tail = "(stderr unavailable)"
        pytest.fail(
            f"Thunderbird did not open Marionette port within 45s.\n"
            f"TB stderr tail:\n{tail}"
        )
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
