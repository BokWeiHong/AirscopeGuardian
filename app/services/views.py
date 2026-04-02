from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import subprocess
import os
import json
import shutil
import signal
from django.conf import settings

# =========================
# === KISMET SETTINGS ===
# =========================
LOG_FILE = str(settings.KISMET_LOG_PATH)
KISMET_IFACE_FILE = "/tmp/kismet_active_iface"

# =========================
# === WASMSHARK (STATIC SERVE) ===
# =========================
WASMSHARK_DIR = settings.WASMSHARK_DIR
WASMSHARK_PORT = 8085
WASMSHARK_PCAP_DIR = str(settings.KISMET_PCAP_DIR)
WASMSHARK_PID_FILE = "/tmp/wasmshark.pid"
WEB_BUILD_DIR = os.path.join(WASMSHARK_DIR, "dist/webshark")
AUTO_PCAP_PATH = os.path.join(WEB_BUILD_DIR, "assets/auto.pcap")


@login_required
def services_view(request):
    return render(request, "services/services.html")


# -----------------
# === KISMET ===
# -----------------
@login_required
def get_interfaces(request):
    try:
        result = subprocess.check_output(
            "iw dev | awk '$1==\"Interface\"{print $2}'",
            shell=True
        )
        interfaces = [i for i in result.decode().split() if i]
        return JsonResponse({"interfaces": interfaces})
    except subprocess.CalledProcessError:
        return JsonResponse({"error": "Failed to fetch interfaces"}, status=500)


@login_required
def run_kismet(request):
    iface = request.GET.get("iface")
    if not iface:
        return JsonResponse({"error": "Missing interface"}, status=400)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Persist interface name so stop_kismet knows which instance to stop
    with open(KISMET_IFACE_FILE, "w") as f:
        f.write(iface)

    result = subprocess.run(
        ["sudo", "systemctl", "start", f"kismet@{iface}"],
        capture_output=True
    )
    if result.returncode != 0:
        return JsonResponse({"error": result.stderr.decode()}, status=500)

    return JsonResponse({"status": "running"})


@login_required
def stop_kismet(request):
    iface = None
    if os.path.exists(KISMET_IFACE_FILE):
        with open(KISMET_IFACE_FILE) as f:
            iface = f.read().strip()
        os.remove(KISMET_IFACE_FILE)

    if iface:
        subprocess.run(
            ["sudo", "systemctl", "stop", f"kismet@{iface}"],
            check=False
        )
    else:
        # Fallback: stop any running kismet@ instance
        subprocess.run(
            ["sudo", "systemctl", "stop", "kismet@.service"],
            check=False
        )

    return JsonResponse({"status": "stopped"})


@login_required
def kismet_logs(request):
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()[-30:]
        output = []
        for line in lines:
            output.append(line.rstrip())
            output.append("")
        return JsonResponse({"logs": output})
    except FileNotFoundError:
        return JsonResponse({"logs": ["No logs yet."]})


@login_required
def list_pcaps(request):
    if not os.path.isdir(WASMSHARK_PCAP_DIR):
        return JsonResponse({"pcaps": []})
    pcaps = []
    for fname in sorted(os.listdir(WASMSHARK_PCAP_DIR)):
        if fname.endswith((".pcap", ".pcapng")):
            pcaps.append({
                "name": fname,
                "path": os.path.join(WASMSHARK_PCAP_DIR, fname)
            })
    return JsonResponse({"pcaps": pcaps})


# -----------------
# === WebShark ===
# -----------------
def _stop_wasmshark_process():
    if os.path.exists(WASMSHARK_PID_FILE):
        with open(WASMSHARK_PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGKILL)  # Use SIGKILL to force kill
        except ProcessLookupError:
            pass
        os.remove(WASMSHARK_PID_FILE)


@login_required
@require_POST
@csrf_protect
def run_webshark(request):
    try:
        body = json.loads(request.body)
        pcap = body.get("file")  # full path to PCAP
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not pcap or not os.path.isfile(pcap):
        return JsonResponse({"error": "PCAP file not found"}, status=400)

    # Stop any existing server
    _stop_wasmshark_process()

    # Copy PCAP to production build assets
    os.makedirs(os.path.dirname(AUTO_PCAP_PATH), exist_ok=True)
    shutil.copy(pcap, AUTO_PCAP_PATH)

    # Start static server
    log_file = "/tmp/wasmshark.log"
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            ["serve", "-s", WEB_BUILD_DIR, "-l", str(WASMSHARK_PORT)],
            cwd=WASMSHARK_DIR,
            stdout=log,
            stderr=log,
            preexec_fn=os.setsid
        )

    with open(WASMSHARK_PID_FILE, "w") as f:
        f.write(str(proc.pid))

    # Wait a bit for the server to start
    import time
    time.sleep(2)

    return JsonResponse({
        "status": "running",
        "pcap": os.path.basename(pcap),
        "url": f"http://localhost:{WASMSHARK_PORT}"
    })


@login_required
@require_POST
@csrf_protect
def stop_webshark(request):
    _stop_wasmshark_process()
    return JsonResponse({"status": "stopped"})
