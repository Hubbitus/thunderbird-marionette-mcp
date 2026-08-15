#!/usr/bin/env bash
# Run integration tests against a REAL Thunderbird profile (visible GUI).
#
# Copies the profile into .tmp/tb-real-profile-copy/ (never touches the original),
# injects marionette.port pref, then runs pytest with the real profile.
# NO greenmail is started; tests requiring greenmail (imap_account fixture) skip.
#
# Usage:
#   ./run.tests.REAL.sh                 # uses default profile path below
#   ./run.tests.REAL.sh /path/to/prof   # override profile path
#   ./run.tests.REAL.sh -- -k pattern   # pass extra args to pytest

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

DEFAULT_PROFILE="/home/pasha/@Projects/@Hubbitus/@public/HuNote/.tmp/test-profile"
PROFILE="$DEFAULT_PROFILE"
PYTEST_EXTRA=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --)
            shift; PYTEST_EXTRA=("$@"); break ;;
        -h|--help)
            grep -E '^# ' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)
            if [[ -d "$1" ]]; then
                PROFILE="$1"; shift
            else
                PYTEST_EXTRA+=("$1"); shift
            fi ;;
    esac
done

if [[ ! -d "$PROFILE" ]]; then
    echo "ERROR: profile dir not found: $PROFILE" >&2
    exit 1
fi

# Default free port; user can override.
: "${TB_MCP_TEST_PORT:=2929}"

export TB_INTEGRATION_REAL_PROFILE="$PROFILE"
export TB_TEST_HEADLESS=0
export TB_MCP_TEST_PORT

echo "=== REAL profile mode ==="
echo "  profile source: $PROFILE  (will be copied to .tmp/tb-real-profile-copy/)"
echo "  marionette port: $TB_MCP_TEST_PORT"
echo "  headless: no (GUI visible)"
echo "  greenmail: none (mail-workflow tests skipped)"
echo "==="

exec uv run pytest tests/integration -v "${PYTEST_EXTRA[@]}"
