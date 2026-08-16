# Integration Tests — 100% Tool Coverage Design

## Goal

Extend the integration test suite from covering 5 of 30 MCP tools live to
covering **all 30 tools** end-to-end against a real Thunderbird process. The
existing 109 unit tests + coverage will remain; this spec adds live wire
coverage that catches regressions the mocks cannot (Marionette wire protocol
drift, TB 153 chrome API changes, extension lifecycle, IMAP round-trip).

## Non-goals

- No refactoring of production code (`src/tb_marionette_mcp/**`). Bugs found
  during test authoring are reported and fixed under separate commits.
- No cross-platform coverage — Linux-only, matches existing CI.
- No load / performance / stress testing.
- No mail server compatibility matrix (only greenmail).

## Success criteria

1. Each of the 30 MCP tools exercised by at least one integration test that
   calls the tool through its FastMCP handler (not a bypass).
2. `pytest -q tests/integration` passes in CI (Fedora 44 container, non-root
   `tester` user) on every push, with no regression to current ~1 min CI time
   above the additional ~2-3 min budget approved by the user.
3. `pytest --cov=tb_marionette_mcp --cov-report=term-missing` at 100% for
   `src/tb_marionette_mcp/**` (already achieved by unit tests; integration
   tests must not regress it).
4. Integration tests run locally via `./run.tests.sh` and `./run.ci.local.sh`
   without host-side setup steps beyond what the scripts perform.

## Fixture architecture

Three-layer fixture pyramid — each layer reusable independently so tests only
pay for what they need.

### Layer 1: session-scoped services

**`tb_process`** (exists) — TB 153 launched with headless mode by default,
`-headless` flag omitted when `TB_TEST_HEADLESS=0`. Session-scoped because TB
takes 3-5s cold start and Marionette allows only one client per process.

**`greenmail_service`** (new) — greenmail/standalone container started via
podman on ports 3143 (IMAP), 3025 (SMTP), 3080 (REST API for seeding).
Session-scoped: container start-up is ~2s. Uses `--rm` and a unique container
name derived from `os.getpid()` to avoid collisions on parallel test runs.
Health-checked by TCP probe on 3080 with a 30s deadline. Teardown kills the
container.

**`session`** (exists, refactored) — `MarionetteSession` singleton connected
to `tb_process` port. Function-scoped fixture but reuses the singleton across
tests (Marionette allows only one client session per process). Each test is
expected to leave the Marionette context clean; a per-test `finalizer` calls
`switch_to_default()` and closes any tabs opened during the test.

### Layer 2: module-scoped state

**`configured_profile_with_imap`** (new, module-scoped) — provisions a TB
profile pre-configured with:
- Local Folders + IMAP account pointing at `greenmail_service`
- Account seeded with fixture messages via greenmail REST API before test
  discovery
- Account credentials: `user@greenmail.local` / `password`

Implementation: writes `prefs.js` fragments directly into the profile dir
before TB launch (matches how TB persists account config via
`mail.account.*` / `mail.server.*` prefs). Avoids driving Account Setup
Assistant through the UI (fragile).

Because `tb_process` is session-scoped, and only one profile is loaded per
process, this fixture depends on `tb_process` starting with the IMAP profile.
Session-scoped effective; module scope declared to keep the fixture available
to tests that never touch IMAP without paying its cost. Tests that need only
an empty profile go through a separate `empty_profile` fixture.

**Decision**: because we cannot re-load the profile mid-session, we use a
**single session-scoped profile with IMAP pre-configured**. Extension and
UI-only tests still work — the extra account is silent to them. This
simplifies the fixture graph at the cost of ~500ms extra TB startup.

**`test_extension`** (new, module-scoped) — copies `tests/fixtures/ext_hello.xpi`
into `.tmp/` and installs it via `extension_install(temporary=True)` at
module setup. Teardown uninstalls it. Reused by extension tests to avoid
re-installing per-test.

### Layer 3: per-test helpers (not fixtures)

Helpers imported from `tests/integration/_helpers.py`:
- `open_new_tab(session)` — creates a fresh tab so a test can navigate
  without stomping on the 3-pane view
