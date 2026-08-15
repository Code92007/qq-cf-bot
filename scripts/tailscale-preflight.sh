#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

is_true() {
    case "${1:-}" in
        1 | true | TRUE | yes | YES | on | ON) return 0 ;;
        *) return 1 ;;
    esac
}

run_as_root() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    else
        sudo "$@"
    fi
}

host_from_url() {
    value=${1:-}
    value=${value#*://}
    value=${value%%/*}
    value=${value##*@}
    value=${value#[}
    value=${value%]}
    value=${value%%:*}
    printf '%s\n' "$value"
}

looks_like_tailnet_host() {
    case "${1:-}" in
        100.* | *.ts.net) return 0 ;;
        *) return 1 ;;
    esac
}

tailscale_backend_running() {
    tailscale status --json 2>/dev/null | grep -q '"BackendState":"Running"'
}

required=${TAILSCALE_REQUIRED:-false}
ping_host=${TAILSCALE_PING_HOST:-}
if [ -z "$ping_host" ]; then
    judge_host=$(host_from_url "${JUDGE_API_URL:-}")
    if looks_like_tailnet_host "$judge_host"; then
        ping_host=$judge_host
    fi
fi

if ! is_true "$required" && [ -z "${TAILSCALE_AUTHKEY:-}" ] && [ -z "$ping_host" ]; then
    echo "Tailscale preflight skipped. Set TAILSCALE_REQUIRED=true to enforce it."
    exit 0
fi

if ! command -v tailscale >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Tailscale is required but the tailscale command is missing.
Install it on the server first:
  curl -fsSL https://tailscale.com/install.sh | sh
EOF
    exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl is-active --quiet tailscaled; then
        echo "Starting tailscaled with systemd..."
        run_as_root systemctl enable --now tailscaled
    fi
elif command -v service >/dev/null 2>&1; then
    run_as_root service tailscaled start >/dev/null 2>&1 || true
fi

if ! tailscale_backend_running; then
    hostname=${TAILSCALE_HOSTNAME:-qq-cf-bot}
    if [ -n "${TAILSCALE_AUTHKEY:-}" ]; then
        echo "Logging in to Tailscale with TAILSCALE_AUTHKEY..."
        # TAILSCALE_EXTRA_ARGS is intentionally split so .env can pass flags like --accept-routes.
        # shellcheck disable=SC2086
        run_as_root tailscale up --authkey "$TAILSCALE_AUTHKEY" --hostname "$hostname" ${TAILSCALE_EXTRA_ARGS:-}
    else
        cat >&2 <<EOF
Tailscale is not logged in.
Either set TAILSCALE_AUTHKEY in $ENV_FILE, or run this once on the server:
  sudo tailscale up --hostname $hostname
EOF
        exit 1
    fi
fi

if ! tailscale_backend_running; then
    echo "Tailscale is still not running after tailscale up." >&2
    exit 1
fi

if [ -n "$ping_host" ]; then
    echo "Checking Tailscale reachability: $ping_host"
    if ! tailscale ping -c 1 "$ping_host" >/dev/null 2>&1; then
        cat >&2 <<EOF
Tailscale is running, but $ping_host is not reachable.
Check that the model server is online and both machines are in the same tailnet.
EOF
        exit 1
    fi
fi

echo "Tailscale preflight OK."
