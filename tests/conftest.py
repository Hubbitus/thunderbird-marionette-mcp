"""Pytest global config."""

from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-integration",
        action="store_true",
        default=False,
        help="Skip tests under tests/integration/",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    skip_integration = config.getoption("--no-integration") or os.environ.get(
        "TB_MCP_INTEGRATION"
    ) == "0"
    if not skip_integration:
        return
    skip_marker = pytest.mark.skip(reason="integration tests disabled")
    for item in items:
        if "tests/integration" in str(item.fspath):
            item.add_marker(skip_marker)
