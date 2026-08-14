"""Build ext_hello.xpi with minimal browser_action."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
XPI = HERE / "ext_hello.xpi"

MANIFEST = {
    "manifest_version": 2,
    "name": "Hello Test",
    "version": "0.0.1",
    "applications": {
        "gecko": {
            "id": "hello-test@tb-marionette-mcp"
        }
    },
    "browser_action": {
        "default_title": "Hello"
    },
}


def build() -> Path:
    with zipfile.ZipFile(XPI, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(MANIFEST, indent=2))
    return XPI


if __name__ == "__main__":
    print(build())
