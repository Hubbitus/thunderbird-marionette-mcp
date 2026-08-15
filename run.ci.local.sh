#!/usr/bin/env bash
# Run the same CI pipeline (.github/workflows/ci.yml) locally in a
# Fedora 44 podman container. Mirrors GitHub Actions steps 1:1.

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")" #"

IMAGE="${CI_IMAGE:-fedora:44}"
NAME="tb-mcp-ci-local"

# Reuse a persistent named container so package installs + uv sync are
# cached between runs. Use `--fresh` to rebuild from scratch.
FRESH=0
if [[ "${1:-}" == "--fresh" ]]; then
    FRESH=1
    shift
fi

if [[ $FRESH -eq 1 ]]; then
    echo "=== removing existing container $NAME ==="
    podman rm -f "$NAME" 2>/dev/null || true
fi

# Bind repo read-write into container at /work.
# `:Z` relabels for SELinux (Fedora host).
TTY_FLAG=""
if [[ -t 0 && -t 1 ]]; then
    TTY_FLAG="-it"
fi

podman run --rm $TTY_FLAG \
    --name "${NAME}-$$" \
    -v "$PWD:/work:Z" \
    -w /work \
    -e TB_MCP_LOG_LEVEL=DEBUG \
    "$IMAGE" \
    bash -c '
        set -euo pipefail
        echo "=== install system deps ==="
        dnf install -y --setopt=install_weak_deps=False \
            thunderbird xorg-x11-server-Xvfb git \
            python3.11 python3.11-devel \
            gcc which findutils curl

        echo "=== install uv ==="
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"

        echo "=== uv sync ==="
        uv sync --frozen || uv sync

        echo "=== ruff ==="
        uv run ruff check

        echo "=== mypy ==="
        uv run mypy

        echo "=== tests (xvfb) ==="
        xvfb-run -a uv run pytest --cov=src --cov-report=term
    '
