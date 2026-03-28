import os
import json
import math
import sqlite3
from datetime import datetime
from django.db import transaction
from django.utils import timezone

from .models import Asset, SecurityEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def kismet_ts_to_datetime(ts_sec, ts_usec=0):
    if ts_sec is None:
        return None
    try:
        naive = datetime.fromtimestamp(ts_sec + (ts_usec or 0) / 1_000_000)
        return timezone.make_aware(naive, timezone.get_default_timezone())
    except Exception:
        return None


def safe_json_load(val):
    if not val:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


def channel_to_freq_mhz(channel):
    """Convert a WiFi channel number to approximate frequency in MHz."""
    try:
        ch = int(channel)
    except (TypeError, ValueError):
        return 2412  # default 2.4 GHz
    if 1 <= ch <= 14:
        return 2412 + (ch - 1) * 5
    if 36 <= ch <= 165:
        return 5180 + (ch - 36) * 5
    return 2412


def fspl_radius_meters(rssi_dbm, freq_mhz=2412):
    """
    Estimate distance from Free-Space Path Loss formula:
    d = 10 ^ ((27.55 - 20*log10(freq_mhz) + |rssi_dbm|) / 20)
    """
    if rssi_dbm is None:
        return None
    try:
        exponent = (27.55 - 20 * math.log10(freq_mhz) + abs(rssi_dbm)) / 20
        return round(10 ** exponent, 2)
    except (ValueError, ZeroDivisionError):
        return None


def map_asset_type(kismet_type: str) -> str:
    if not kismet_type:
        return 'UNKNOWN'
    t = kismet_type.lower()
    if 'ap' in t or 'access point' in t:
        return 'AP'
    if 'client' in t:
        return 'CLIENT'
    return 'UNKNOWN'


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

def import_kismet_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} does not exist")

    with sqlite3.connect(file_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ---- 1. Devices → Asset ----
        cur.execute("SELECT * FROM devices")
        rows = cur.fetchall()

        for row in rows:
            d_json = safe_json_load(row['device'])
            signal_data = d_json.get("kismet.device.base.signal", {})
            dot11 = d_json.get("dot11.device", {})

            # Determine SSID
            adv_ssid_map = dot11.get("dot11.device.advertised_ssid_map", [])
            ssid_alias = None
            if isinstance(adv_ssid_map, list) and adv_ssid_map:
                ssid_alias = adv_ssid_map[0].get("dot11.advertisedssid.ssid") or None
            elif isinstance(adv_ssid_map, dict) and adv_ssid_map:
                first = next(iter(adv_ssid_map.values()), {})
                ssid_alias = first.get("dot11.advertisedssid.ssid") or None

            if not ssid_alias:
                ssid_alias = d_json.get("kismet.device.base.name") or None

            # Encryption
            crypt = d_json.get("kismet.device.base.crypt") or ""
            is_encrypted = bool(crypt and crypt.lower() not in ("none", "open", ""))

            # Signal
            smoothed_rssi = (
                signal_data.get("kismet.common.signal.avg_signal")
                or row['strongest_signal']
                or None
            )
            if isinstance(smoothed_rssi, float):
                smoothed_rssi = int(smoothed_rssi)

            # Channel and FSPL radius
            channel = d_json.get("kismet.device.base.channel")
            freq = channel_to_freq_mhz(channel) if channel else 2412
            radius = fspl_radius_meters(smoothed_rssi, freq)

            asset_type = map_asset_type(row['type'])
            mac = row['devmac']
            vendor = d_json.get("kismet.device.base.manuf")

            first_seen_ts = kismet_ts_to_datetime(row['first_time'])

            with transaction.atomic():
                Asset.objects.update_or_create(
                    mac_address=mac,
                    defaults={
                        'vendor_oui': vendor or None,
                        'asset_type': asset_type,
                        'ssid_alias': ssid_alias,
                        'operating_channel': int(channel) if channel else None,
                        'is_encrypted': is_encrypted,
                        'smoothed_rssi': smoothed_rssi,
                        'estimated_radius_meters': radius,
                        'first_seen': first_seen_ts or timezone.now(),
                    }
                )

        # ---- 2. Alerts → SecurityEvent ----
        cur.execute("SELECT * FROM alerts")
        for r in cur.fetchall():
            devmac = r['devmac']
            if not devmac:
                continue
            asset = Asset.objects.filter(mac_address=devmac).first()
            if not asset:
                # Create a placeholder asset so the FK is satisfied
                asset, _ = Asset.objects.get_or_create(
                    mac_address=devmac,
                    defaults={'asset_type': 'UNKNOWN'}
                )
            ts = kismet_ts_to_datetime(r['ts_sec']) or timezone.now()
            SecurityEvent.objects.create(
                timestamp=ts,
                asset=asset,
                event_type=r['header'] or 'Unknown Alert',
                severity='MEDIUM',
                description=str(safe_json_load(r['json'])),
            )