- `close_all_extra_tabs(session)` — restores default 3-pane after test
- `wait_marionette_ready(session, timeout=5)` — polls until session ready

## Test file layout

One file per tool group, matching `src/tb_marionette_mcp/tools/*.py`:

```
tests/integration/
├── conftest.py               # tb_process, greenmail_service, session, extension fixtures
├── _helpers.py               # imported helpers, not auto-collected
├── test_process.py           # 3 tools: launch, terminate, status
├── test_ui.py                # 12 tools: find_element(s), click, type_text,
│                             #           get_text, get_attribute, get_property,
│                             #           is_displayed, list_windows,
│                             #           switch_to_window/frame/default,
│                             #           wait_for_element
├── test_keys.py              # 2 tools: send_keys, send_hotkey  [NEW]
├── test_scripts.py           # 2 tools: execute_script, wait_for_condition
├── test_diagnostics.py       # 6 tools: screenshot, get_page_source,
│                             #          get_current_url, get_window_title,
│                             #          get_console_logs, get_marionette_log  [NEW]
├── test_extensions.py        # 4 tools: install, uninstall, reload, list
└── test_mail_workflow.py     # end-to-end: launch → account visible → open
                              # message → verify subject/body → open compose  [NEW]
```

Tests use `pytest.mark.asyncio` (already `asyncio_mode = "auto"` in
`pyproject.toml`).

## Per-tool test matrix

Every tool gets a positive-path test hitting its FastMCP handler. Where the
tool has meaningful branches, additional tests cover them.

### Process (test_process.py, 3 tools)
- `thunderbird_status` → returns pid + port after `tb_process` fixture runs
- `thunderbird_launch` → confirms idempotent when process already running
  (returns existing pid, does not spawn)
- `thunderbird_terminate` → exercised in a **dedicated test** that spawns a
  second short-lived TB process on a different port (`TB_MCP_TEST_PORT+1`),
  calls `thunderbird_terminate(pid=<that pid>)`, verifies process exits.
  The session `tb_process` remains untouched. Alternative "skip and rely on
  unit test" was rejected: the goal is live wire coverage for every tool.

### UI (test_ui.py, 12 tools)
Target: the 3-pane messenger.xhtml chrome window. Tests use `#folderTree`,
`#threadTree`, `#messagepane` as stable selectors.
- `find_element` — locates `#folderTree` by CSS
- `find_elements` — returns >0 tree rows
- `click` — clicks a folder row, verifies selection changes via `get_attribute`
- `type_text` — types into the quick-filter search box, `clear=True` variant
- `get_text` / `get_attribute` / `get_property` / `is_displayed` — read
  properties of a known chrome element
- `list_windows` — returns ≥1 window handle (chrome-only fallback path)
- `switch_to_window` — no-op switch to current handle succeeds
- `switch_to_frame` / `switch_to_default` — enter the message iframe, then exit
- `wait_for_element` — waits for a lazily-created element (compose window
  opened via keyboard shortcut)

### Keys (test_keys.py, 2 tools)  [NEW FILE]
- `send_keys` — sends `n` into search box, verifies text present
- `send_hotkey` — `Ctrl+Shift+M` opens Compose window; verifies via
  `wait_for_element` + `list_windows`

### Scripts (test_scripts.py, 2 tools)
- `execute_script` — chrome context: `return Services.appinfo.name` returns
  `"Thunderbird"`
- `execute_script` — content context via arg: reads message body iframe
- `wait_for_condition` — polls a JS expression until true (opens a tab,
  waits for `document.readyState === 'complete'`)

### Diagnostics (test_diagnostics.py, 6 tools)  [NEW FILE]
- `screenshot` — returns non-empty base64, saveable as PNG
- `get_page_source` — returns XUL markup containing `messenger` root element
- `get_current_url` — returns `chrome://messenger/content/messenger.xhtml`
- `get_window_title` — returns TB title
- `get_console_logs` — returns list (may be empty on a clean session; test
  asserts type + no exception)
