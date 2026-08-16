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


def test_spawn_returns_pid(tmp_path):
    import os as _os
    fake_popen = MagicMock(spec=subprocess.Popen)
    fake_popen.pid = 12345
    stderr_file = tmp_path / "stderr.log"
    fd = _os.open(str(stderr_file), _os.O_WRONLY | _os.O_CREAT)
    with patch("tb_marionette_mcp.process.shutil.which", return_value="/usr/bin/thunderbird"), \
         patch("tb_marionette_mcp.process.subprocess.Popen", return_value=fake_popen) as popen_mock, \
         patch("tb_marionette_mcp.process.tempfile.mkstemp",
               return_value=(fd, str(stderr_file))):
        pid = spawn("test-profile", 2828)
    assert pid == 12345
    args = popen_mock.call_args.args[0]
    assert "--marionette" in args
    assert "--remote-allow-system-access" in args
    assert "--marionette-port" in args
    assert "2828" in args
    assert "--profile" in args
    assert "test-profile" in args
    assert "-no-remote" in args
    assert ProcessRegistry.stderr_path(12345) == str(stderr_file)


def test_wait_port_open_success():
    with patch("tb_marionette_mcp.process.probe_port", return_value=True):
        wait_port_open("127.0.0.1", 2828, timeout=1.0)


def test_wait_port_open_timeout():
    with patch("tb_marionette_mcp.process.probe_port", return_value=False), \
         pytest.raises(TimeoutError):
        wait_port_open("127.0.0.1", 2828, timeout=0.3)


def test_terminate_unknown_pid():
    assert terminate(99999) is False


def test_status_no_process():
    with patch("tb_marionette_mcp.process.probe_port", return_value=False):
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


def testprobe_port_returns_false_on_oserror():
    from tb_marionette_mcp.process import probe_port
    with patch("tb_marionette_mcp.process.socket.create_connection",
               side_effect=OSError):
        assert probe_port("127.0.0.1", 1) is False


def testprobe_port_returns_true_when_listener_up():
    import socket as _s

    from tb_marionette_mcp.process import probe_port
    srv = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert probe_port("127.0.0.1", port) is True
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


def test_stderr_tail_reads_bytes(tmp_path):
    from tb_marionette_mcp.process import stderr_tail
    log = tmp_path / "s.log"
    log.write_bytes(b"log data")
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 666
    ProcessRegistry.register(fake, stderr_path=str(log))
    assert stderr_tail(666) == "log data"


def test_stderr_tail_seek_fallback_on_short_file(tmp_path):
    from tb_marionette_mcp.process import stderr_tail
    log = tmp_path / "short.log"
    log.write_bytes(b"short")
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 777
    ProcessRegistry.register(fake, stderr_path=str(log))
    # max_bytes bigger than file → seek raises OSError, fallback to seek(0)
    assert stderr_tail(777, max_bytes=100000) == "short"


def test_stderr_tail_returns_empty_when_file_missing(tmp_path):
    from tb_marionette_mcp.process import stderr_tail
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 888
    ProcessRegistry.register(fake, stderr_path=str(tmp_path / "does-not-exist"))
    assert stderr_tail(888) == ""


def test_unregister_removes_stderr_file(tmp_path):
    log = tmp_path / "s.log"
    log.write_bytes(b"x")
    fake = MagicMock(spec=subprocess.Popen)
    fake.pid = 999
    ProcessRegistry.register(fake, stderr_path=str(log))
    assert log.exists()
    ProcessRegistry.unregister(999)
    assert not log.exists()
    assert ProcessRegistry.stderr_path(999) is None
