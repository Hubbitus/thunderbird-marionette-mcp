# Publishing Guide

One-time setup for pushing to GitHub and PyPI, and per-release steps.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth login`)
- Access to https://github.com/Hubbitus (repo owner)
- Access to https://pypi.org account owning (or empty and about to own)
  the `tb-marionette-mcp` project name

## One-time: Create GitHub repository

```bash
# From project root
gh repo create Hubbitus/thunderbird-marionette-mcp \
  --public \
  --source . \
  --description "MCP server for Thunderbird UI automation via Marionette" \
  --remote origin \
  --push
```

Or, if the repo already exists:

```bash
git remote add origin git@github.com:Hubbitus/thunderbird-marionette-mcp.git
git push -u origin main
```

Verify:

```bash
gh repo view Hubbitus/thunderbird-marionette-mcp --web
```

## One-time: PyPI trusted publishing

PyPI trusted publishing (OIDC) removes the need for API tokens. Configure once:

1. Go to https://pypi.org/manage/account/publishing/
2. Click **Add a new pending publisher**
3. Fill in:
   - **PyPI project name**: `tb-marionette-mcp`
   - **Owner**: `Hubbitus`
   - **Repository name**: `thunderbird-marionette-mcp`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
4. Save

The `release.yml` workflow already references `environment: pypi` and requests
`id-token: write` — no secrets needed once the pending publisher is registered.

## One-time: GitHub environment

In the GitHub repo:

1. Settings → Environments → **New environment** → name it `pypi`
2. (Optional) Add **Required reviewers** for manual approval before publish
3. (Optional) Restrict deployment to `main` branch and version tags

## Per-release checklist

1. **Bump version** in `pyproject.toml` (e.g. `0.1.0` → `0.2.0`)
2. **Update `CHANGELOG.md`**: move `[Unreleased]` items into a new
   `## [X.Y.Z] — YYYY-MM-DD` section, add fresh empty `[Unreleased]` header,
   update comparison links at the bottom
3. **Verify tests locally**:
   ```bash
   ./run.tests.sh --unit
   uv run ruff check
   uv run mypy
   ```
4. **Commit**:
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "release: vX.Y.Z"
   git push
   ```
5. **Wait for CI** to pass on `main`
6. **Tag and push**:
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
7. **`release.yml` runs automatically**:
   - Builds wheel + sdist
   - Publishes to PyPI (via OIDC)
   - Creates GitHub Release with `CHANGELOG.md` excerpt + attaches artifacts
8. **Verify**:
   - https://pypi.org/project/tb-marionette-mcp/
   - `pip install tb-marionette-mcp==X.Y.Z` (or `uv tool install`)
   - GitHub Releases page shows the new release

## Rollback

If a bad release ships:

- **PyPI**: releases are immutable. Yank via
  https://pypi.org/manage/project/tb-marionette-mcp/releases/ (yanked
  versions stay installable only if pinned) — then publish a fixed
  `X.Y.Z+1`.
- **GitHub Release**: `gh release delete vX.Y.Z` and `git push --delete
  origin vX.Y.Z` (only safe if no one has pulled the tag yet).

## Local dry-run build

To verify the package builds without publishing:

```bash
uv build
ls -la dist/
uv tool run --from twine twine check dist/*
```