- `get_marionette_log` — reads the stderr tempfile TB was launched with

### Extensions (test_extensions.py, 4 tools)
- `extension_install` — installs `ext_hello.xpi`, returns addon id
- `extension_list` — includes the installed addon id
- `extension_reload` — reload succeeds, returns addon id
- `extension_uninstall` — uninstalls, subsequent `extension_list` excludes it

### Mail workflow (test_mail_workflow.py, integration scenario)  [NEW FILE]
Depends on `configured_profile_with_imap` fixture. Sequence:
1. Wait for account tree to include `user@greenmail.local`
2. Click Inbox — verify seeded messages appear in thread tree
3. Click first message — verify subject via `get_text`
4. Extract body via `switch_to_frame` into message iframe + `get_page_source`
5. `send_hotkey("Ctrl+N")` opens compose — verify via `list_windows`
6. `switch_to_default()` returns to 3-pane

This test is the acceptance test for the greenmail fixture — if it passes,
the IMAP path works end-to-end.

## CI integration

`.github/workflows/ci.yml` — add greenmail service before test steps:

```yaml
services:
  greenmail:
    image: greenmail/standalone:2.1.0
    ports:
      - 3143:3143  # IMAP
      - 3025:3025  # SMTP
      - 3080:3080  # REST API
```

GHA `services:` runs the container on the host network, accessible from the
job container at `localhost:PORT` — no podman-in-podman needed. In the
non-root `tester` user's step, greenmail is reached at `127.0.0.1`.

For `./run.ci.local.sh` (podman-based local repro): script starts greenmail
via `podman run -d --rm --name greenmail-integ ...` before running pytest,
teardown in `trap`.

## Error handling and flake mitigation

- All `wait_for_element` calls use explicit 10s timeout (default is 5s;
  chrome-only fallback adds variance).
- `pytest-timeout` marker `@pytest.mark.timeout(30)` on every integration test.
- Retries: `pytest-rerunfailures` at 1 retry only for tests marked
  `@pytest.mark.flaky` (specifically the compose-window-opens tests, which
  historically race the Marionette handshake after keyboard input).
- Between tests, `session` fixture finalizer calls `switch_to_default()` and
  closes tabs opened during the test — leftover state is the top flake
  source in Marionette suites.

## Rejected alternatives

- **Dovecot in podman** for IMAP — heavier, needs volume-mounted maildir seed,
  slower start. greenmail's REST seed API is faster and mail-only.
- **Live Gmail via app password** — CI secrets, rate limits, network flake.
- **Pre-generated profile.tar.gz** with mbox — skips IMAP wire protocol, so
  the mail workflow test would not actually verify TB's IMAP client works.
- **Single "fat" session fixture** setting up everything — extension tests
  would pay IMAP cost; harder to isolate failures.

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| greenmail startup race with TB IMAP client | tests flake | health-check greenmail before starting TB; `configured_profile` sets `mail.server.server1.check_new_mail = false` initially, tests explicitly poll |
| TB 153 API drift between minor versions | tool breaks silently | integration tests catch it; run on every push |
| Non-root `tester` user cannot bind ports | container start fails | GHA `services:` block runs on host; local script uses `--userns keep-id` or rootless bind (ports >1024 fine) |
| CI time budget | budget +2-3 min | greenmail image cached in workflow, tests parallelisable across tool groups (xdist opt-in) |

## Migration and rollout

1. Author fixtures + helpers first (no test changes yet) — verify locally.
2. Add tests file-by-file, one commit per file, each keeping the suite green.
3. Update `.github/workflows/ci.yml` and `run.ci.local.sh` last, after all
   tests pass locally.
4. Bump to `v0.2.0` on merge (minor release: test-only additions, no API
   changes).

## Out of scope for a follow-up

- Windows / macOS integration tests (Marionette works on both; CI
  infrastructure differs)
- Extension popup interaction (would need a real popup-triggering extension
  fixture; ext_hello is minimal)
- Multi-account IMAP scenarios
- Compose-and-send actually delivering via greenmail SMTP and verifying receipt
