# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Hubbitus/thunderbird-marionette-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Hubbitus/thunderbird-marionette-mcp/releases/tag/v0.1.0
