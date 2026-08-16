# Thunderbird Marionette MCP

[![CI](https://github.com/Hubbitus/thunderbird-marionette-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Hubbitus/thunderbird-marionette-mcp/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/tb-marionette-mcp.svg)](https://pypi.org/project/tb-marionette-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/tb-marionette-mcp.svg)](https://pypi.org/project/tb-marionette-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An MCP (Model Context Protocol) server exposing UI automation of a running Thunderbird via the native **Marionette** protocol. Lets an AI assistant click buttons, type text, install extensions, capture screenshots, run chrome-scope JavaScript, and drive Thunderbird end-to-end.

## What & why

Existing Thunderbird MCP servers ([TKasperczyk/thunderbird-mcp](https://github.com/TKasperczyk/thunderbird-mcp), [U-C4N/Thunderbird-MCP](https://github.com/U-C4N/Thunderbird-MCP), and others) all work through the **WebExtension API** from inside Thunderbird. They handle mail/folder/contact data but cannot click UI, invoke hotkeys, or interact with extension popups.

Marionette is Gecko's built-in automation protocol. It gives full **chrome** and **content** scope, including popups, dialogs, `Services`, `Cc/Ci`, `MailServices`, and the WebExtension popup DOM. This server wraps Marionette as MCP tools, so an LLM client can drive Thunderbird for extension development and end-to-end testing.

Like "playwright for Thunderbird".

## Install

Package on PyPI: <https://pypi.org/project/tb-marionette-mcp/>

```bash
uv tool install tb-marionette-mcp
```

Or with [pipx](https://pipx.pypa.io/):

```bash
pipx install tb-marionette-mcp
```

Or plain pip (into an isolated venv, not system Python):

```bash
pip install tb-marionette-mcp
```

## Prerequisites

- **Thunderbird 153** on PATH (or via `TB_MCP_BINARY`). Live-tested against TB 153; TB 140–152 may work but is untested — chrome-only XUL window fallbacks target TB 153 API surface.
- **Python 3.11+**
- Linux (Fedora / Ubuntu tested), macOS. Windows is not supported yet.

Install Thunderbird:

```bash
# Fedora
sudo dnf install thunderbird

# Ubuntu / Debian
sudo apt install thunderbird

# macOS
brew install --cask thunderbird
```

## Configure your MCP client

### Claude Desktop

Add to `~/.config/Claude/claude_desktop_config.json` (or the platform equivalent):

```json
{
  "mcpServers": {
    "tb-marionette": {
      "command": "uv",
      "args": ["tool", "run", "tb-marionette-mcp"]
    }
  }
}
```

### Claude Code CLI

```bash
claude mcp add tb-marionette -- uv tool run tb-marionette-mcp
```

### opencode

Add to `opencode.json`:

```json
{
  "mcp": {
    "tb-marionette": {
      "type": "local",
      "command": ["uv", "tool", "run", "tb-marionette-mcp"]
    }
  }
}
```

## Quickstart

Three worked examples: extension dev cycle, mail-reader navigation, and raw chrome-JS access. All tool calls below are JSON-RPC payloads exactly as an MCP client sends them.

### A. Extension dev cycle — install, click, screenshot

**1. Launch Thunderbird with a dedicated profile:**

```json
{"tool": "thunderbird_launch", "arguments": {"profile": "test-profile"}}
```

**2. Install a temporary WebExtension:**

```json
{"tool": "extension_install", "arguments": {"xpi_path": "/abs/path/to/ext.xpi", "temporary": true}}
```

**3. Find a chrome-scope button (e.g. addon toolbar button):**

```json
{"tool": "find_element", "arguments": {"strategy": "id", "selector": "button-appmenu", "context": "chrome"}}
```

**4. Click it:**

```json
{"tool": "click", "arguments": {"element_id": "<element_id from step 3>", "context": "chrome"}}
```

**5. Capture a screenshot:**

```json
{"tool": "screenshot", "arguments": {"full": true}}
```

Result contains base64-encoded PNG under `data_base64`.

**6. Reload after editing the source:**

```json
{"tool": "extension_reload", "arguments": {"addon_id": "yourext@example.com", "xpi_path": "/abs/path/to/ext.xpi"}}
```

**7. Trigger a WebExtension command shortcut directly (bypasses key dispatch — useful when TB chrome-XUL windows swallow WebDriver key events):**

```json
{"tool": "extension_trigger_command", "arguments": {"addon_id": "yourext@example.com", "command_name": "my-shortcut"}}
```

### B. Mail-reader — open Inbox, read first message

Assumes an account is already configured in the profile.

**1. Attach to a running Thunderbird** (or launch, as in A.1):

```json
{"tool": "thunderbird_status", "arguments": {}}
```

Any subsequent tool call auto-connects to `TB_MCP_MARIONETTE_PORT` if TB is already running with `--marionette`.

**2. Drive the 3-pane via chrome-scope JS** — select INBOX and read the first message's subject. This is the stable pattern (documented in `tests/integration/test_mail_ui_navigation.py`); avoids XUL widget IDs that shift between TB releases:

```json
{
  "tool": "execute_script",
  "arguments": {
    "context": "chrome",
    "async_": true,
    "timeout": 30.0,
    "script": "let [resolve] = arguments; (async () => { let mainWin = Services.wm.getMostRecentWindow('mail:3pane'); let about3pane = mainWin.document.getElementById('tabmail').currentAbout3Pane; let acctMgr = Cc['@mozilla.org/messenger/account-manager;1'].getService(Ci.nsIMsgAccountManager); let inbox = acctMgr.allServers[0].rootFolder.getChildNamed('INBOX'); await about3pane.displayFolder(inbox.URI); await new Promise(r => about3pane.setTimeout(r, 200)); let threadTree = about3pane.document.getElementById('threadTree'); threadTree.selectedIndex = 0; let hdr = about3pane.gDBView.getMsgHdrAt(0); resolve({subject: hdr.mime2DecodedSubject, from: hdr.mime2DecodedAuthor}); })();"
  }
}
```

Response: `{"result": {"subject": "...", "from": "..."}}`.

**3. Capture the message reader:**

```json
{"tool": "screenshot", "arguments": {"full": true}}
```

### C. Chrome-JS access — inspect installed accounts

```json
{
  "tool": "execute_script",
  "arguments": {
    "context": "chrome",
    "script": "let acctMgr = Cc['@mozilla.org/messenger/account-manager;1'].getService(Ci.nsIMsgAccountManager); return acctMgr.allServers.map(s => ({name: s.prettyName, type: s.type, host: s.hostName}));"
  }
}
```

Result: `[{"name": "user@example.com", "type": "imap", "host": "imap.example.com"}, ...]`.

Chrome context exposes `Cc`, `Ci`, `Services`, `MailServices`, `ExtensionParent`, `ChromeUtils` — the same JSM/ESM surface TB's own UI uses. This is what makes Marionette-based automation strictly more capable than WebExtension-based approaches for UI-driving and internal introspection.

## Tool reference

All 31 tools are pydantic-validated. Response objects are always dicts (or lists
of dicts) so future fields can be added without breaking clients.

### Process

| Tool                   | Description                              | Key params                                           |
| ---------------------- | ---------------------------------------- | ---------------------------------------------------- |
| `thunderbird_launch`   | Start TB with `--marionette` and profile | `profile`, `marionette_port=2828`, `wait_ready=True` |
| `thunderbird_terminate`| SIGTERM tracked or given pid             | `pid=None`                                           |
| `thunderbird_status`   | Report running / connected               | —                                                    |

### Extensions

| Tool                        | Description                                    | Key params                    |
| --------------------------- | ---------------------------------------------- | ----------------------------- |
| `extension_install`         | Install XPI via `Addons.install`               | `xpi_path`, `temporary=True`  |
| `extension_uninstall`       | Remove addon by id                             | `addon_id`                    |
| `extension_reload`          | Uninstall + install (dev cycle)                | `addon_id`, `xpi_path`        |
| `extension_list`            | List all addons via `AddonManager`             | —                             |
| `extension_trigger_command` | Fire `commands.onCommand` directly (bypass kbd) | `addon_id`, `command_name`    |

### UI

| Tool                 | Description                                 | Key params                                         |
| -------------------- | ------------------------------------------- | -------------------------------------------------- |
| `find_element`       | Locate one element                          | `strategy`, `selector`, `context="chrome"`         |
| `find_elements`      | Locate many elements                        | `strategy`, `selector`, `context="chrome"`         |
| `click`              | Click an element                            | `element_id`                                       |
| `type_text`          | Type text (optional clear first)            | `element_id`, `text`, `clear=False`                |
| `get_text`           | Element inner text                          | `element_id`                                       |
| `get_attribute`      | HTML attribute value                        | `element_id`, `name`                               |
| `get_property`       | DOM property value                          | `element_id`, `name`                               |
| `is_displayed`       | Visibility check                            | `element_id`                                       |
| `list_windows`       | All open window handles + title/url         | —                                                  |
| `switch_to_window`   | Switch active window                        | `handle`                                           |
| `switch_to_frame`    | Switch into an iframe                       | `element_id`                                       |
| `switch_to_default`  | Switch back to top-level content            | —                                                  |
| `wait_for_element`   | Poll until element is present (and visible) | `strategy`, `selector`, `timeout=10.0`, `visible`  |

Strategy enum: `id | css | xpath | link_text | partial_link_text | tag_name | class_name | name`.

### Keys

| Tool          | Description                          | Key params                          |
| ------------- | ------------------------------------ | ----------------------------------- |
| `send_keys`   | Send raw keys globally or to element | `keys`, `element_id=None`           |
| `send_hotkey` | Parse & dispatch a chord             | `chord` (e.g. `"Ctrl+Shift+N"`)     |

Chord grammar: `Mod (+ Mod)* + Key`. Modifiers: `Ctrl | Alt | Shift | Meta | Cmd` (Cmd = Meta). Named keys: `Enter | Escape | Tab | Space | Delete | Backspace | Up | Down | Left | Right | Home | End | PageUp | PageDown | Insert | F1..F12`.

### Scripts

| Tool                 | Description                       | Key params                                                     |
| -------------------- | --------------------------------- | -------------------------------------------------------------- |
| `execute_script`     | Run JS in chrome or content scope | `script`, `args=[]`, `context="chrome"`, `async_=False`        |
| `wait_for_condition` | Poll JS predicate until truthy    | `script`, `timeout=30`, `poll_interval=0.5`                    |

`chrome` context has full `Cc / Ci / Services / MailServices` access.

### Diagnostics

| Tool                  | Description                                | Key params                            |
| --------------------- | ------------------------------------------ | ------------------------------------- |
| `screenshot`          | PNG/JPEG of screen or element              | `element_id=None`, `format`, `full`   |
| `get_page_source`     | Current DOM serialized                     | `context="content"`                   |
| `get_current_url`     | URL of active tab / window                 | —                                     |
| `get_window_title`    | Title of active window                     | —                                     |
| `get_console_logs`    | Chrome console messages (optional filter)  | `clear=False`, `level=None`           |
| `get_marionette_log`  | Tail stderr of a TB we launched            | —                                     |

## Environment variables

| Variable                     | Default            | Meaning                             |
| ---------------------------- | ------------------ | ----------------------------------- |
| `TB_MCP_BINARY`              | `which thunderbird`| Thunderbird executable              |
| `TB_MCP_MARIONETTE_HOST`     | `127.0.0.1`        | Marionette host                     |
| `TB_MCP_MARIONETTE_PORT`     | `2828`             | Marionette port                     |
| `TB_MCP_LOG_LEVEL`           | `INFO`             | structlog level                     |
| `TB_MCP_STARTUP_TIMEOUT`     | `30`               | seconds to wait for TB port open    |
| `TB_MCP_INTEGRATION`         | `1`                | `0` skips integration tests         |

## Troubleshooting

- **Port 2828 already in use** — another TB instance is running with Marionette. Either terminate it (`thunderbird_terminate` or `pkill thunderbird`) or launch on a different port via `marionette_port=2829`.
- **TB does not respond** — check `thunderbird_status`; if `running=true` but `connected=false`, TB started without `--marionette`. Kill and relaunch.
- **Extension install fails** — for `temporary=false` the XPI must be signed by Mozilla; for dev use `temporary=true` (unsigned, cleared on restart).
- **CI without display** — wrap the pytest / launch command with `xvfb-run -a ...` or set up `Xvfb` and export `DISPLAY=:0`.
- **Attach to externally-started TB** — do not call `thunderbird_launch`. If TB is already running on `TB_MCP_MARIONETTE_PORT`, any tool call auto-connects. `get_marionette_log` returns `available=false` in that mode (we have no stderr handle).

## Development

```bash
uv sync                        # install deps + editable
uv run pytest                  # full suite (unit + integration)
uv run pytest --no-integration # unit only
uv run ruff check              # lint
uv run mypy                    # type-check
```

Integration tests spawn a real Thunderbird under `xvfb-run` and default ON;
opt-out via `--no-integration` or `TB_MCP_INTEGRATION=0`.

## Roadmap

- Prebuilt Fedora + Thunderbird CI Docker image (`ghcr.io/hubbitus/tb-mcp-ci`)
- Windows support
- MCP protocol 2.0 migration
- WebDriver BiDi transport (Marionette wire is on Mozilla's sunset roadmap)

## References

- Marionette Protocol: https://firefox-source-docs.mozilla.org/testing/marionette/Protocol.html
- marionette_driver: https://firefox-source-docs.mozilla.org/testing/marionette/PythonTests.html
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Companion project (WebExt data access): https://github.com/TKasperczyk/thunderbird-mcp
