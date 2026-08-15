#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

"$ROOT_DIR/scripts/tailscale-preflight.sh"

cd "$ROOT_DIR"
docker compose up -d --build "$@"
