"""
AirscopeGuardian Target Tracker & Proximity Estimator
"""
import math
import json
import os
import time
import threading

__apiversion__ = 1
__config__ = {
    'log_level': 'ERROR',
    'trigger_cooldown': 0.5,
}

_PLUGIN_CONFIG = {
    'power_threshold': -100,   # ignore devices below this dBm
    'ref_power': -55,          # RSSI at 1 metre
    'path_loss_n': 2.5,        # environmental path-loss exponent
}

class Trigger:
    def __init__(self):
        self.thresholds = {
            "Very Near": -45,
            "Near": -60,
            "A bit Far": -75,
            "Far": -85
        }
        self.history = {}

        self._lock = threading.Lock()
        save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'app', 'tracker', 'saves')
        os.makedirs(save_dir, exist_ok=True)
        self._save_path = os.path.join(save_dir, 'targets.json')

        if not os.path.exists(self._save_path):
            try:
                with open(self._save_path, 'w') as f:
                    json.dump({}, f)
            except Exception:
                pass

    def get_proximity_label(self, rssi):
        """Categorizes the RSSI into human terms."""
        if rssi >= self.thresholds["Very Near"]:
            return "VERY NEAR"
        elif rssi >= self.thresholds["Near"]:
            return "NEAR"
        elif rssi >= self.thresholds["A bit Far"]:
            return "A BIT FAR"
        elif rssi >= self.thresholds["Far"]:
            return "FAR"
        else:
            return "VERY FAR"

    def calculate_distance(self, rssi):
        """Converts dBm to estimated meters using config variables."""
        n = _PLUGIN_CONFIG['path_loss_n']
        tx_power = _PLUGIN_CONFIG['ref_power']
        return 10 ** ((tx_power - rssi) / (10 * n))

    def _load_store(self):
        try:
            with open(self._save_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_store(self, store):
        tmp = self._save_path + '.tmp'
        try:
            with open(tmp, 'w') as f:
                json.dump(store, f)
            os.replace(tmp, self._save_path)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    def __call__(self, dev_id=None, vendor=None, power=None, **kwargs):
        if dev_id and power is not None:
            if dev_id not in self.history:
                self.history[dev_id] = []
            
            self.history[dev_id].append(power)
            if len(self.history[dev_id]) > 3:
                self.history[dev_id].pop(0)
            
            avg_power = sum(self.history[dev_id]) / len(self.history[dev_id])

            dist = self.calculate_distance(avg_power)
            label = self.get_proximity_label(avg_power)

            vendor_str = vendor if vendor else 'N/A'

            print(f"[{label}] ID: {dev_id} | Vendor: {vendor_str} | Power: {power}dBm | Est: {dist:.1f}m")

            record = {
                'mac': dev_id,
                'label': label,
                'power': round(avg_power, 1),
                'dist': round(dist, 1),
                'vendor': vendor_str,
                'ts': int(time.time())
            }
            try:
                with self._lock:
                    store = self._load_store()
                    store[dev_id] = record
                    self._save_store(store)
            except Exception:
                pass
            
        elif dev_id:
            print(f"Target {dev_id} detected, but no power data available.")