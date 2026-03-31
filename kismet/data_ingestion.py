import time
import threading
import requests
import os
import sys
import django

# Bootstrap Django so this script can be run as a standalone process by systemd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone
from kismet.models import Asset, SecurityEvent, SystemMessage

KISMET_URL = "http://127.0.0.1:2501"
KISMET_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "kismet_output.log"
)

# ---------------------------------------------------------------------------
# Transparent auth: reads credentials from Kismet's own auth file automatically.
# No credentials are hardcoded here — Kismet manages them.
# ---------------------------------------------------------------------------
def _load_kismet_auth():
    search_paths = [
        "/root/.kismet/kismet_httpd.conf",
        "/home/pi/.kismet/kismet_httpd.conf",
        "/home/pi/kismet/conf/kismet_httpd.conf",
    ]
    user = os.environ.get("KISMET_USER")
    pwd  = os.environ.get("KISMET_PASS")
    if not (user and pwd):
        for path in search_paths:
            try:
                cfg = {}
                with open(path) as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            cfg[k.strip()] = v.strip()
                user = user or cfg.get("httpd_username")
                pwd  = pwd  or cfg.get("httpd_password")
                if user and pwd:
                    break
            except OSError:
                continue
    return (user, pwd) if (user and pwd) else None

SESSION = requests.Session()
_auth = _load_kismet_auth()
if _auth:
    SESSION.auth = _auth

# The specific data we want from Kismet to save bandwidth and CPU
EKJSON_REGEX = [
    "kismet.device.base.macaddr",
    "kismet.device.base.type",
    "kismet.device.base.phyname",
    "kismet.device.base.manuf",
    "kismet.device.base.channel",
    "kismet.device.base.crypt",
    "kismet.device.base.name",
    "kismet.device.base.signal",
    # Nested path syntax required — flat "dot11.device.last_bssid" returns integer 0
    "dot11.device/dot11.device.last_bssid",
]

# Exact Kismet type strings → Asset.ASSET_TYPES choices
# Confirmed from live API: Wi-Fi AP, Wi-Fi Client, Wi-Fi Bridged,
# Wi-Fi Device, Wi-Fi WDS, Wi-Fi WDS AP, Wi-Fi Ad-Hoc
_TYPE_MAP = {
    "wi-fi ap":      "AP",
    "wi-fi wds ap":  "AP",
    "wi-fi ad-hoc":  "AP",
    "wi-fi client":  "CLIENT",
    "wi-fi bridged": "CLIENT",
    "wi-fi wds":     "CLIENT",
    "wi-fi device":  "UNKNOWN",
}

def calculate_fspl_radius(rssi):
    """Translates RSSI to an estimated radius using Free-Space Path Loss."""
    if not rssi or rssi == 0:
        return None
    # Assuming TxPower = -30dBm at 1m, Path Loss Exponent = 3.0
    return int(round(10 ** ((-30 - rssi) / (10 * 3.0))))

def _log(level, component, message):
    """Write a message to the SystemMessage table and stdout."""
    print(f"[{level}] {component}: {message}", flush=True)
    try:
        SystemMessage.objects.create(level=level, component=component, message=message)
    except Exception:
        pass  # Never let logging crash the pipeline

def fetch_kismet_messages(last_poll_time):
    """Polls the Kismet Messagebus and saves entries to SystemMessage table."""
    endpoint = f"{KISMET_URL}/messagebus/last-time/{last_poll_time}/messages.json"
    try:
        response = SESSION.get(endpoint, timeout=2)
        if response.status_code == 200:
            messages = response.json()
            for msg in messages:
                text = msg.get("kismet.messagebus.message_string", "").strip()
                if not text:
                    continue
                flags = str(msg.get("kismet.messagebus.message_flags", "")).upper()
                level = 'CRITICAL' if ('FATAL' in flags or 'ERROR' in flags) else \
                        'WARNING' if ('ALERT' in flags or 'WARNING' in flags) else 'INFO'
                _log(level, 'KISMET_API', text)
    except requests.exceptions.RequestException:
        pass  # Handled by the main loop

def _parse_log_level(line):
    """Map Kismet log prefixes to SystemMessage level choices."""
    upper = line.upper()
    if upper.startswith('FATAL') or 'FATAL' in upper[:12]:
        return 'CRITICAL'
    if upper.startswith('ERROR') or 'ERROR' in upper[:12]:
        return 'ERROR'
    if upper.startswith('WARNING') or 'WARNING' in upper[:12]:
        return 'WARNING'
    return 'INFO'


def _tail_kismet_log(seed_lines=200):
    """Background thread: tail kismet_output.log and write each new line to SystemMessage.
    Seeds the table with the last `seed_lines` lines on startup."""
    # Wait for the file to appear (Kismet may not have created it yet)
    while not os.path.exists(KISMET_LOG_PATH):
        time.sleep(2)

    def _save(line):
        line = line.strip()
        if not line:
            return
        level = _parse_log_level(line)
        try:
            SystemMessage.objects.create(level=level, component='KISMET_API', message=line)
        except Exception:
            pass

    with open(KISMET_LOG_PATH, 'r') as fh:
        # --- Seed: read last N lines without loading the whole file ---
        try:
            fh.seek(0, 2)
            end = fh.tell()
            chunk = min(end, 32768)          # read up to 32 KB from the end
            fh.seek(max(0, end - chunk))
            recent = fh.readlines()[-seed_lines:]
            for line in recent:
                _save(line)
        except Exception:
            pass

        # --- Tail: continue reading new lines as Kismet writes them ---
        fh.seek(0, 2)  # jump back to current end
        while True:
            line = fh.readline()
            if not line:
                time.sleep(0.5)
                continue
            _save(line)


