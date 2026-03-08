#!/usr/bin/env bash
set -euo pipefail

# Absolute paths
LOG_DIR="/home/pi/AirscopeGuardian/kismet/logs"
VENV_ACTIVATE="/home/pi/AirscopeGuardian/venv/bin/activate"
PROJECT_DIR="/home/pi/AirscopeGuardian"
MANAGE_PY="${PROJECT_DIR}/manage.py"

if [[ -f "$VENV_ACTIVATE" ]]; then
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
fi

# kismet is already stopped by systemd before ExecStopPost runs;
# wait briefly to ensure its DB file is fully flushed to disk.
echo ">>> Waiting for kismet logs to flush..."
sleep 2

LATEST_DB=$(ls -t "${LOG_DIR}"/*.kismet 2>/dev/null | head -n1 || true)
if [[ -z "$LATEST_DB" ]]; then
    echo "Error: No .kismet files found in ${LOG_DIR}"
    exit 1
fi

echo ">>> Importing latest file: $LATEST_DB"

# ensure manage.py exists
if [[ ! -f "$MANAGE_PY" ]]; then
    echo "Error: manage.py not found at $MANAGE_PY. Please update PROJECT_DIR in this script."
    exit 1
fi

# run the Django import command from project dir
cd "$PROJECT_DIR"
python "$MANAGE_PY" import_kismet "$LATEST_DB"

echo ">>> Import completed successfully."
exit 0
