from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from tb_marionette_mcp.errors import LaunchError
from tb_marionette_mcp.process import (
    ProcessRegistry,
    spawn,
    status,
    terminate,
    wait_port_open,
)


@pytest.fixture(autouse=True)
def clean_registry():
    ProcessRegistry.reset()
    yield
    ProcessRegistry.reset()


def test_spawn_no_binary_raises():
    with patch("tb_marionette_mcp.process.shutil.which", return_value=None), \
         patch.dict("os.environ", {}, clear=False), \
         pytest.raises(LaunchError):
        spawn("test-profile", 2828)


def test_spawn_returns_pid():
    fake_popen = MagicMock(spec=subprocess.Popen)
    fake_popen.pid = 12345
    with patch("tb_marionette_mcp.process.shutil.which", return_value="/usr/bin/thunderbird"), \
         patch("tb_marionette_mcp.process.subprocess.Popen", return_value=fake_popen) as popen_mock:
        pid = spawn("test-profile", 2828)
    assert pid == 12345
    args = popen_mock.call_args.args[0]
    assert "--marionette" in args
    assert "--marionette-port" in args
    assert "2828" in args
    assert "-P" in args
    assert "test-profile" in args
    assert "-no-remote" in args


def test_wait_port_open_success():
    with patch("tb_marionette_mcp.process._probe_port", return_value=True):
        wait_port_open("127.0.0.1", 2828, timeout=1.0)


def test_wait_port_open_timeout():
    with patch("tb_marionette_mcp.process._probe_port", return_value=False), \
         pytest.raises(TimeoutError):
        wait_port_open("127.0.0.1", 2828, timeout=0.3)


def test_terminate_unknown_pid():
    assert terminate(99999) is False


def test_status_no_process():
    with patch("tb_marionette_mcp.process._probe_port", return_value=False):
        s = status(2828)
    assert s["running"] is False
    assert s["pid"] is None
