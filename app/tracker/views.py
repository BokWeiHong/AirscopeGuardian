import os
import json
import yaml
import subprocess
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET

SAVES_DIR = '/home/pi/GloopieGuardian/app/tracker/saves'
TRACKING_ENV_FILE = os.path.join(SAVES_DIR, 'tracking.env')
TRACKING_SERVICE = 'trackerjacker-track'

def get_wireless_interface():
    try:
        interfaces = os.listdir('/sys/class/net/')
        wlan_ifaces = [iface for iface in interfaces if iface.startswith('wl')]

        if not wlan_ifaces:
            return None

        def base_name(iface):
            return iface[:-3] if iface.endswith('mon') else iface

        for iface in wlan_ifaces:
            if iface.endswith('mon'):
                b = base_name(iface)
                if b != 'wlan0':
                    return b

        if 'wlan1' in wlan_ifaces and 'wlan1' != 'wlan0':
            return 'wlan1'

        for iface in wlan_ifaces:
            if base_name(iface) != 'wlan0':
                return base_name(iface)

        return None
    except Exception:
        return None

@login_required
def tracker_view(request):
    return render(request, 'tracker/tracker.html')

@require_POST
@login_required
def start_network_scan(request):
    try:
        wifi_iface = get_wireless_interface()
        
        if not wifi_iface:
            return JsonResponse({
                'status': 'error', 
                'message': 'No wireless interface (wlan) found on the system.'
            }, status=400)

        systemctl_cmd = ['sudo', '/bin/systemctl', 'start', f'trackerjacker@{wifi_iface}.service']
        subprocess.run(systemctl_cmd, check=True, capture_output=True, text=True)

        return JsonResponse({
            'status': 'success', 
            'message': f'Scanner started successfully on {wifi_iface} in the background.'
        })

    except subprocess.CalledProcessError as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'Failed to start scanner service: {e.stderr}'
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)


@require_GET
@login_required
def status_network_scan(request):
    try:
        wifi_iface = get_wireless_interface()

        if not wifi_iface:
            return JsonResponse({
                'status': 'inactive',
                'running': False
            })

        systemctl_cmd = ['/bin/systemctl', 'is-active', f'trackerjacker@{wifi_iface}.service']
        proc = subprocess.run(systemctl_cmd, check=False, capture_output=True, text=True)
        active = proc.stdout.strip() == 'active'

        if not active:
            systemctl_cmd2 = ['/bin/systemctl', 'is-active', 'trackerjacker.service']
            proc2 = subprocess.run(systemctl_cmd2, check=False, capture_output=True, text=True)
            active = proc2.stdout.strip() == 'active'

        return JsonResponse({
            'status': 'active' if active else 'inactive',
            'running': active
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'running': False,
            'message': str(e)
        }, status=500)

@require_POST
@login_required
def stop_network_scan(request):
    try:
        wifi_iface = get_wireless_interface()
        
        if not wifi_iface:
            return JsonResponse({
                'status': 'error', 
                'message': 'No wireless interface found to stop.'
            }, status=400)

        systemctl_cmd = ['sudo', '/bin/systemctl', 'stop', f'trackerjacker@{wifi_iface}.service']
        subprocess.run(systemctl_cmd, check=False, capture_output=True, text=True)

        is_active = subprocess.run(
            ['/bin/systemctl', 'is-active', f'trackerjacker@{wifi_iface}.service'],
            check=False, capture_output=True, text=True
        ).stdout.strip()

        if is_active == 'active':
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to stop scanner service on {wifi_iface}.'
            }, status=500)

        return JsonResponse({
            'status': 'success',
            'message': f'Scanner stopped and {wifi_iface} restored to normal mode.'
        })

    except subprocess.CalledProcessError as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'Failed to stop scanner service: {e.stderr}'
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)

@login_required
@require_GET
def get_wifi_map_data(request):
    yaml_file_path = '/home/pi/GloopieGuardian/app/tracker/saves/wifi_map.yaml'

    if not os.path.exists(yaml_file_path):
        return JsonResponse({
            'status': 'waiting',
            'message': 'Scan has not generated data yet. Waiting for trackerjacker...'
        }, status=200)

    try:
        with open(yaml_file_path, 'r') as file:
            wifi_data = yaml.safe_load(file)

        return JsonResponse({
            'status': 'success',
            'data': wifi_data
        }, status=200)

    except yaml.YAMLError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to parse YAML file: {str(e)}'
        }, status=500)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)


# --- Device Tracking ---

@require_POST
@login_required
def start_tracking(request):
    try:
        body = json.loads(request.body)
        mac = body.get('mac', '').strip()
        channels = body.get('channels', '1,2,3,6,10').strip() or '1,2,3,6,10'
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid request body.'}, status=400)

    if not mac:
        return JsonResponse({'status': 'error', 'message': 'MAC address is required.'}, status=400)

    # Reject if already running
    result = subprocess.run(
        ['/bin/systemctl', 'is-active', TRACKING_SERVICE],
        check=False, capture_output=True, text=True
    )
    if result.stdout.strip() == 'active':
        return JsonResponse({'status': 'error', 'message': 'Tracking is already running. Stop it first.'}, status=400)

    wifi_iface = get_wireless_interface()
    if not wifi_iface:
        return JsonResponse({'status': 'error', 'message': 'No wireless interface found.'}, status=400)

    # Write env file for the service to read
    try:
        os.makedirs(SAVES_DIR, exist_ok=True)
        with open(TRACKING_ENV_FILE, 'w') as f:
            f.write(f'TRACK_MAC={mac}\n')
            f.write(f'TRACK_IFACE={wifi_iface}\n')
            f.write(f'TRACK_CHANNELS={channels}\n')
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Failed to write env file: {e}'}, status=500)

    try:
        subprocess.run(
            ['sudo', '/bin/systemctl', 'start', TRACKING_SERVICE],
            check=True, capture_output=True, text=True
        )
        return JsonResponse({'status': 'success', 'message': f'Tracking {mac} on {wifi_iface}mon (channels: {channels})'})
    except subprocess.CalledProcessError as e:
        return JsonResponse({'status': 'error', 'message': f'Failed to start service: {e.stderr}'}, status=500)


@require_POST
@login_required
def stop_tracking(request):
    try:
        subprocess.run(
            ['sudo', '/bin/systemctl', 'stop', TRACKING_SERVICE],
            check=False, capture_output=True, text=True
        )
        return JsonResponse({'status': 'success', 'message': 'Tracking stopped.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_GET
@login_required
def status_tracking(request):
    result = subprocess.run(
        ['/bin/systemctl', 'is-active', TRACKING_SERVICE],
        check=False, capture_output=True, text=True
    )
    active = result.stdout.strip() == 'active'
    return JsonResponse({'status': 'active' if active else 'inactive', 'running': active})


@require_GET
@login_required
def get_tracking_logs(request):
    try:
        result = subprocess.run(
            ['journalctl', '-u', TRACKING_SERVICE, '-n', '100', '--no-pager', '--output=cat'],
            check=False, capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        return JsonResponse({'status': 'success', 'logs': lines})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)