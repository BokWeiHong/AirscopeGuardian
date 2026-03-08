#!/usr/bin/env bash
set -euo pipefail

# Absolute paths
LOG_DIR="/home/pi/AirscopeGuardian/kismet/logs"
VENV_ACTIVATE="/home/pi/AirscopeGuardian/venv/bin/activate"

ELIGIBLE_IFACE="${1:-}"

if [[ -z "$ELIGIBLE_IFACE" ]]; then
  echo "Error: No interface specified."
  echo "Usage: $0 <interface>"
  exit 1
fi

# validate interface exists
if ! iw dev | awk '$1=="Interface"{print $2}' | grep -qx "$ELIGIBLE_IFACE"; then
  echo "Error: Interface '$ELIGIBLE_IFACE' not found."
  exit 1
fi

# ensure log dir exists
mkdir -p "$LOG_DIR"
chmod 770 "$LOG_DIR"

if [[ -f "$VENV_ACTIVATE" ]]; then
  source "$VENV_ACTIVATE"
fi

echo ">>> Starting Kismet on interface: $ELIGIBLE_IFACE"
# exec replaces the shell so systemd tracks kismet's PID directly (Type=simple)
exec kismet --no-ncurses-wrapper -c "$ELIGIBLE_IFACE" -l "${LOG_DIR}/Kismet"
