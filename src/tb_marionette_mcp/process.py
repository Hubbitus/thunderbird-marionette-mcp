"""Thunderbird process lifecycle."""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any, ClassVar

from tb_marionette_mcp.errors import LaunchError


class ProcessRegistry:
    _processes: ClassVar[dict[int, subprocess.Popen[bytes]]] = {}
    _stderr_paths: ClassVar[dict[int, str]] = {}

    @classmethod
    def register(
        cls, popen: subprocess.Popen[bytes], stderr_path: str | None = None
    ) -> None:
        cls._processes[popen.pid] = popen
        if stderr_path is not None:
            cls._stderr_paths[popen.pid] = stderr_path

    @classmethod
    def get(cls, pid: int) -> subprocess.Popen[bytes] | None:
        return cls._processes.get(pid)

    @classmethod
    def stderr_path(cls, pid: int) -> str | None:
        return cls._stderr_paths.get(pid)

    @classmethod
    def unregister(cls, pid: int) -> None:
        cls._processes.pop(pid, None)
        path = cls._stderr_paths.pop(pid, None)
        if path is not None:
            with contextlib.suppress(OSError):
                os.unlink(path)

    @classmethod
    def any_pid(cls) -> int | None:
        for pid, p in list(cls._processes.items()):
            if p.poll() is None:
                return pid
        return None

    @classmethod
    def reset(cls) -> None:
        for p in cls._processes.values():
            with contextlib.suppress(Exception):
                p.kill()
        cls._processes.clear()
        for path in cls._stderr_paths.values():
            with contextlib.suppress(OSError):
                os.unlink(path)
        cls._stderr_paths.clear()


def _probe_port(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def spawn(profile: str, port: int) -> int:
    tb_bin = os.environ.get("TB_MCP_BINARY") or shutil.which("thunderbird")
    if not tb_bin:
        raise LaunchError(
            "Thunderbird binary not found; set TB_MCP_BINARY or install thunderbird",
            details={"which_result": None},
        )
    stderr_fd, stderr_path = tempfile.mkstemp(prefix="tb-mcp-stderr-", suffix=".log")
    try:
        popen = subprocess.Popen(
            [
                tb_bin,
                "--marionette",
                "--remote-allow-system-access",
                "--marionette-port",
                str(port),
                "--profile",
                profile,
                "-no-remote",
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_fd,
        )
    finally:
        os.close(stderr_fd)
    ProcessRegistry.register(popen, stderr_path=stderr_path)
    return popen.pid


def wait_port_open(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe_port(host, port):
            return
        time.sleep(0.2)
    raise TimeoutError(f"port {host}:{port} did not open within {timeout}s")


def terminate(pid: int) -> bool:
    popen = ProcessRegistry.get(pid)
    if popen is None:
        return False
    try:
        popen.terminate()
        try:
            popen.wait(timeout=10)
        except subprocess.TimeoutExpired:
            popen.kill()
            popen.wait(timeout=5)
    finally:
        ProcessRegistry.unregister(pid)
    return True


def status(port: int, host: str = "127.0.0.1") -> dict[str, Any]:
    pid = ProcessRegistry.any_pid()
    return {
        "running": pid is not None,
        "pid": pid,
        "port": port,
        "connected": _probe_port(host, port),
    }


def stderr_tail(pid: int, max_bytes: int = 65536) -> str:
    path = ProcessRegistry.stderr_path(pid)
    if path is None:
        return ""
    try:
        with open(path, "rb") as f:
            try:
                f.seek(-max_bytes, os.SEEK_END)
            except OSError:
                f.seek(0)
            raw: bytes = f.read()
    except OSError:
        return ""
    return raw.decode(errors="replace")
