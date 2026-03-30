from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import connection

import psutil
import platform
import cpuinfo
import datetime
import time
import subprocess
import os
import glob
import socket as _socket

def get_cpu_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000.0, 1)
    except (FileNotFoundError, ValueError):
        return None

@login_required
def system_view(request):
    # --- Disk Info ---
    disk_info = []
    for part in psutil.disk_partitions():
        if 'loop' in part.device:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk_info.append({
                'device': part.device,
                'mountpoint': part.mountpoint,
                'fstype': part.fstype,
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb': round(usage.used / (1024**3), 2),
                'percent': usage.percent,
            })
        except PermissionError:
            continue

    # --- Memory Info ---
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # --- Network I/O ---
    net_io = psutil.net_io_counters()

    # --- System Uptime ---
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time

    # --- CPU Warm-up for accurate process stats ---
    psutil.cpu_percent(interval=None)
    for p in psutil.process_iter():
        p.cpu_percent(interval=None)
    time.sleep(0.5)

    # --- Top Processes ---
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:10]

    # --- CPU Temperature ---
    cpu_temp = get_cpu_temperature()

    sys_info = {
        # === System Basics ===
        'system_name': platform.node(),
        'os_version': platform.platform(),
        'boot_time': boot_time.isoformat(),
        'uptime': str(uptime).split('.')[0],

        # === CPU Info ===
        'processor': cpuinfo.get_cpu_info().get('brand_raw', platform.machine()),
        'cpu_physical_cores': psutil.cpu_count(logical=False),
        'cpu_logical_cores': psutil.cpu_count(logical=True),
        'cpu_current_usage_percent': psutil.cpu_percent(interval=0.5),
        'cpu_per_core': psutil.cpu_percent(interval=0.5, percpu=True),
        'load_average': psutil.getloadavg(),
        'cpu_temperature_c': cpu_temp,

        # === Memory Info ===
        'ram_total_gb': round(mem.total / (1024**3), 2),
        'ram_used_gb': round(mem.used / (1024**3), 2),
        'ram_usage_percent': mem.percent,
        'swap_total_gb': round(swap.total / (1024**3), 2),
        'swap_used_gb': round(swap.used / (1024**3), 2),
        'swap_usage_percent': swap.percent,

        # === Disk Info ===
        'disk_partitions': disk_info,

        # === Network Info ===
        'network_interfaces': psutil.net_if_addrs(),
        'network_io': {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
        },

        # === Process Info ===
        'process_count': len(psutil.pids()),
        'top_processes': processes,
    }

    return render(request, 'system/system.html', {'sys_info': sys_info})

def system_status(request):
    # --- Wireless Interfaces ---
    try:
        iw_output = subprocess.check_output(["iw", "dev"], text=True)
        wlan_list = []
        current = None

        for line in iw_output.splitlines():
            line = line.strip()
            if line.startswith("Interface"):
                current = {"name": line.split()[1]}
            elif "type" in line and current:
                current["type"] = line.split()[-1]
                wlan_list.append(current)
                current = None

    except Exception as e:
        wlan_list = [{"error": f"Failed to get interfaces: {e}"}]

    # --- GPS Detection ---
    gps_devices = glob.glob('/dev/ttyACM*')
    gps_detected = any(os.path.exists(dev) for dev in gps_devices)

    # --- SSH Status ---
    ssh_status = subprocess.getoutput("systemctl is-active ssh") == "active"

    # --- CPU Temperature (for live polling) ---
    cpu_temp = get_cpu_temperature()

    return JsonResponse({
        "interfaces": wlan_list,
        "gps_detected": gps_detected,
        "ssh_status": ssh_status,
        "cpu_temperature_c": cpu_temp,
    })


def _tcp_reachable(host, port, timeout=1.5):
    """Return True if host:port accepts a TCP connection within timeout."""
    try:
        with _socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def heartbeat(request):
    """
    Lightweight health-check used by the SOC footer.
    Returns JSON with the status of DB, Kismet API and tactical node.
    No login required so the footer script can call it before page auth.
    """
    # --- PostgreSQL ---
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    # --- Kismet REST API (port 2501 on localhost) ---
    kismet_ok = _tcp_reachable('127.0.0.1', 2501)

    # --- Tactical node = self (loopback always reachable if this code runs) ---
    node_ok = True

    return JsonResponse({
        'db': db_ok,
        'kismet': kismet_ok,
        'node': node_ok,
    })
