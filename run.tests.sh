#!/usr/bin/env bash
# Run tb-marionette-mcp test suite.

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")" #"

usage() {
    cat <<'EOF'
Usage:
  ./run.tests.sh                 # full suite (unit + integration), xvfb if no DISPLAY
  ./run.tests.sh -u              # unit tests only (--no-integration)
  ./run.tests.sh --lint          # ruff + mypy first, then full suite
  ./run.tests.sh -u --lint       # ruff + mypy + unit tests
  ./run.tests.sh --with-gui      # show TB window (no -headless, skip xvfb)
  ./run.tests.sh -p PATH         # use existing TB profile at PATH (--profile PATH)
  ./run.tests.sh -- -k pattern   # pass extra args to pytest after --
EOF
}

UNIT_ONLY=0
RUN_LINT=0
WITH_GUI=0
PROFILE=""
PYTEST_EXTRA=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--unit|--no-integration)
            UNIT_ONLY=1
            shift
            ;;
        --lint)
            RUN_LINT=1
            shift
            ;;
        --with-gui)
            WITH_GUI=1
            shift
            ;;
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        --profile=*)
            PROFILE="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            PYTEST_EXTRA=("$@")
            break
            ;;
        *)
            PYTEST_EXTRA+=("$1")
            shift
            ;;
    esac
done

if [[ $RUN_LINT -eq 1 ]]; then
    echo "=== ruff ==="
    uv run ruff check
    echo "=== mypy ==="
    uv run mypy
fi

PYTEST_ARGS=(--cov=src --cov-report=term)
if [[ $UNIT_ONLY -eq 1 ]]; then
    PYTEST_ARGS+=(--no-integration)
fi
PYTEST_ARGS+=("${PYTEST_EXTRA[@]}")

if [[ $WITH_GUI -eq 1 ]]; then
    export TB_TEST_HEADLESS=0
fi

if [[ -n "$PROFILE" ]]; then
    export TB_MCP_TEST_PROFILE="$PROFILE"
fi

# Auto-start greenmail if TB_INTEGRATION_IMAP=1 and no external instance configured.
# In-fixture podman lifecycle is default; this env is for pre-starting the container
# manually (e.g. when podman rootless would fail inside pytest).
if [[ "${TB_INTEGRATION_IMAP:-0}" == "1" && "${TB_INTEGRATION_GM_EXTERNAL:-0}" != "1" ]]; then
    GM_NAME="greenmail-run-tests-$$"
    echo "=== starting greenmail ($GM_NAME) ==="
    podman run -d --rm --name "$GM_NAME" \
        -p 3143:3143 -p 3025:3025 -p 8080:8080 \
        -e GREENMAIL_OPTS="-Dgreenmail.setup.test.all -Dgreenmail.hostname=0.0.0.0 -Dgreenmail.auth.disabled" \
        docker.io/greenmail/standalone:2.1.0 >/dev/null
    trap "podman kill '$GM_NAME' >/dev/null 2>&1 || true" EXIT
    export TB_INTEGRATION_GM_EXTERNAL=1
    export GREENMAIL_HOST=127.0.0.1
fi

echo "=== pytest ${PYTEST_ARGS[*]} ==="

if [[ $UNIT_ONLY -eq 0 && $WITH_GUI -eq 0 && -z "${DISPLAY:-}" ]]; then
    if command -v xvfb-run >/dev/null 2>&1; then
        exec xvfb-run -a uv run pytest "${PYTEST_ARGS[@]}"
    else
        echo "WARN: no DISPLAY and xvfb-run not found; integration tests may fail" >&2
    fi
fi

exec uv run pytest "${PYTEST_ARGS[@]}"
