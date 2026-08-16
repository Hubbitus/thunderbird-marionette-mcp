"""Extension management tools via marionette_driver.addons.Addons."""

from __future__ import annotations

from typing import Any, cast

from marionette_driver.addons import Addons

from tb_marionette_mcp.errors import ExtensionInstallError, InvalidArgumentError
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


# Path validated against TB 153 omni.ja (mail/components/extensions/parent/
# ext-commands.js line 63: `onCommand: name => this.emit("command", name)`).
# GlobalManager.extensionMap.get(id) returns the Extension instance; its
# apiManager.getAPI(module, ext, "addon_parent") returns the API class
# instance (ExtensionAPIPersistent), which inherits EventEmitter and exposes
# .emit(). wakeupBackground() ensures the persistent listener has been
# re-primed if the background page is currently suspended.
_TRIGGER_COMMAND_SCRIPT = """
const cb = arguments[arguments.length - 1];
const addonId = arguments[0];
const commandName = arguments[1];
(async () => {
  try {
    const {ExtensionParent} = ChromeUtils.importESModule(
      "resource://gre/modules/ExtensionParent.sys.mjs");
    const ext = ExtensionParent.GlobalManager.extensionMap.get(addonId);
    if (!ext) {
      cb({ok: false, error: "extension not found"});
      return;
    }
    if (typeof ext.wakeupBackground === "function") {
      await ext.wakeupBackground();
    }
    const api = ext.apiManager.getAPI("commands", ext, "addon_parent");
    if (!api || typeof api.emit !== "function") {
      cb({ok: false, error: "commands API not loaded"});
      return;
    }
    api.emit("command", commandName);
    cb({ok: true});
  } catch (e) {
    cb({ok: false, error: String(e)});
  }
})();
"""


async def extension_trigger_command(
    addon_id: str, command_name: str
) -> dict[str, bool]:
    """Fire a WebExtension `commands.onCommand` event directly.

    Works around TB chrome-XUL windows swallowing WebDriver key events before
    they reach the shortcut manager. Bypasses key dispatch entirely by
    emitting the internal event that the shortcut manager would emit on a
    real key press. See issue #1.
    """
    session = MarionetteSession.get()

    def _trigger() -> dict[str, Any]:
        return cast(
            dict[str, Any],
            session.client.execute_async_script(
                _TRIGGER_COMMAND_SCRIPT,
                script_args=[addon_id, command_name],
            ),
        )

    result = await session.call(_trigger, ctx="chrome")
    if not result.get("ok"):
        raise InvalidArgumentError(
            f"extension_trigger_command failed: {result.get('error', 'unknown')}",
            details={"addon_id": addon_id, "command_name": command_name},
        )
    return {"triggered": True}
