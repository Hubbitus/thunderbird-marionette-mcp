#!/usr/bin/env bash
# Build tb-marionette-mcp distribution artifacts (sdist + wheel) and validate.

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")" #"

usage() {
    cat <<'EOF'
Usage:
  ./run.build.sh                 # clean dist/, build sdist+wheel, twine check
  ./run.build.sh --no-clean      # keep existing dist/ contents
  ./run.build.sh --no-check      # skip twine check
  ./run.build.sh --inspect       # list contents of built sdist and wheel
  ./run.build.sh -h | --help     # this help
EOF
}

CLEAN=1
CHECK=1
INSPECT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-clean) CLEAN=0; shift ;;
        --no-check) CHECK=0; shift ;;
        --inspect)  INSPECT=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        *)          echo "Unknown arg: $1" >&2; usage; exit 2 ;;
    esac
done

if [[ $CLEAN -eq 1 ]]; then
    echo "=== clean dist/ ==="
    rm -rf dist/
fi

echo "=== uv build ==="
uv build

if [[ $CHECK -eq 1 ]]; then
    echo "=== twine check ==="
    uv tool run --from twine twine check dist/*
fi

echo "=== artifacts ==="
ls -la dist/

if [[ $INSPECT -eq 1 ]]; then
    SDIST=$(ls dist/*.tar.gz | head -n1)
    WHEEL=$(ls dist/*.whl | head -n1)
    echo "=== sdist contents: $SDIST ==="
    tar tzf "$SDIST" | sort
    echo "=== wheel contents: $WHEEL ==="
    unzip -l "$WHEEL"
fi
