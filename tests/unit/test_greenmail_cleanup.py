"""Unit tests for greenmail stale-container cleanup."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from tests.integration import greenmail as gm


@patch("tests.integration.greenmail.subprocess.run")
def test_cleanup_lists_by_label_and_removes_each(mock_run: MagicMock) -> None:
    """cleanup_stale_containers uses label filter + podman rm -f per name."""
    mock_run.side_effect = [
        subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="greenmail-integ-1111\ngreenmail-integ-2222\n",
        ),
        subprocess.CompletedProcess(args=[], returncode=0),
        subprocess.CompletedProcess(args=[], returncode=0),
    ]

    gm.cleanup_stale_containers()

    ps_call = mock_run.call_args_list[0]
    assert ps_call.args[0] == [
        "podman", "ps", "-a",
        "--filter", f"label={gm.CONTAINER_LABEL}",
        "--format", "{{.Names}}",
    ]
    assert mock_run.call_args_list[1] == call(
        ["podman", "rm", "-f", "greenmail-integ-1111"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    assert mock_run.call_args_list[2] == call(
        ["podman", "rm", "-f", "greenmail-integ-2222"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@patch("tests.integration.greenmail.subprocess.run")
def test_cleanup_noop_when_no_stale(mock_run: MagicMock) -> None:
    """No containers matching label → only ps executed, no rm calls."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="",
    )
    gm.cleanup_stale_containers()
    assert mock_run.call_count == 1


@patch("tests.integration.greenmail.subprocess.run")
def test_cleanup_ignores_ps_failure(mock_run: MagicMock) -> None:
    """podman ps non-zero (e.g. podman missing) → no crash, no rm calls."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="podman: command not found",
    )
    gm.cleanup_stale_containers()
    assert mock_run.call_count == 1


@patch("tests.integration.greenmail.subprocess.run")
def test_start_container_calls_cleanup_first(mock_run: MagicMock) -> None:
    """start_container triggers cleanup_stale_containers before podman run."""
    mock_run.side_effect = [
        subprocess.CompletedProcess(args=[], returncode=0, stdout=""),  # cleanup ps
        subprocess.CompletedProcess(args=[], returncode=0),              # podman run
    ]
    with patch("tests.integration.greenmail.wait_ready"):
        gm.start_container("test-name")

    ps_call = mock_run.call_args_list[0].args[0]
    run_call = mock_run.call_args_list[1].args[0]
    assert ps_call[:2] == ["podman", "ps"]
    assert run_call[:3] == ["podman", "run", "-d"]
    assert "--label" in run_call
    label_idx = run_call.index("--label")
    assert run_call[label_idx + 1] == gm.CONTAINER_LABEL


@patch("tests.integration.greenmail.imaplib.IMAP4")
def test_wait_msg_count_returns_when_count_reached(mock_imap: MagicMock) -> None:
    """wait_msg_count polls IMAP SELECT until EXISTS >= expected."""
    ctx = mock_imap.return_value.__enter__.return_value
    ctx.select.side_effect = [
        ("OK", [b"0"]),
        ("OK", [b"1"]),
        ("OK", [b"2"]),
    ]
    endpoints = gm.GreenmailEndpoints(
        host="127.0.0.1", imap_port=3143, smtp_port=3025, rest_port=8080,
    )
    got = gm.wait_msg_count(endpoints, expected=2, timeout=5.0, poll_interval=0.01)
    assert got == 2
    assert ctx.login.call_count == 3


@patch("tests.integration.greenmail.imaplib.IMAP4")
def test_wait_msg_count_raises_on_timeout(mock_imap: MagicMock) -> None:
    """wait_msg_count raises RuntimeError if count never reached."""
    ctx = mock_imap.return_value.__enter__.return_value
    ctx.select.return_value = ("OK", [b"0"])
    endpoints = gm.GreenmailEndpoints(
        host="127.0.0.1", imap_port=3143, smtp_port=3025, rest_port=8080,
    )
    with pytest.raises(RuntimeError, match="did not reach 2 msgs"):
        gm.wait_msg_count(endpoints, expected=2, timeout=0.2, poll_interval=0.05)


@patch("tests.integration.greenmail.imaplib.IMAP4")
def test_wait_msg_count_tolerates_transient_errors(mock_imap: MagicMock) -> None:
    """Connection failures during poll are swallowed until deadline; success wins."""
    ctx = mock_imap.return_value.__enter__.return_value
    ctx.login.side_effect = [OSError("refused"), None]
    ctx.select.return_value = ("OK", [b"2"])
    endpoints = gm.GreenmailEndpoints(
        host="127.0.0.1", imap_port=3143, smtp_port=3025, rest_port=8080,
    )
    got = gm.wait_msg_count(endpoints, expected=2, timeout=5.0, poll_interval=0.01)
    assert got == 2
