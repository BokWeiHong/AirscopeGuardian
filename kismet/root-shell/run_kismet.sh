#!/usr/bin/env bash
# run_kismet.sh — auto-detect a monitor-capable USB WiFi adapter,
# switch it to monitor mode, and launch Kismet.
set -euo pipefail

# Resolve project root from this script's location (kismet/root-shell/ -> project root)
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PROJECT_DIR="$(cd "${_SCRIPT_DIR}/../.." && pwd)"

LOG_DIR="${_PROJECT_DIR}/kismet/logs"
VENV_ACTIVATE="${_PROJECT_DIR}/venv/bin/activate"

# ---------------------------------------------------------------------------
# 1. Discover the best interface
# ---------------------------------------------------------------------------
# Priority:
#   (a) USB adapters that support monitor mode — Alfa, Panda, TP-Link, etc.
#   (b) Any other wireless interface that supports monitor mode
# We inspect /sys to tell USB from built-in, and `iw phy` to check for
# monitor-mode support without actually changing anything yet.

find_interface() {
    local best=""
    local fallback=""

    while IFS= read -r iface; do
        # Skip loopback / virtual
        [[ "$iface" == lo ]] && continue

        # Resolve the phy name for this interface
        local phy
        phy=$(iw dev "$iface" info 2>/dev/null | awk '/wiphy/{print "phy"$2}') || continue
        [[ -z "$phy" ]] && continue

        # Check monitor mode support
        if ! iw phy "$phy" info 2>/dev/null | grep -q "monitor"; then
            continue
        fi

        # Check if the adapter is USB (path contains /usb)
        local dev_path
        dev_path=$(readlink -f "/sys/class/net/$iface/device" 2>/dev/null || true)
        if echo "$dev_path" | grep -qi "usb"; then
            # Prefer Alfa / known high-power USB vendor IDs if detectable
            # Alfa uses Ralink (148f), Atheros (0cf3), Realtek (0bda), MediaTek (0e8d)
            local vendor=""
            vendor=$(cat "/sys/class/net/$iface/device/../idVendor" 2>/dev/null \
                  || cat "/sys/class/net/$iface/device/../../idVendor" 2>/dev/null \
                  || true)
            case "$vendor" in
                148f|0cf3|0bda|0e8d|2357|0846|13b1)
                    # Known chipset vendors used by Alfa, Panda, TP-Link, Netgear
                    best="$iface"
                    break
                    ;;
                *)
                    # Generic USB adapter — use as fallback
                    [[ -z "$fallback" ]] && fallback="$iface"
                    ;;
            esac
        else
            # Built-in adapter — lowest priority fallback
            [[ -z "$fallback" ]] && fallback="$iface"
        fi
    done < <(iw dev 2>/dev/null | awk '$1=="Interface"{print $2}')

    echo "${best:-$fallback}"
}

IFACE=$(find_interface)

if [[ -z "$IFACE" ]]; then
    echo "ERROR: No monitor-capable wireless interface found. Aborting." >&2
    exit 1
fi

echo ">>> Selected interface: $IFACE"

# ---------------------------------------------------------------------------
# 2. Switch to monitor mode
# ---------------------------------------------------------------------------
echo ">>> Switching $IFACE to monitor mode..."

# Bring down, change type, bring up — preserves the interface name (no mon0 rename)
ip link set "$IFACE" down
iw dev "$IFACE" set type monitor
ip link set "$IFACE" up

# Brief pause so the kernel finishes the mode switch
sleep 1

# Confirm
CURRENT_MODE=$(iw dev "$IFACE" info 2>/dev/null | awk '/type/{print $2}')
if [[ "$CURRENT_MODE" != "monitor" ]]; then
    echo "ERROR: Failed to set $IFACE to monitor mode (current: $CURRENT_MODE)." >&2
    exit 1
fi
echo ">>> $IFACE is now in monitor mode."

# ---------------------------------------------------------------------------
# 3. Prepare and launch Kismet
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
chmod 770 "$LOG_DIR"

[[ -f "$VENV_ACTIVATE" ]] && source "$VENV_ACTIVATE"

echo ">>> Starting Kismet on $IFACE ..."
# exec hands the PID directly to systemd (Type=simple)
exec kismet --no-ncurses-wrapper -c "$IFACE" -l "${LOG_DIR}/Kismet"
