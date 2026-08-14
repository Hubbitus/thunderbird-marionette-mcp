# thunderbird-marionette-mcp — Design Spec

**Date:** 2026-08-14
**Status:** Approved for implementation
**Author:** Pavel Alexeev (design collab with Claude)

## 1. Goal & Scope

Build a **Python MCP server** exposing UI-automation of a running **Thunderbird** to an AI assistant via the native **Marionette** protocol.

### Why

Existing Thunderbird MCP servers (TKasperczyk/thunderbird-mcp, vitalio-sh/thunderbird-cli, U-C4N, zileo-mcp-thunderbird, …) all wrap the in-process **WebExtension API**: they can read/write mail, folders, contacts, but they cannot click UI, send hotkeys, interact with WebExtension popup DOM, or drive Preferences dialogs. Marionette is the native Gecko automation protocol and gives full `chrome` + `content` scope, including WebExt popup DOM.

### Primary use case

End-to-end testing of Thunderbird extensions: click a button in the extension popup, type text, verify UI state, take a screenshot, simulate a hotkey.

### First consumer

`~/@Projects/@Hubbitus/@public/HuNote`.

### In scope (MVP = full scope)

All 7 tool groups from `prompt.md`:

1. Thunderbird process management (launch/terminate/status)
2. Extension install/uninstall/reload/list
3. UI interaction (find/click/type/switch)
4. Keys & hotkeys (send_keys, chord parser)
5. Screenshots & state inspection
6. Waits (`wait_for_element`, `wait_for_condition`)
7. Logging & diagnostics (console logs, marionette log)

### Out of scope

- Multi-tenant sessions (one MCP session = one TB process)
- Remote TB over network (localhost only)
- Wire-protocol version negotiation (target current TB 140+)
- GUI distribution (CLI/library only)
- Windows support (Linux + macOS only in MVP; Windows tracked as roadmap)

---

## 2. Tech stack

- **Python 3.11+**, dependency management via `uv`
- **`marionette_driver`** 3.7.1 — official Mozilla client, includes `marionette_driver.addons.Addons` with `install(path, temp=True) → addon_id` and `uninstall(id)`. Verified via Context7 upstream docs.
- **`mcp`** Python SDK (Anthropic official). Use **FastMCP** high-level API. Pin `>=1.12,<2.0` for MVP (2.0 released recently; migrate as follow-up).
- **`pydantic`** v2 — tool input/output validation
- **`structlog`** — JSON logs to stderr (stdout is MCP wire)
- **`ruff`** — lint + format (replaces black + isort + flake8)
- **`mypy --strict`** — type check
- **`pytest`** — unit + integration
- Build: **`hatchling`**, packaging via `pyproject.toml`

### TB launch invocation

```
thunderbird --marionette --marionette-port <port> -P <profile> -no-remote
```

Marionette listener defaults to port 2828.

---

## 3. Architecture

```
Claude Code / Claude Desktop / opencode
        │ stdio (MCP wire, JSON-RPC)
        ▼
┌─────────────────────────────────────┐
│ Python MCP server (FastMCP)         │
│ ┌─────────────────────────────────┐ │
│ │ MarionetteSession (singleton)   │ │
│ │  connect / reconnect / retry    │ │
│ │  chrome/content context switch  │ │
│ │  asyncio.Lock (wire is sync)    │ │
│ └─────────────────────────────────┘ │
│ tools: process | extensions | ui |  │
│        keys | scripts | diagnostics │
└─────────────────────────────────────┘
        │ TCP 2828 (Marionette wire)
        ▼
Thunderbird --marionette -P <profile>
```

### Session model

- One long-lived MCP process ↔ one `MarionetteSession` singleton.
- Session is **lazy**: created on first tool call.
- **Autoconnect is permissive**: if TB is already listening on `localhost:2828`, attach without requiring prior `thunderbird_launch`.
- All Marionette calls serialized under `asyncio.Lock` (Marionette wire = single request at a time).
- MCP tool handlers are `async def`; blocking Marionette calls wrapped in `asyncio.to_thread(...)`.
- `element_id` returned to MCP client = Marionette WebElement UUID (opaque string). Server holds no dict; passes through.
- Chrome/content context switch is **per-call** via a wrapper: set context → execute → restore prior context.

### Reconnect policy

- On `SocketTimeoutError` / `MarionetteException` matching connection loss: 1 reconnect attempt with fresh handshake, then propagate as `MarionetteWireError`.
- No idle timeout (stdio session is bound to the MCP client lifecycle).

---

## 4. Module layout

