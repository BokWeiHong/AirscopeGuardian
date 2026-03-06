import os
import glob
import yaml
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

SAVES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tracker', 'saves')


@login_required
def history_view(request):
    pattern = os.path.join(SAVES_DIR, 'wifi_map.yaml.*.bak')
    files = sorted(glob.glob(pattern), reverse=True)

    files_info = []
    for f in files:
        fname = os.path.basename(f)
        try:
            ts_part = fname.replace('wifi_map.yaml.', '').replace('.bak', '')
            dt = datetime.strptime(ts_part, '%Y%m%d-%H%M%S')
            label = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            label = fname
        files_info.append({'filename': fname, 'label': label})

    return render(request, 'tracker_history/history.html', {'bak_files': files_info})


@login_required
def history_wifi_data(request):
    filename = request.GET.get('file', '')

    if not filename.endswith('.bak') or '/' in filename or '..' in filename:
        return JsonResponse({'status': 'error', 'message': 'Invalid filename'}, status=400)

    filepath = os.path.join(SAVES_DIR, filename)
    if not os.path.exists(filepath):
        return JsonResponse({'status': 'error', 'message': 'File not found'}, status=404)

    try:
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return JsonResponse({'status': 'success', 'data': data or {}})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)