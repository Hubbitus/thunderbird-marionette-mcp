"""Build ext_cmd_mv{2,3}.xpi — WebExtension with a `commands` shortcut.

The background listener records the last-fired command name by throwing
an Error (routes via reportError() → Services.console.getMessageArray)
so integration tests can verify the listener actually ran. plain
console.log goes to ConsoleAPI (dev-tools only), invisible to
Services.console.

TB MV3 keeps Firefox-style event pages: `background: {scripts: [...]}` —
Chrome-style `service_worker` is NOT supported. Listeners MUST be
registered top-level (before any await) so the event page wakes them.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Literal

HERE = Path(__file__).parent


def _manifest(mv: Literal[2, 3]) -> dict:
    return {
        "manifest_version": mv,
        "name": f"Cmd Test MV{mv}",
        "version": "0.0.1",
        "browser_specific_settings": {
            "gecko": {
                "id": f"cmd-test-mv{mv}@tb-marionette-mcp",
                "strict_min_version": "128.0",
            }
        },
        "background": {"scripts": ["bg.js"]},
        "commands": {
            "fire-test": {
                "suggested_key": {"default": "Ctrl+Shift+Y"},
                "description": "Test command",
            }
        },
    }


BG_JS = r"""
browser.commands.onCommand.addListener((name) => {
  throw new Error("tbmm-cmd-test fired:" + name);
});
"""


def xpi_path(mv: Literal[2, 3]) -> Path:
    return HERE / f"ext_cmd_mv{mv}.xpi"


def build(mv: Literal[2, 3] = 2) -> Path:
    out = xpi_path(mv)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(_manifest(mv), indent=2))
        z.writestr("bg.js", BG_JS)
    return out


if __name__ == "__main__":
    print(build(2))
    print(build(3))
