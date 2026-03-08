#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="opt/airscope"
VENV_ACTIVATE="venv/bin/activate"
SLEEP_AFTER_STOP=2

if [[ -f "$VENV_ACTIVATE" ]]; then
    source "$VENV_ACTIVATE"
fi

echo ">>> Stopping Kismet..."
if [[ -f /tmp/kismet.pid ]]; then
    KPID=$(cat /tmp/kismet.pid)
    sudo kill "$KPID" || true
    rm /tmp/kismet.pid
else
    echo ">>> Warning: No PID file found, trying pkill..."
    sudo pkill -f kismet || true
fi

echo ">>> Waiting ${SLEEP_AFTER_STOP}s for logs to flush..."
sleep "$SLEEP_AFTER_STOP"

LATEST_DB=$(ls -t "$LOG_DIR"/*.kismet 2>/dev/null | head -n1)
if [[ -z "$LATEST_DB" ]]; then
    echo "Error: No .kismet files found in $LOG_DIR"
    exit 1
fi

echo ">>> Importing latest file: $LATEST_DB"
python manage.py import_kismet "$LATEST_DB"
echo ">>> Import completed successfully."
exit 0
