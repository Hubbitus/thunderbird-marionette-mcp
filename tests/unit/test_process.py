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


def test_registry_unregister_removes_pid():
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 111
    ProcessRegistry.register(fake)
    assert ProcessRegistry.get(111) is fake
    ProcessRegistry.unregister(111)
    assert ProcessRegistry.get(111) is None


def test_registry_any_pid_returns_running_pid():
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 222
    fake.poll.return_value = None  # still running
    ProcessRegistry.register(fake)
    assert ProcessRegistry.any_pid() == 222


def test_registry_any_pid_skips_exited():
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 333
    fake.poll.return_value = 0  # exited
    ProcessRegistry.register(fake)
    assert ProcessRegistry.any_pid() is None


def test_probe_port_returns_false_on_oserror():
    from tb_marionette_mcp.process import _probe_port
    with patch("tb_marionette_mcp.process.socket.create_connection",
               side_effect=OSError):
        assert _probe_port("127.0.0.1", 1) is False


def test_probe_port_returns_true_when_listener_up():
    import socket as _s

    from tb_marionette_mcp.process import _probe_port
    srv = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert _probe_port("127.0.0.1", port) is True
    finally:
        srv.close()


def test_terminate_graceful():
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 444
    ProcessRegistry.register(fake)
    assert terminate(444) is True
    fake.terminate.assert_called_once()
    fake.wait.assert_called_with(timeout=10)


def test_terminate_kills_on_timeout():
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 555
    fake.wait.side_effect = [subprocess.TimeoutExpired("cmd", 10), None]
    ProcessRegistry.register(fake)
    assert terminate(555) is True
    fake.kill.assert_called_once()
    assert fake.wait.call_count == 2


def test_stderr_tail_no_process():
    from tb_marionette_mcp.process import stderr_tail
    assert stderr_tail(99999) == ""


def test_stderr_tail_reads_bytes():
    from tb_marionette_mcp.process import stderr_tail
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 666
    fake.stderr = MagicMock()
    fake.stderr.read.return_value = b"log data"
    ProcessRegistry.register(fake)
    assert stderr_tail(666) == "log data"


def test_stderr_tail_seek_fallback_on_short_file():
    from tb_marionette_mcp.process import stderr_tail
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 777
    fake.stderr = MagicMock()
    fake.stderr.seek.side_effect = [OSError("too short"), None]
    fake.stderr.read.return_value = b"short"
    ProcessRegistry.register(fake)
    assert stderr_tail(777) == "short"
    assert fake.stderr.seek.call_count == 2
