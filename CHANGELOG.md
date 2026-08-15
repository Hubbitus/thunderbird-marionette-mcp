# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Hubbitus/thunderbird-marionette-mcp/releases/tag/v0.1.0
