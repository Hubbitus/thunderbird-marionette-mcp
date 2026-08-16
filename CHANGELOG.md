# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] — 2026-08-17

### Added

- `extension_trigger_command` integration test now runs against both MV2 and
  MV3 event pages via `@pytest.mark.parametrize("manifest_version", [2, 3])`.
  Confirms the tool works regardless of manifest version — TB keeps
  Firefox-style `background.scripts` for both (no Chrome-style
  `service_worker`), and the `command` event fires the same `ExtensionParent`
  pathway.
- New integration suite `test_content_context.py` (6 tests) exercising
  `context="content"` variants of `click`, `type_text`, `get_text`,
  `get_attribute`, `get_property`, `is_displayed` against a real HTML fixture
  loaded into a synthesized 3-pane tab. Uses a `<tabbrowser>` shim to satisfy
  TB 153's `TabManager.getTabBrowser()` returning null, and a `permanentKey`
  stub so WebDriver `NavigableManager.getIdForBrowser` succeeds.
- `tests/integration/greenmail.py::wait_msg_count()` — polls IMAP INBOX
  `EXISTS` after SMTP seed to bridge greenmail's SMTP→IMAP commit latency
  window (rootless podman coldstart). Fixture calls it with `expected=2`
  after `_seed_messages`.

### Changed

- `tests/fixtures/build_cmd_xpi.py`: `build()` now takes `mv: 2 | 3`, emits
  `ext_cmd_mv2.xpi` / `ext_cmd_mv3.xpi` with distinct addon ids
  (`cmd-test-mv{2,3}@tb-marionette-mcp`). Legacy `ext_cmd.xpi` removed.
- `tests/integration/profile_prefs.py`: new `password` param (default
  `"password"` matching greenmail default); disabled login-at-startup,
  download-on-biff, biff alerts to prevent race between fixture-seeded IMAP
  fetch and startup auto-fetch.

### Fixed

- `test_ui_select_inbox_and_read_first_message` was flaky with `db empty after
  60s` on cold IMAP fetch. Root cause: JS polled `msgDatabase` before
  `nsIImapMailFolderSink` finished the async commit pipeline. Fix: subscribe
  to `MailServices.mfn::msgsClassified`/`msgAdded` — the event fires only
  after the commit is durable. Deterministic (7.5s vs 60s+ timeout).

## [0.2.0] — 2026-08-16

### Added

