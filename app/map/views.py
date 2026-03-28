from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from kismet.models import Asset, SecurityEvent


@login_required
def map_view(request):
    return render(request, 'map/map.html')


def api_aps(request):
    """Return all AP-type assets. Clients can filter by asset_type query param."""
    asset_type = request.GET.get('asset_type', 'AP')
    if asset_type == 'ALL':
        qs = Asset.objects.all()
    else:
        qs = Asset.objects.filter(asset_type=asset_type)

    data = [
        {
            'id': a.id,
            'mac_address': a.mac_address,
            'vendor_oui': a.vendor_oui,
            'asset_type': a.asset_type,
            'ssid_alias': a.ssid_alias,
            'operating_channel': a.operating_channel,
            'is_encrypted': a.is_encrypted,
            'smoothed_rssi': a.smoothed_rssi,
            'estimated_radius_meters': a.estimated_radius_meters,
            'is_whitelisted': a.is_whitelisted,
            'first_seen': a.first_seen.isoformat() if a.first_seen else None,
            'last_seen': a.last_seen.isoformat() if a.last_seen else None,
        }
        for a in qs
    ]
    return JsonResponse(data, safe=False)


def api_monitoring_path(request):
    """
    With the new Asset model there is no per-packet GPS data.
    Returns a summary of asset counts by type instead.
    """
    return JsonResponse({
        'success': True,
        'note': 'GPS tracking not available with current data model. Use asset radius data.',
        'total_assets': Asset.objects.count(),
        'access_points': Asset.objects.filter(asset_type='AP').count(),
        'clients': Asset.objects.filter(asset_type='CLIENT').count(),
    })


def api_client_graph(request):
    """
    Build a Cytoscape-compatible node graph from Asset records.
    APs and Clients are separate node types; SecurityEvents form edges.
    """
    elements = []
    added_nodes = set()

    for asset in Asset.objects.all():
        node_id = f"asset-{asset.id}"
        if node_id not in added_nodes:
            elements.append({
                "data": {
                    "id": node_id,
                    "label": asset.ssid_alias or asset.mac_address,
                    "mac": asset.mac_address,
                    "type": asset.asset_type,
                    "vendor": asset.vendor_oui or "Unknown",
                    "channel": asset.operating_channel,
                    "encrypted": asset.is_encrypted,
                    "signal": asset.smoothed_rssi,
                    "radius": asset.estimated_radius_meters,
                    "whitelisted": asset.is_whitelisted,
                }
            })
            added_nodes.add(node_id)

    # SecurityEvents as edges pointing from asset → a central "threat" node
    for event in SecurityEvent.objects.select_related('asset').order_by('-timestamp')[:200]:
        src_id = f"asset-{event.asset_id}"
        evt_id = f"event-{event.id}"

        # Add a small event node
        if evt_id not in added_nodes:
            elements.append({
                "data": {
                    "id": evt_id,
                    "label": event.event_type,
                    "type": "EVENT",
                    "severity": event.severity,
                }
            })
            added_nodes.add(evt_id)

        elements.append({
            "data": {
                "id": f"edge-{event.id}",
                "source": src_id,
                "target": evt_id,
                "severity": event.severity,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            }
        })

    return JsonResponse(elements, safe=False)
