# tb-marionette-mcp — project notes for Claude

## Changelog discipline

Any user-visible change (new tool, changed tool signature, bug fix, TB
compatibility fix, dependency bump that matters to users, breaking change) **must
be recorded in `CHANGELOG.md` under the `## [Unreleased]` section** as part of
the same commit that makes the change. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Categories to use:

- **Added** — new features / tools
- **Changed** — behavior changes in existing features
- **Deprecated** — features marked for removal
- **Removed** — features actually removed
- **Fixed** — bug fixes (include TB version if compatibility-related)
- **Security** — vulnerability fixes

Purely internal changes (refactor, test additions, CI tweaks, docs typos, dev
tooling) do **not** need a changelog entry.

At release time, `[Unreleased]` items get moved into a new
`## [X.Y.Z] — YYYY-MM-DD` section (see `docs/PUBLISHING.md` for the full
release checklist).

The release workflow (`.github/workflows/release.yml`) extracts release notes
from `CHANGELOG.md` by tag version; if the section is empty or the file is
missing, it falls back to auto-generated notes from git commit history — so the
release will still ship, but users see raw commit messages instead of a curated
summary. **Prefer the curated summary.**

## Build & publish

- Local dry-run build: `./run.build.sh --inspect`
- Full release procedure: `docs/PUBLISHING.md`
- CI: `.github/workflows/ci.yml` (lint + tests), `.github/workflows/release.yml`
  (tag `v*` → PyPI OIDC → GitHub Release)

## Tests

- `./run.tests.sh` — full suite (unit + integration under xvfb if no DISPLAY)
- `./run.tests.sh -u` — unit only
- `./run.tests.sh --lint` — ruff + mypy first
- `./run.tests.DEV.sh` — dev convenience wrapper
