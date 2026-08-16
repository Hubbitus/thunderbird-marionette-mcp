from __future__ import annotations

import pytest

from tb_marionette_mcp.session import MarionetteSession
from tb_marionette_mcp.tools.script_tools import execute_script, wait_for_condition


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_execute_script_chrome_returns_appinfo_version(
    session: MarionetteSession,
) -> None:
    result = await execute_script(
        script=(
            'return Components.classes["@mozilla.org/xre/app-info;1"]'
            '.getService(Components.interfaces.nsIXULAppInfo).version;'
        ),
        args=[],
        context="chrome",
    )
    assert result["result"]
    assert result["result"][0].isdigit()


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_execute_script_chrome_returns_appinfo_name(
    session: MarionetteSession,
) -> None:
    result = await execute_script(
        script="return Services.appinfo.name;",
        args=[],
        context="chrome",
    )
    assert result["result"] == "Thunderbird"


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_execute_script_arithmetic(session: MarionetteSession) -> None:
    result = await execute_script(
        script="return arguments[0] + arguments[1];",
        args=[2, 3],
        context="chrome",
    )
    assert result["result"] == 5


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_wait_for_condition_true_immediately(
    session: MarionetteSession,
) -> None:
    result = await wait_for_condition(
        script="return true;",
        args=[],
        context="chrome",
        timeout=5.0,
    )
    assert result["result"] is True


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_wait_for_condition_services_defined(
    session: MarionetteSession,
) -> None:
    result = await wait_for_condition(
        script="return typeof Services !== 'undefined';",
        args=[],
        context="chrome",
        timeout=5.0,
    )
    assert result["result"] is True
