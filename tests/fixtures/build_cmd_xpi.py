"""Build ext_cmd.xpi — MV2 WebExtension with a `commands` shortcut.

The background listener records the last-fired command name into a
pref (`tbmm.test.cmd.last-fired`), so integration tests can verify the
listener actually ran without needing to scrape browser console output.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
XPI = HERE / "ext_cmd.xpi"

MANIFEST = {
    "manifest_version": 2,
    "name": "Cmd Test",
    "version": "0.0.1",
    "browser_specific_settings": {
        "gecko": {
            "id": "cmd-test@tb-marionette-mcp",
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

# Throwing an Error from the listener routes the message via reportError()
# into nsIConsoleService, where Services.console.getMessageArray() picks it up.
# console.log() from ext background goes to ConsoleAPI (dev-tools only), which
# is NOT visible via Services.console — hence the intentional throw.
BG_JS = r"""
browser.commands.onCommand.addListener((name) => {
  throw new Error("tbmm-cmd-test fired:" + name);
});
"""


def build() -> Path:
    with zipfile.ZipFile(XPI, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(MANIFEST, indent=2))
        z.writestr("bg.js", BG_JS)
    return XPI


if __name__ == "__main__":
    print(build())