```
src/tb_marionette_mcp/
  __init__.py
  __main__.py              # python -m tb_marionette_mcp
  server.py                # FastMCP app, tool registration
  session.py               # MarionetteSession: connect/reconnect/lock/ctx switch
  process.py               # TB spawn/terminate, port probe
  models.py                # pydantic schemas (inputs/outputs)
  errors.py                # TbMcpError hierarchy → MCP error responses
  logging_.py              # structlog JSON config
  tools/
    __init__.py
    process_tools.py       # launch, terminate, status
    extension_tools.py     # install, uninstall, reload, list
    ui_tools.py            # find, click, type, get_text/attr, switch_*, waits
    key_tools.py           # send_keys, send_hotkey (W3C key map)
    script_tools.py        # execute_script, wait_for_condition
    diagnostic_tools.py    # screenshot, page_source, url, title, console logs
tests/
  unit/                    # mock Marionette, ≥80% cov
  integration/             # real TB (opt-out via --no-integration)
  fixtures/
    ext_hello.xpi          # trivial test extension
  conftest.py
docs/superpowers/specs/    # this file
.github/workflows/
  ci.yml                   # Fedora 44 container: lint + type + unit + integration
pyproject.toml
README.md
```

---

## 5. Session & connection details

### `MarionetteSession` (session.py)

- Singleton, thread-safe init.
- Config from env: `TB_MCP_MARIONETTE_HOST` (default `127.0.0.1`), `TB_MCP_MARIONETTE_PORT` (default `2828`), overall timeout `60s`.
- `async def ensure_connected() -> None`:
  1. If session live → return.
  2. Probe TCP port. If closed → raise `NotConnectedError("call thunderbird_launch first or start TB with --marionette")`.
  3. `Marionette(host, port).start_session()`.
- `async def call(fn, *args, ctx: Literal["chrome","content"] | None = None, **kw)`:
  - Acquire `self._lock`.
  - If `ctx` given: save current, `set_context(ctx)`, run, restore.
  - Run `await asyncio.to_thread(fn, *args, **kw)`.
  - On `SocketTimeoutError` / connection-loss `MarionetteException`: one reconnect attempt, retry once, else raise `MarionetteWireError`.

### `process.py`

- `spawn(profile: str, port: int) -> int`:
  - `tb_bin = os.environ.get("TB_MCP_BINARY") or shutil.which("thunderbird")`
  - Raise `LaunchError` if not found.
  - `subprocess.Popen([tb_bin, "--marionette", "--marionette-port", str(port), "-P", profile, "-no-remote"], stdout=DEVNULL, stderr=PIPE)`
  - Store handle in module-level dict `{pid: Popen}` (also captures stderr for `get_marionette_log`).
- `wait_port_open(host, port, timeout) -> None`: poll `socket.create_connection` every 200ms.
- `terminate(pid) -> bool`: SIGTERM → wait 10s → SIGKILL. Returns True if process exited.
- `status() -> dict`: port open? tracked pid alive?

---

## 6. Tool contracts (all pydantic-validated)

Response shape convention: every tool returns a JSON object (no bare scalars) so future fields can be added without breaking clients.

### 6.1 Process

| Tool | Input | Output |
|---|---|---|
| `thunderbird_launch` | `profile: str`, `marionette_port: int = 2828`, `wait_ready: bool = True`, `ready_timeout: float = 30.0` | `{pid: int, port: int, connected: bool}` |
| `thunderbird_terminate` | `pid: int \| None = None` (None = tracked pid) | `{stopped: bool}` |
| `thunderbird_status` | — | `{running: bool, pid: int \| null, port: int, connected: bool}` |

### 6.2 Extensions (via `marionette_driver.addons.Addons`)

| Tool | Input | Output |
|---|---|---|
| `extension_install` | `xpi_path: str`, `temporary: bool = True` | `{addon_id: str}` |
| `extension_uninstall` | `addon_id: str` | `{removed: bool}` |
| `extension_reload` | `addon_id: str`, `xpi_path: str` | `{addon_id: str, reloaded: bool}` |
| `extension_list` | — | `[{id, name, version, enabled, temporary}]` |

`extension_list` implementation: `execute_script` in chrome context calling `AddonManager.getAllAddons()` (async) via `execute_async_script`.

### 6.3 UI

Strategy enum: `id | css | xpath | link_text | partial_link_text | tag_name | class_name | name`. Context enum: `chrome | content`.

