#!/bin/bash
# Run this once on any new device to install all systemd services.
# Usage: sudo bash install-service.sh
set -e

CURRENT_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
SYSTEMD_DIR="$SCRIPT_DIR/systemd"

if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo: sudo bash install-service.sh"
    exit 1
fi

# Resolve the actual home directory of the deploying user (not root)
USER_HOME=$(getent passwd "$CURRENT_USER" | cut -d: -f6)
if [[ -z "$USER_HOME" ]]; then
    echo "ERROR: Could not determine home directory for user '$CURRENT_USER'"
    exit 1
fi

echo "Installing services as user: $CURRENT_USER (home: $USER_HOME)"
echo "Project directory: $SCRIPT_DIR"

# root-owned services: substitute /root/AirscopeGuardian with actual project dir
ROOT_SERVICES=("trackerjacker@.service" "trackerjacker-track.service")
for svc in "${ROOT_SERVICES[@]}"; do
    src="$SYSTEMD_DIR/$svc"
    dest="/etc/systemd/system/$svc"
    sed "s|/root/AirscopeGuardian|${SCRIPT_DIR}|g" "$src" > "$dest"
    echo "  Installed $svc"
done

# user-owned services: substitute User= and expand %h with the real home dir
USER_SERVICES=("airscopeguardian.service" "waveshare.service")
for svc in "${USER_SERVICES[@]}"; do
    src="$SYSTEMD_DIR/$svc"
    dest="/etc/systemd/system/$svc"
    sed \
        -e "s/^User=.*/User=${CURRENT_USER}/" \
        -e "s|%h|${USER_HOME}|g" \
        "$src" > "$dest"
    echo "  Installed $svc"
done

systemctl daemon-reload

# Enable and start user-owned services
for svc in "${USER_SERVICES[@]}"; do
    systemctl enable "$svc"
    systemctl restart "$svc"
    echo "  Started $svc"
done

# Enable template and track services (not auto-started — triggered on demand)
systemctl enable "trackerjacker@.service" 2>/dev/null || true

echo ""
echo "Done. Service statuses:"
for svc in "${USER_SERVICES[@]}"; do
    systemctl status "$svc" --no-pager -l 2>&1 | head -5
    echo "---"
done
