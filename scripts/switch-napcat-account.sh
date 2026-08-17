#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

NAPCAT_SERVICE=${NAPCAT_DOCKER_SERVICE:-napcat}
QR_OUT=${NAPCAT_QRCODE_OUT:-/tmp/napcat-qrcode.png}
LABEL=${1:-qq-account}
STAMP=$(date +%Y%m%d-%H%M%S)
SAFE_LABEL=$(printf '%s' "$LABEL" | tr -c 'A-Za-z0-9_.-' '_')
BACKUP_DIR="napcat/backup/${SAFE_LABEL}-${STAMP}"

echo "Switching NapCat account profile."
echo "Service: $NAPCAT_SERVICE"

if command -v systemctl >/dev/null 2>&1; then
    sudo -n systemctl stop napcat-watchdog >/dev/null 2>&1 || true
fi

docker compose stop "$NAPCAT_SERVICE" >/dev/null 2>&1 || true

if [ -e napcat/qq ] || [ -e napcat/config ] || [ -e napcat/cache ]; then
    mkdir -p "$BACKUP_DIR"
    for name in qq config cache; do
        if [ -e "napcat/$name" ]; then
            mv "napcat/$name" "$BACKUP_DIR/$name"
            echo "Backed up napcat/$name -> $BACKUP_DIR/$name"
        fi
    done
else
    echo "No existing NapCat account data found."
fi

mkdir -p napcat/qq napcat/config napcat/cache napcat/plugins

if [ -f .env ]; then
    tmp=".env.switch-napcat-account.$$"
    awk '
        BEGIN { seen = 0 }
        /^ONEBOT_SELF_ID=/ { print "ONEBOT_SELF_ID="; seen = 1; next }
        { print }
        END { if (!seen) print "ONEBOT_SELF_ID=" }
    ' .env > "$tmp"
    mv "$tmp" .env
    echo "Cleared ONEBOT_SELF_ID in .env so the bot auto-detects the logged-in QQ."
fi

docker compose up -d "$NAPCAT_SERVICE"
sleep 8

container_id=$(docker compose ps -q "$NAPCAT_SERVICE")
if [ -n "$container_id" ]; then
    if docker cp "$container_id:/app/napcat/cache/qrcode.png" "$QR_OUT" >/dev/null 2>&1; then
        echo "QR code exported to $QR_OUT"
    else
        echo "QR code is not ready yet. Check logs below and retry docker cp if needed."
    fi
fi

docker compose logs --tail=80 "$NAPCAT_SERVICE"

cat <<EOF

Next steps:
1. Copy and open the QR code on your Mac:
   scp root@<server-ip>:$QR_OUT ~/Desktop/napcat-qrcode.png
   open ~/Desktop/napcat-qrcode.png

2. Scan it with the QQ account you want to host the bot.

3. After get_login_info returns the new QQ, start the watchdog:
   sudo systemctl start napcat-watchdog
EOF
