from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from tb_marionette_mcp.process import probe_port
from tb_marionette_mcp.session import MarionetteSession
from tests.fixtures import build_cmd_xpi, build_hello_xpi
from tests.integration import greenmail as gm
from tests.integration.profile_prefs import write_imap_account_prefs


@pytest.fixture(scope="session", autouse=True)
def _build_xpis() -> None:
    """Rebuild test XPIs before integration tests run.

    XPIs are build artifacts (gitignored); their manifest source lives in
    tests/fixtures/build_*_xpi.py and is the canonical definition.
    """
    build_hello_xpi.build()
    build_cmd_xpi.build(mv=2)
    build_cmd_xpi.build(mv=3)

PROFILE_DIR = Path(
    os.environ.get("TB_MCP_TEST_PROFILE")
    or (Path(__file__).parents[2] / ".tmp" / "tb-profile")
).resolve()
PORT = int(os.environ.get("TB_MCP_TEST_PORT", "2828"))
GREENMAIL_NAME = f"greenmail-integ-{os.getpid()}"
# When running under GHA `services:` block, greenmail is started by GHA;
# tests connect to localhost. Setting TB_INTEGRATION_GM_EXTERNAL=1 skips
# the podman lifecycle in the fixture.
GM_EXTERNAL = os.environ.get("TB_INTEGRATION_GM_EXTERNAL", "0") == "1"
# REAL_PROFILE mode: copy user's real TB profile into .tmp, append marionette.port,
# skip greenmail. Source path from TB_INTEGRATION_REAL_PROFILE env var.
REAL_PROFILE_SRC = os.environ.get("TB_INTEGRATION_REAL_PROFILE", "").strip()
REAL_PROFILE = bool(REAL_PROFILE_SRC)


def _tb_bin() -> str | None:
    return os.environ.get("TB_MCP_BINARY") or shutil.which("thunderbird")


@pytest.fixture(scope="session")
def greenmail_service() -> Iterator[gm.GreenmailEndpoints | None]:
    if REAL_PROFILE:
        # No greenmail — user's real profile talks to its own real mail server.
        yield None
        return
    if GM_EXTERNAL:
        endpoints = gm.endpoints_from_env()
        gm.wait_ready(endpoints)
        yield endpoints
        return
    endpoints = gm.start_container(GREENMAIL_NAME)
    try:
        yield endpoints
    finally:
        gm.stop_container(GREENMAIL_NAME)


def _append_marionette_port_pref(profile_dir: Path, port: int) -> None:
    """Append marionette.port user_pref to profile prefs.js (TB 153 ignores CLI arg)."""
    prefs = profile_dir / "prefs.js"
    with prefs.open("a", encoding="utf-8") as fh:
        fh.write(f'user_pref("marionette.port", {port});\n')


def _prepare_real_profile() -> Path:
    """Copy user's real TB profile into ephemeral .tmp/ dir + inject marionette port."""
    src = Path(REAL_PROFILE_SRC).expanduser().resolve()
    if not src.is_dir():
        pytest.fail(f"TB_INTEGRATION_REAL_PROFILE not a directory: {src}")
    dst = Path(__file__).parents[2] / ".tmp" / "tb-real-profile-copy"
    if dst.exists():
        shutil.rmtree(dst)
    # Skip lock files; TB will create fresh ones.
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns("parent.lock", "lock", ".parentlock"),
    )
    _append_marionette_port_pref(dst, PORT)
    return dst


def _prepare_profile(endpoints: gm.GreenmailEndpoints | None) -> Path:
    """Prepare profile: real-copy mode OR wipe+greenmail-IMAP mode."""
    if REAL_PROFILE:
        return _prepare_real_profile()
    assert endpoints is not None, "greenmail endpoints required in non-real mode"
    if PROFILE_DIR.exists():
        shutil.rmtree(PROFILE_DIR)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    write_imap_account_prefs(
        PROFILE_DIR,
        imap_host=endpoints.host,
        imap_port=endpoints.imap_port,
        smtp_host=endpoints.host,
        smtp_port=endpoints.smtp_port,
        marionette_port=PORT,
    )
    return PROFILE_DIR


@pytest.fixture(scope="session")
def tb_process(
    greenmail_service: gm.GreenmailEndpoints | None,
) -> Iterator[subprocess.Popen[bytes]]:
    binary = _tb_bin()
    if not binary:
        pytest.fail("thunderbird binary not found; install it or set TB_MCP_BINARY")
    profile_dir = _prepare_profile(greenmail_service)
    args = [
        binary,
        "--marionette", "--remote-allow-system-access",
        "--marionette-port", str(PORT),
        "--profile", str(profile_dir),
        "-no-remote",
    ]
    if os.environ.get("TB_TEST_HEADLESS", "1") != "0":
        args.append("-headless")
    stderr_fd, stderr_path = tempfile.mkstemp(prefix="tb-integ-stderr-", suffix=".log")
    popen = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=stderr_fd,
    )
    os.close(stderr_fd)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if probe_port("127.0.0.1", PORT):
            break
        time.sleep(0.5)
    else:
        popen.kill()
        try:
            with open(stderr_path) as fh:
                tail = fh.read()[-4000:]
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
async def session(
    tb_process: subprocess.Popen[bytes],
) -> AsyncIterator[MarionetteSession]:
    s = MarionetteSession.get()
    s.port = PORT
    await s.ensure_connected()
    yield s
    # Per-test cleanup: reset frame to default so the next test starts clean.
    with contextlib.suppress(Exception):
        await s.call(lambda: s.client.switch_to_default_content())
    # If a test invoked thunderbird_terminate (which nulls session._client without
    # cleaning up the server-side Marionette session), the next test's ensure_connected
    # would open a NEW session while TB still holds the old one — causing hangs.
    # Force full disconnect so the next test starts from a clean singleton state.
    with contextlib.suppress(Exception, asyncio.TimeoutError):
        client = s._client
        if client is not None:
            # Timeout guards against a wedged TB blocking teardown indefinitely
            # (pytest-timeout fires per-test, not per-fixture).
            await asyncio.wait_for(asyncio.to_thread(client.cleanup), timeout=5.0)
    s._client = None
    s._connected = False


def _seed_messages(endpoints: gm.GreenmailEndpoints) -> None:
    gm.seed_message(
        endpoints, to="user@greenmail.local",
        from_addr="alice@example.com",
        subject="Integration Fixture Message 1",
        body="hello from greenmail fixture",
    )
    gm.seed_message(
        endpoints, to="user@greenmail.local",
        from_addr="bob@example.com",
        subject="Integration Fixture Message 2",
        body="second body",
    )


@pytest.fixture(scope="session")
def imap_account(
    greenmail_service: gm.GreenmailEndpoints | None,
    tb_process: subprocess.Popen[bytes],
) -> gm.GreenmailEndpoints:
    """Seed messages after TB has started so an IMAP fetch will actually find them."""
    if greenmail_service is None:
        pytest.skip("imap_account fixture requires greenmail (skipped in REAL_PROFILE mode)")
    _seed_messages(greenmail_service)
    return greenmail_service
