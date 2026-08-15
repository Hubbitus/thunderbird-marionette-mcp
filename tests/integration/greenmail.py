"""Greenmail podman container lifecycle + REST seed API."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

GREENMAIL_IMAGE = "docker.io/greenmail/standalone:2.1.0"
IMAP_PORT = 3143
SMTP_PORT = 3025
REST_PORT = 3080


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


def start_container(name: str) -> GreenmailEndpoints:
    """Start greenmail via podman. Caller is responsible for stop_container."""
    subprocess.run(
        [
            "podman", "run", "-d", "--rm", "--name", name,
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
    """POST a raw message to greenmail REST /api/service/handle/mail."""
    raw = (
        f"From: {from_addr}\r\n"
        f"To: {to}\r\n"
        f"Subject: {subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}"
    )
    payload = json.dumps({
        "from": from_addr, "to": to, "subject": subject, "body": raw
    }).encode()
    url = f"http://{endpoints.host}:{endpoints.rest_port}/api/service/handle/mail"
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except urllib.error.URLError as exc:
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
