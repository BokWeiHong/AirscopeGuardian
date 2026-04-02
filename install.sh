#!/usr/bin/env bash
# install.sh — install AirscopeGuardian systemd services on any machine.
#
# Usage:
#   sudo ./install.sh [--user <username>] [--project-dir <path>]
#
# Defaults:
#   --user        $(logname)  (the user who called sudo, not root)
#   --project-dir directory containing this script
#
# What it does:
#   1. Patches each *.service file in systemd/ replacing placeholder paths
#      with the real project directory and username.
#   2. Copies the patched files to /etc/systemd/system/
#   3. Reloads systemd and enables the services.

set -euo pipefail

# ── defaults ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
SERVICE_USER="${SUDO_USER:-$(logname 2>/dev/null || echo pi)}"

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)        SERVICE_USER="$2"; shift 2 ;;
        --project-dir) PROJECT_DIR="$2";  shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

VENV_BIN="${PROJECT_DIR}/venv/bin"

echo "Installing AirscopeGuardian services"
echo "  Project dir : ${PROJECT_DIR}"
echo "  Service user: ${SERVICE_USER}"
echo "  Venv bin    : ${VENV_BIN}"
echo ""

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: run this script with sudo." >&2
    exit 1
fi

# ── patch and install each service file ───────────────────────────────────────
for src in "${PROJECT_DIR}/systemd/"*.service; do
    name="$(basename "${src}")"
    dest="/etc/systemd/system/${name}"

    sed \
        -e "s|@@PROJECT_DIR@@|${PROJECT_DIR}|g" \
        -e "s|@@SERVICE_USER@@|${SERVICE_USER}|g" \
        "${src}" > "${dest}"

    echo "  installed ${dest}"
done

# ── patch and install run_kismet.sh ───────────────────────────────────────────
KISMET_SHELL="${PROJECT_DIR}/kismet/root-shell/run_kismet.sh"
if [[ -f "${KISMET_SHELL}" ]]; then
    sed -i \
        -e "s|/home/pi/AirscopeGuardian|${PROJECT_DIR}|g" \
        "${KISMET_SHELL}"
    chmod +x "${KISMET_SHELL}"
    echo "  patched ${KISMET_SHELL}"
fi

# ── reload systemd ────────────────────────────────────────────────────────────
systemctl daemon-reload

echo ""
echo "Done. Enable services with:"
echo "  sudo systemctl enable --now airscopeguardian.service"
echo "  sudo systemctl enable --now kismet.service"
echo "  sudo systemctl enable --now kismet-ingest.service"
echo "  sudo systemctl enable --now waveshare.service"
