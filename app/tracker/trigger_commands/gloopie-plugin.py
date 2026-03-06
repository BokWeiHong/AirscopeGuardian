"""
GloopieGuardian Target Tracker & Distance Estimator
"""
import math

__apiversion__ = 1
__config__ = {'power': -100, 'log_level': 'ERROR', 'trigger_cooldown': 0.5}

class Trigger:
    def calculate_distance(self, rssi):
        """Converts dBm to estimated meters."""
        n = 2.5 
        tx_power = -55
        return 10 ** ((tx_power - rssi) / (10 * n))

    def __call__(self, dev_id=None, vendor=None, power=None, **kwargs):
        if dev_id:
            if power is not None:
                dist = self.calculate_distance(power)
                vendor_str = vendor if vendor else 'N/A'
                print(f"TARGET LOCKED: {dev_id} | Vendor: {vendor_str} | Power: {power}dBm | Dist: {dist:.2f}m")
            else:
                print(f"Target {dev_id} detected, but no power data available.")