def run_ingestion_pipeline():
    _log('INFO', 'MIDDLEWARE', 'Airscope Guardian Ingestion Pipeline successfully started.')

    # Start background thread to capture kismet_output.log lines into SystemMessage
    log_thread = threading.Thread(target=_tail_kismet_log, daemon=True, name='kismet-log-tailer')
    log_thread.start()

    last_poll_time = int(time.time()) - 10 # Start polling from 10 seconds ago

    while True:
        try:
            # 1. POLL DEVICE TELEMETRY
            device_endpoint = f"{KISMET_URL}/devices/last-time/{last_poll_time}/devices.json"
            device_resp = SESSION.post(device_endpoint, json={"fields": EKJSON_REGEX}, timeout=2)
            
            if device_resp.status_code == 200:
                devices = device_resp.json()
                for device in devices:
                    # --- Extract ---
                    mac = device.get("kismet.device.base.macaddr")
                    if not mac:          # skip any device without a usable MAC
                        continue

                    raw_type = (device.get("kismet.device.base.type") or "").strip()
                    vendor    = (device.get("kismet.device.base.manuf") or "").strip()
                    ssid      = (device.get("kismet.device.base.name")  or "").strip()

                    # Extract BSSID association.
                    # Requested via nested path "dot11.device/dot11.device.last_bssid";
                    # the response key is still "dot11.device.last_bssid" but now returns
                    # a real MAC (e.g. "BA:D6:F6:49:23:C4") instead of integer 0.
                    raw_bssid = device.get("dot11.device.last_bssid") or ""
                    last_bssid = str(raw_bssid).strip()
                    if last_bssid in ("", "0", "00:00:00:00:00:00"):
                        last_bssid = ""
                    raw_chan = device.get("kismet.device.base.channel") or 0
                    try:
                        channel = int(raw_chan)
                    except (ValueError, TypeError):
                        channel = 0

                    # Encryption: non-empty crypt string means encrypted
                    crypt_data = (device.get("kismet.device.base.crypt") or "").strip()
                    is_enc = bool(crypt_data)

                    # Signal: Kismet uses 'last_signal' (confirmed from live data)
                    signal_dict = device.get("kismet.device.base.signal") or {}
                    rssi = (
                        signal_dict.get("kismet.common.signal.last_signal")
                        or signal_dict.get("kismet.common.signal.last_signal_dbm")
                        or -100
                    )

                    # --- Transform ---
                    # Use exact type map; fall back to substring heuristic for safety
                    asset_type = _TYPE_MAP.get(raw_type.lower())
                    if asset_type is None:
                        lower = raw_type.lower()
                        if "ap" in lower or "access point" in lower:
                            asset_type = "AP"
                        elif "client" in lower or "sta" in lower or "bridged" in lower:
                            asset_type = "CLIENT"
                        else:
                            asset_type = "UNKNOWN"

                    radius_meters = calculate_fspl_radius(rssi)

                    # Resolve connected_bssid: only meaningful for CLIENT devices
                    connected_bssid = None
                    if asset_type == 'CLIENT' and last_bssid not in ('', '00:00:00:00:00:00'):
                        connected_bssid = last_bssid

                    # Load to Database
                    asset, created = Asset.objects.update_or_create(
                        mac_address=mac,
                        defaults={
                            'vendor_oui': vendor,
                            'asset_type': asset_type,
                            'ssid_alias': ssid,
                            'connected_bssid': connected_bssid,
                            'operating_channel': channel,
                            'is_encrypted': is_enc,
                            'smoothed_rssi': rssi,
                            'estimated_radius_meters': radius_meters,
                            'last_seen': timezone.now()
                        }
                    )

                    # Generate Security Events
                    if created and not asset.is_whitelisted:
                        SecurityEvent.objects.create(
                            asset=asset,
                            event_type="Unknown Asset Discovery",
                            severity="LOW",
                            description=f"A new {asset_type} ({vendor}) was detected broadcasting on channel {channel}."
                        )
                    elif not created and not asset.is_whitelisted:
                        if radius_meters and radius_meters < 5.0:
                            # Add advanced logic here later to prevent spamming
                            pass 

            # 2. POLL SYSTEM HEALTH MESSAGES
            fetch_kismet_messages(last_poll_time)
            
            # Sync timestamp for next loop
            last_poll_time = int(time.time())
                
        except requests.exceptions.RequestException as e:
            _log('WARNING', 'KISMET_API', f"Kismet API connection dropped. Retrying in 5s. Trace: {e}")
            time.sleep(5)  # Graceful degradation

        time.sleep(2) # Polling interval

if __name__ == "__main__":
    run_ingestion_pipeline()