| Tool | Input | Output |
|---|---|---|
| `find_element` | `strategy, selector, context="chrome", timeout=5.0` | `{element_id: str}` |
| `find_elements` | (same) | `{element_ids: [str]}` |
| `click` | `element_id` | `{}` |
| `type_text` | `element_id, text, clear: bool = False` | `{}` |
| `get_text` | `element_id` | `{text: str}` |
| `get_attribute` | `element_id, name` | `{value: str \| null}` |
| `get_property` | `element_id, name` | `{value: any}` |
| `is_displayed` | `element_id` | `{visible: bool}` |
| `list_windows` | — | `[{handle, title, url}]` |
| `switch_to_window` | `handle: str` | `{}` |
| `switch_to_frame` | `element_id: str` | `{}` |
| `switch_to_default` | — | `{}` |
| `wait_for_element` | `strategy, selector, context="chrome", timeout=10.0, visible: bool = True` | `{element_id: str}` |

### 6.4 Keys

| Tool | Input | Output |
|---|---|---|
| `send_keys` | `keys: str, element_id: str \| None = None` | `{}` |
| `send_hotkey` | `chord: str, element_id: str \| None = None` | `{}` |

**Chord grammar:** `Mod (+ Mod)* + Key`, e.g. `Ctrl+Shift+N`, `Alt+F4`, `Enter`. Case-insensitive modifiers.

- Modifiers: `Ctrl | Alt | Shift | Meta | Cmd` (Cmd = Meta)
- Keys: `A-Z`, `0-9`, `F1-F12`, named (`Enter | Escape | Tab | Space | Delete | Backspace | Up | Down | Left | Right | Home | End | PageUp | PageDown | Insert`)

Implemented via `Marionette.actions` (W3C Actions API): key-down each modifier → key-down key → key-up key → key-up each modifier (reverse order).

### 6.5 Scripts

| Tool | Input | Output |
|---|---|---|
| `execute_script` | `script: str, args: list = [], context="chrome", async_: bool = False, timeout: float = 30` | `{result: any}` |
| `wait_for_condition` | `script: str, args: list = [], context="chrome", timeout: float = 30, poll_interval: float = 0.5` | `{result: any}` |

`chrome` context gives full `Cc / Ci / Services / MailServices` access.

### 6.6 Diagnostics

| Tool | Input | Output |
|---|---|---|
| `screenshot` | `element_id: str \| null = null, format: "png"\|"jpeg" = "png", full: bool = False` | `{data_base64: str, format: str}` |
| `get_page_source` | `context="content"` | `{source: str}` |
| `get_current_url` | — | `{url: str}` |
| `get_window_title` | — | `{title: str}` |
| `get_console_logs` | `clear: bool = False, level: str \| null = null` | `[{level, message, timestamp, source}]` |
| `get_marionette_log` | — | `{log: str, available: bool}` |

`get_console_logs`: chrome-context `execute_script` calling `Services.console.getMessageArray()`, filter by `level`, optional `Services.console.reset()` if `clear=True`.

`get_marionette_log`: returns tail of captured stderr for TB processes we launched; if session is attached to externally-started TB, returns `{available: false, log: ""}`.

---

## 7. Errors, logging, config

### Error hierarchy (`errors.py`)

```
TbMcpError                       code
├── NotConnectedError            not_connected
├── LaunchError                  launch_failed
├── MarionetteWireError          wire_error
├── ElementNotFoundError         element_not_found
├── ExtensionInstallError        extension_install_failed
├── TimeoutError                 timeout
└── InvalidArgumentError         invalid_argument
```

All carry `message: str` and optional `details: dict`.

Server-level handler wraps every tool: catches `TbMcpError` → returns MCP `isError=True` with `{code, message, details}`. Uncaught `Exception` → log full traceback, return generic `internal_error`.

### Logging (`logging_.py`)

- `structlog` JSON to **stderr** (stdout is reserved for MCP wire).
- Level via `TB_MCP_LOG_LEVEL` env, default `INFO`.
- Fields: `event`, `tool`, `duration_ms`, `error.code`, `session_id` (UUID per MCP session).
- Every tool call: start + end log entries with duration.

### Environment variables

| Var | Default | Meaning |
|---|---|---|
| `TB_MCP_BINARY` | `which thunderbird` | Thunderbird executable path |
| `TB_MCP_MARIONETTE_HOST` | `127.0.0.1` | Marionette host |
| `TB_MCP_MARIONETTE_PORT` | `2828` | Marionette port |
| `TB_MCP_LOG_LEVEL` | `INFO` | structlog level |
| `TB_MCP_STARTUP_TIMEOUT` | `30` | seconds to wait for TB port open |
| `TB_MCP_INTEGRATION` | `1` | 0 → skip integration tests |

No config file for MVP.

---

## 8. Testing

### Unit (`tests/unit/`, ≥80% coverage)

