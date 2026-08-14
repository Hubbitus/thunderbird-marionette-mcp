"""Extension management tools via marionette_driver.addons.Addons."""

from __future__ import annotations

from typing import Any, cast

from marionette_driver.addons import Addons

from tb_marionette_mcp.errors import ExtensionInstallError
from tb_marionette_mcp.session import MarionetteSession

_LIST_SCRIPT = """
const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
const cb = arguments[arguments.length - 1];
AddonManager.getAllAddons().then(addons => {
  cb(addons.map(a => ({
    id: a.id,
    name: a.name,
    version: a.version,
    enabled: !a.userDisabled && !a.appDisabled,
    temporary: !!a.temporarilyInstalled,
  })));
});
"""


async def extension_install(xpi_path: str, temporary: bool = True) -> dict[str, str]:
    session = MarionetteSession.get()

    def _install() -> str:
        addons = Addons(session.client)
        try:
            return cast(str, addons.install(xpi_path, temp=temporary))
        except Exception as exc:
            raise ExtensionInstallError(
                f"failed to install {xpi_path}: {exc}"
            ) from exc

    addon_id = await session.call(_install)
    return {"addon_id": addon_id}


async def extension_uninstall(addon_id: str) -> dict[str, bool]:
    session = MarionetteSession.get()

    def _uninstall() -> None:
        addons = Addons(session.client)
        addons.uninstall(addon_id)

    await session.call(_uninstall)
    return {"removed": True}


async def extension_reload(addon_id: str, xpi_path: str) -> dict[str, Any]:
    session = MarionetteSession.get()

    def _reload() -> str:
        addons = Addons(session.client)
        addons.uninstall(addon_id)
        return cast(str, addons.install(xpi_path, temp=True))

    new_id = await session.call(_reload)
    return {"addon_id": new_id, "reloaded": True}


async def extension_list() -> list[dict[str, Any]]:
    session = MarionetteSession.get()

    def _list() -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            session.client.execute_async_script(_LIST_SCRIPT, script_args=[]),
        )

    return await session.call(_list, ctx="chrome")
