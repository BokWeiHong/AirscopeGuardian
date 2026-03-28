import time
import requests
import os
import sys
import django

# Bootstrap Django so this script can be run as a standalone process by systemd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone
from kismet.models import Asset, SecurityEvent

KISMET_URL = "http://127.0.0.1:2501"

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
    "kismet.device.base.manuf",
    "kismet.device.base.channel",
    "kismet.device.base.crypt",
    "kismet.device.base.name",
    "kismet.device.base.signal"
]

def calculate_fspl_radius(rssi):
    """Translates RSSI to an estimated radius using Free-Space Path Loss."""
    if not rssi or rssi == 0:
        return None
    # Assuming TxPower = -30dBm at 1m, Path Loss Exponent = 3.0
    return round(10 ** ((-30 - rssi) / (10 * 3.0)), 2)

def fetch_kismet_messages(last_poll_time):
    """Polls the Kismet Messagebus for system health logs."""
    endpoint = f"{KISMET_URL}/messagebus/last-time/{last_poll_time}/messages.json"
    try:
        response = SESSION.get(endpoint, timeout=2)
        if response.status_code == 200:
            messages = response.json()
            for msg in messages:
                text = msg.get("kismet.messagebus.message_string", "")
                flags = str(msg.get("kismet.messagebus.message_flags", "")).upper()
                level = 'CRITICAL' if ('FATAL' in flags or 'ERROR' in flags) else \
                        'WARNING' if ('ALERT' in flags or 'WARNING' in flags) else 'INFO'
                print(f"[{level}] KISMET_API: {text}", flush=True)
    except requests.exceptions.RequestException:
        pass  # Handled by the main loop

def run_ingestion_pipeline():
    print("[INFO] Airscope Guardian Ingestion Pipeline successfully started.", flush=True)
    
    last_poll_time = int(time.time()) - 10 # Start polling from 10 seconds ago

    while True:
        try:
            # 1. POLL DEVICE TELEMETRY
            device_endpoint = f"{KISMET_URL}/devices/last-time/{last_poll_time}/devices.json"
            device_resp = SESSION.post(device_endpoint, json={"fields": EKJSON_REGEX}, timeout=2)
            
            if device_resp.status_code == 200:
                devices = device_resp.json()
                for device in devices:
                    # Extract
                    mac = device.get("kismet.device.base.macaddr")
                    raw_type = device.get("kismet.device.base.type", "UNKNOWN")
                    vendor = device.get("kismet.device.base.manuf", "")
                    channel = int(device.get("kismet.device.base.channel", 0))
                    ssid = device.get("kismet.device.base.name", "")
                    
                    crypt_data = device.get("kismet.device.base.crypt", "")
                    is_enc = bool(crypt_data) 
                    
                    signal_dict = device.get("kismet.device.base.signal") or {}
                    # Kismet reports dBm as 'last_signal' (not 'last_signal_dbm')
                    rssi = signal_dict.get("kismet.common.signal.last_signal",
                           signal_dict.get("kismet.common.signal.last_signal_dbm", -100))

                    # Transform
                    asset_type = 'AP' if 'AP' in raw_type else 'CLIENT' if 'Client' in raw_type else 'UNKNOWN'
                    radius_meters = calculate_fspl_radius(rssi)

                    # Load to Database
                    asset, created = Asset.objects.update_or_create(
                        mac_address=mac,
                        defaults={
                            'vendor_oui': vendor,
                            'asset_type': asset_type,
                            'ssid_alias': ssid,
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
            print(f"[WARNING] Kismet API connection dropped. Retrying in 5s. Trace: {e}", flush=True)
            time.sleep(5)  # Graceful degradation

        time.sleep(2) # Polling interval

if __name__ == "__main__":
    run_ingestion_pipeline()