- New MCP tool `extension_trigger_command(addon_id, command_name)` — fires a
  WebExtension `commands.onCommand` listener directly by emitting the internal
  `"command"` event via `ExtensionParent.GlobalManager`. Bypasses key dispatch
  entirely, working around TB 153 chrome-XUL windows swallowing WebDriver key
  events before they reach the shortcut manager
  (fixes [#1](https://github.com/Hubbitus/thunderbird-marionette-mcp/issues/1)).
  Total tool count: 30 → 31.
- Integration test suite expanded from 5 to 37 tests, covering all 31 MCP tools
  at 100% line coverage. New per-tool-group files: `test_process.py`,
  `test_process_terminate.py`, `test_ui.py`, `test_keys.py`, `test_scripts.py`,
  `test_diagnostics.py`, `test_extensions.py`, plus end-to-end
  `test_mail_workflow.py` (IMAP fetch against Greenmail) and
  `test_mail_ui_navigation.py` (chrome-script + XUL click flavours of "select
  Inbox, read first message").
- Greenmail-backed fixtures (`tests/integration/greenmail.py`,
  `tests/integration/profile_prefs.py`): auto-starts a `greenmail/standalone:2.1.0`
  podman sidecar and seeds a pre-configured IMAP account into a wiped TB profile
  before launch. Set `TB_INTEGRATION_GM_EXTERNAL=1` + `GREENMAIL_HOST` to reuse
  an externally-started instance (used by CI `services:` block).
- `run.ci.local.sh` and CI `services:` block both spawn a Greenmail sidecar so
  the mail-workflow test runs in every pipeline.
- `pytest-timeout` dev-dep — every integration test is capped so a wedged TB
  cannot stall the whole suite.
- Label-based orphan container reap: `start_container()` now runs
  `cleanup_stale_containers()` first, filtering by
  `app=tb-marionette-mcp-autotest`. Prevents port-binding conflicts after a
  session dies from SIGKILL / segfault / OOM, without touching user's own
  containers.

### Changed

- **BREAKING**: `click`, `type_text`, `get_text`, `get_attribute`,
  `get_property`, `is_displayed` gained a `context: "chrome" | "content"`
  parameter with `"chrome"` as default. Previously these tools ran in
  whatever context Marionette's session was in — effectively `"content"`
  on a fresh connection. This matches TB's chrome-only UI (`messenger.xhtml`)
  as the primary target of the server; callers targeting content pages must
  pass `context="content"` explicitly.
- **BREAKING**: `probe_port` in `tb_marionette_mcp.process` was renamed from
  `_probe_port` (private) to `probe_port` (public), since it is imported by
  `tools/process_tools.py` and integration tests.

### Fixed

- Cross-test hang triggered by `thunderbird_terminate`: nulling the session
  client without calling `cleanup()` left a dangling Marionette session on the
  main TB, so the next test's `ensure_connected` blocked forever. Session
  fixture now force-cleans the client after every test, with a 5s timeout so
  a wedged TB cannot stall test-suite teardown indefinitely.

## [0.1.4] — 2026-08-15

### Added

- PyPI trove classifiers (Python 3.11/3.12, MIT license, Linux, testing/email
  topics) — fixes missing `pyversions` badge on the PyPI page.

### Changed

- `requires-python` narrowed to `>=3.11,<3.13`. Python 3.13 removed the
  `telnetlib` stdlib module which `mozrunner` imports; declaring 3.13 support
  would let pip install a broken package.

## [0.1.3] — 2026-08-15

### Changed

- Package version now derived from git tags via `hatch-vcs` (removes manual
  bump). `pyproject.toml` uses `dynamic = ["version"]`; sdist/wheel get their
  version from `git describe`. Runtime `tb_marionette_mcp.__version__` reads
  from installed wheel metadata via `importlib.metadata`.

### Fixed

- CI: `set -euo pipefail` under `sudo -u tester` treated `GITHUB_PATH` as
  unbound. Removed the writeback (each step already `export PATH=$HOME/.local/bin:$PATH`
  inline).
- Release: v0.1.1 and v0.1.2 tags were pushed without bumping the static
  `version` field in `pyproject.toml`, so `uv build` produced 0.1.0 artifacts
  that PyPI rejected as duplicates. Dynamic versioning prevents this failure
  mode entirely.

## [0.1.2] — 2026-08-15

### Fixed

- CI (GitHub Actions `container: fedora:44`): TB 153 refused to launch as
  root. Rather than papering over with `MOZ_DISABLE_CONTENT_SANDBOX`, the
  workflow now creates an unprivileged `tester` (uid 1001) after the root
  package install and runs uv / lint / typecheck / tests via `sudo -u tester`.
  Content sandbox stays enabled; TB runs rootless with its own `$HOME`.
- Integration fixture now captures TB stderr to a tempfile and includes its
  tail in the `pytest.fail` message when the Marionette port fails to open
  within 45s (previously the stderr was discarded, hiding root causes like
  the sandbox EPERM above).
- `run.ci.local.sh`: reclaim workspace ownership on exit via
  `podman unshare chown` (rootless podman remaps container uid 1001 to host
  uid 101000, leaving files unwritable to the host user otherwise).

## [0.1.1] — 2026-08-15

### Fixed

- Integration test fixture: TB 153 removed `--CreateProfile`; profile is now
  provisioned by creating an empty directory and letting TB initialize it via
  `--profile <path>` on first run. Restores CI green after 5 integration errors.

## [0.1.0] — 2026-08-15

Initial public release.

### Added

- 30 MCP tools across 7 groups:
  - **Process**: `thunderbird_launch`, `thunderbird_terminate`, `thunderbird_status`
  - **Extensions**: `extension_install`, `extension_uninstall`, `extension_reload`,
    `extension_list`
  - **UI**: `find_element`, `find_elements`, `click`, `type_text`, `get_text`,
    `get_attribute`, `get_property`, `is_displayed`, `list_windows`,
    `switch_to_window`, `switch_to_frame`, `switch_to_default`, `wait_for_element`
  - **Keys**: `send_keys`, `send_hotkey` (W3C Actions API with chrome fallback)
  - **Scripts**: `execute_script`, `wait_for_condition`
  - **Diagnostics**: `screenshot`, `get_page_source`, `get_current_url`,
    `get_window_title`, `get_console_logs`, `get_marionette_log`
- Singleton `MarionetteSession` with async wrapper and `client.using_context()`
  context management
- Process registry with per-PID stderr tempfile tracking
- Full type annotations, pydantic input/output schemas
- 109 unit tests, 100% coverage
- Integration test harness with headless / GUI / existing-profile flags
  (`run.tests.sh`)
- Fedora 44 CI (xvfb, ruff, mypy, pytest)

### Fixed (TB 153 compatibility)

- Launch flags: `--marionette --remote-allow-system-access --profile <path>`
  (TB 153 removed `-P` short form)
- Chrome-only XUL window fallbacks for `list_windows`, `switch_to_window`,
  `screenshot`, `get_current_url`, `get_window_title`, `get_page_source`
  (WebDriver `window_handles`, `screenshot`, `page_source` all require a
  browsing context which `messenger.xhtml` lacks)
- `send_keys` / `send_hotkey`: new `ActionSequence(client, "key", ...)` API +
  chrome-context `KeyboardEvent` dispatch fallback for XUL windows
- `get_console_logs`: dropped broken `ChromeUtils.importESModule("Services.sys.mjs")`
  call — `Services` is already a chrome-context global in TB 153
- `session.py`: replaced non-existent `client.current_context` polling with
  `client.using_context(ctx)` context manager
- `process.py`: stderr routed to `tempfile.mkstemp()` instead of
  `subprocess.PIPE` (PIPE streams are non-seekable → `get_marionette_log` failed)

[Unreleased]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.4...v0.2.0
[0.1.4]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Hubbitus/thunderbird-marionette-mcp/releases/tag/v0.1.0