- Mock `Marionette` client via `unittest.mock`; inject fake into `MarionetteSession`.
- Per tool: happy path + one edge case (timeout / not-found / invalid arg).
- Chord parser: table-driven (`Ctrl+Shift+N`, `Alt+F4`, `Enter`, invalid).
- Pydantic schema round-trip tests.
- Runs on every push, target <10s wall time.

### Integration (`tests/integration/`, default ON, opt-out)

- No `pytest.mark.integration` skip by default.
- Opt-out: `pytest --no-integration` (custom CLI flag in `conftest.py`) or `TB_MCP_INTEGRATION=0`.
- Fixture `tb_process` (session-scoped): spawn TB with dedicated test profile under `.tmp/tb-profile/`, teardown SIGKILL.
- Fixture `mcp_session`: connected `MarionetteSession`.
- Fixture `test_extension`: path to `tests/fixtures/ext_hello.xpi` (trivial WebExt with browser_action).
- Coverage: launch/terminate, install/uninstall test xpi, find + click on a Compose-window toolbar button, screenshot, `execute_script` chrome scope returns `Services.appinfo.version`.
- Runs under `xvfb-run -a`.
- Prereqs check in `conftest.py`: if TB binary missing AND integration enabled → fail early with actionable message.

### CI (`.github/workflows/ci.yml`)

Single workflow on push + PR + `workflow_dispatch` + nightly cron:

- Runner: `ubuntu-latest`, `container: fedora:44`.
- Steps: `dnf install -y thunderbird xorg-x11-server-Xvfb git uv` → `uv sync` → `uv run ruff check` → `uv run mypy --strict src` → `xvfb-run -a uv run pytest`.
- Estimated: 2-3 min per run.

Future task (roadmap, tracked in README): publish `ghcr.io/hubbitus/tb-mcp-ci:fedora44-tb140` prebuilt image; switch `container:` to it → CI ~30-45s.

---

## 9. README structure

1. **What & why** — Marionette UI access vs WebExt-API MCP; niche
2. **Install** — `uv tool install tb-marionette-mcp` (primary) + `pip install` fallback
3. **Prereqs** — Thunderbird 140+, Fedora / Ubuntu / macOS
4. **Configure client** — three subsections with copy-paste snippets:
   - **Claude Desktop** — `~/.config/Claude/claude_desktop_config.json`
   - **Claude Code CLI** — `claude mcp add tb-marionette -- uv tool run tb-marionette-mcp`
   - **opencode** — `opencode.json` mcp section
5. **Quickstart** — 5-step: launch TB → install extension → find button → click → screenshot
6. **Tool reference** — table (name, description, key params)
7. **Environment variables**
8. **Troubleshooting** — port busy / TB no response / extension install fail / xvfb in CI / attaching to externally-started TB
9. **Development** — `uv sync`, `pytest`, `--no-integration`, ruff, mypy
10. **Roadmap** — prebuilt CI Docker image, Windows support, MCP 2.0 migration, WebDriver BiDi transport

---

## 10. Thunderbird vs Firefox specifics

- Main window chrome URI: `chrome://messenger/content/messenger.xhtml` (Firefox: `chrome://browser/content/browser.xhtml`).
- WebExtension popup in TB opens as a **separate window** (`chrome://extensions/content/...` or panel) — use `list_windows` + `switch_to_window`.
- Some Firefox-specific Marionette wire commands may be absent in TB — verify each in integration tests.
- `--marionette-port` works identically, default 2828.

---

## 11. Non-goals / explicitly deferred

- Windows support
- Remote (non-localhost) Marionette
- MCP protocol 2.0 migration (do after MVP stabilizes)
- WebDriver BiDi transport (Marionette wire is sunset roadmap upstream, but stable for 140+)
- Prebuilt CI image
- Multi-tenant / multi-TB per MCP server

---

## 12. Success criteria

- `uv tool install tb-marionette-mcp` works from PyPI.
- Configured in Claude Code CLI via `claude mcp add`, `list-tools` returns all documented tools.
- Integration test suite green on Fedora 44 CI.
- HuNote can drive its extension end-to-end: install xpi → open popup window → click button → assert visible state → screenshot.
- Coverage ≥ 80% (unit + integration combined).
- `mypy --strict` clean; `ruff check` clean.

---

## 13. References

- Marionette Protocol: https://firefox-source-docs.mozilla.org/testing/marionette/Protocol.html
- marionette_driver Python API: https://firefox-source-docs.mozilla.org/python/marionette_driver.html
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Sibling project (WebExt-API MCP for TB): https://github.com/TKasperczyk/thunderbird-mcp
- First consumer: `~/@Projects/@Hubbitus/@public/HuNote`
