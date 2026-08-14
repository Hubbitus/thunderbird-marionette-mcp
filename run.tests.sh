#!/usr/bin/env bash
# Run tb-marionette-mcp test suite.
#
# Usage:
#   ./run.tests.sh                 # full suite (unit + integration), xvfb if no DISPLAY
#   ./run.tests.sh -u              # unit tests only (--no-integration)
#   ./run.tests.sh --lint          # ruff + mypy first, then full suite
#   ./run.tests.sh -u --lint       # ruff + mypy + unit tests
#   ./run.tests.sh -- -k pattern   # pass extra args to pytest after --

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

UNIT_ONLY=0
RUN_LINT=0
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
        -h|--help)
            sed -n '3,10p' "$0"
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

echo "=== pytest ${PYTEST_ARGS[*]} ==="

if [[ $UNIT_ONLY -eq 0 && -z "${DISPLAY:-}" ]]; then
    if command -v xvfb-run >/dev/null 2>&1; then
        exec xvfb-run -a uv run pytest "${PYTEST_ARGS[@]}"
    else
        echo "WARN: no DISPLAY and xvfb-run not found; integration tests may fail" >&2
    fi
fi

exec uv run pytest "${PYTEST_ARGS[@]}"
