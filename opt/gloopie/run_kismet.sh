#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="opt/airscope"
VENV_ACTIVATE="venv/bin/activate"
ELIGIBLE_IFACE="$1"

if [[ -f "$VENV_ACTIVATE" ]]; then
  source "$VENV_ACTIVATE"
fi

if [[ -z "$ELIGIBLE_IFACE" ]]; then
  echo "Error: No interface specified."
  echo "Usage: $0 <interface>"
  exit 1
fi

if ! iw dev | awk '$1=="Interface"{print $2}' | grep -qx "$ELIGIBLE_IFACE"; then
  echo "Error: Interface '$ELIGIBLE_IFACE' not found."
  exit 1
fi

echo ">>> Starting Kismet on interface: $ELIGIBLE_IFACE"
sudo kismet -c "$ELIGIBLE_IFACE" > "$LOG_DIR/kismet_output.log" 2>&1 &
KISMET_PID=$!

echo ">>> Kismet started with PID $KISMET_PID"
echo "$KISMET_PID" > /tmp/kismet.pid
echo ">>> Logs are being written to $LOG_DIR/kismet_output.log"
exit 0
