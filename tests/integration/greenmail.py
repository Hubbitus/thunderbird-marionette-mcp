"""Greenmail podman container lifecycle + REST seed API."""

from __future__ import annotations

import logging
import os
import smtplib
import socket
import subprocess
import time
from dataclasses import dataclass
from email.message import EmailMessage

_log = logging.getLogger(__name__)

GREENMAIL_IMAGE = "docker.io/greenmail/standalone:2.1.0"
IMAP_PORT = 3143
SMTP_PORT = 3025
REST_PORT = 8080
CONTAINER_LABEL = "app=tb-marionette-mcp-autotest"


@dataclass(frozen=True)
class GreenmailEndpoints:
    host: str
    imap_port: int
    smtp_port: int
    rest_port: int


def _probe(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_ready(endpoints: GreenmailEndpoints, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe(endpoints.host, endpoints.rest_port) and _probe(
            endpoints.host, endpoints.imap_port
        ):
            return
        time.sleep(0.3)
    raise TimeoutError(
        f"greenmail did not become ready within {timeout}s "
        f"at {endpoints.host}:{endpoints.rest_port}/{endpoints.imap_port}"
    )


def cleanup_stale_containers() -> None:
    """Remove leftover autotest containers from prior crashed sessions.

    Session-scoped teardown misses SIGKILL / segfault / OOM — stale
    containers hold port bindings and break subsequent runs. Filter
    is label-based (CONTAINER_LABEL) so unrelated user containers
    are never touched.
    """
    result = subprocess.run(
        [
            "podman", "ps", "-a",
            "--filter", f"label={CONTAINER_LABEL}",
            "--format", "{{.Names}}",
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        _log.warning(
            "podman ps failed (rc=%s); skipping stale-container cleanup. "
            "stderr=%s",
            result.returncode, result.stderr.strip(),
        )
        return
    for name in result.stdout.splitlines():
        name = name.strip()
        if not name:
            continue
        subprocess.run(
            ["podman", "rm", "-f", name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def start_container(name: str) -> GreenmailEndpoints:
    """Start greenmail via podman. Caller is responsible for stop_container."""
    cleanup_stale_containers()
    subprocess.run(
        [
            "podman", "run", "-d", "--rm", "--name", name,
            "--label", CONTAINER_LABEL,
            "-p", f"{IMAP_PORT}:{IMAP_PORT}",
            "-p", f"{SMTP_PORT}:{SMTP_PORT}",
            "-p", f"{REST_PORT}:{REST_PORT}",
            "-e", "GREENMAIL_OPTS=-Dgreenmail.setup.test.all "
                  "-Dgreenmail.hostname=0.0.0.0 -Dgreenmail.auth.disabled",
            GREENMAIL_IMAGE,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    endpoints = GreenmailEndpoints(
        host="127.0.0.1",
        imap_port=IMAP_PORT,
        smtp_port=SMTP_PORT,
        rest_port=REST_PORT,
    )
    wait_ready(endpoints)
    return endpoints


def stop_container(name: str) -> None:
    subprocess.run(
        ["podman", "kill", name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def seed_message(
    endpoints: GreenmailEndpoints,
    to: str,
    from_addr: str,
    subject: str,
    body: str,
) -> None:
    """Deliver a message to greenmail via SMTP. Greenmail 2.x REST does not
    expose a synchronous mail-injection endpoint; SMTP is the supported path
    with -Dgreenmail.setup.test.all (all protocols on all-users acceptance)."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(endpoints.host, endpoints.smtp_port, timeout=5) as smtp:
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f"greenmail seed failed: {exc}") from exc


def endpoints_from_env() -> GreenmailEndpoints:
    """For tests running against a greenmail started outside the fixture
    (e.g., GHA services: block)."""
    return GreenmailEndpoints(
        host=os.environ.get("GREENMAIL_HOST", "127.0.0.1"),
        imap_port=int(os.environ.get("GREENMAIL_IMAP_PORT", str(IMAP_PORT))),
        smtp_port=int(os.environ.get("GREENMAIL_SMTP_PORT", str(SMTP_PORT))),
        rest_port=int(os.environ.get("GREENMAIL_REST_PORT", str(REST_PORT))),
    )
