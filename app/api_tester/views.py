from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.apps import apps
import json


@login_required
def api_tester_view(request):
    return render(request, 'api_tester/api_tester.html')


# ---------------------------------------------------------------------------
# Schema – reflects the three new kismet models
# ---------------------------------------------------------------------------
FILTER_SCHEMA = {
    "Asset": {
        "label": "Assets",
        "groups": {
            "Identity": ["mac_address", "vendor_oui", "asset_type"],
            "Network":  ["ssid_alias", "operating_channel", "is_encrypted"],
            "Signal":   ["smoothed_rssi", "estimated_radius_meters"],
            "State":    ["is_whitelisted", "first_seen", "last_seen"],
        }
    },
    "SecurityEvent": {
        "label": "Security Events",
        "groups": {
            "Info": ["event_type", "severity", "description"],
            "Time": ["timestamp"],
        }
    },
    "HunterDispatchLog": {
        "label": "Dispatch Logs",
        "groups": {
            "Info": ["admin_id", "locked_channel", "status", "resolution_notes"],
            "Time": ["timestamp"],
        }
    },
}


@login_required
@require_GET
def filter_schema(request):
    return JsonResponse(FILTER_SCHEMA, safe=True)


def get_model(model_name):
    try:
        return apps.get_model("kismet", model_name)
    except LookupError:
        return None


@login_required
@require_POST
def fetch_filtered_data(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON body")

    tables = payload.get("tables")
    if not tables:
        return HttpResponseBadRequest("tables is required")

    response = {}

    for table_name, columns in tables.items():
        model = get_model(table_name)
        if not model:
            continue

        schema = FILTER_SCHEMA.get(table_name)
        if not schema:
            continue

        allowed_columns = set()
        for group_cols in schema["groups"].values():
            allowed_columns.update(group_cols)

        valid_columns = [c for c in columns if c in allowed_columns]
        if not valid_columns:
            continue

        data = list(model.objects.values(*valid_columns)[:5000])
        response[table_name] = data

    return JsonResponse(response)
