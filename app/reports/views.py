"""
Reports & Compliance Export views.

Endpoints
─────────
GET  /reports/                    → UI page
GET  /reports/api/summary/        → JSON summary for the UI
GET  /reports/export/executive/   → PDF executive summary (date range via ?days=N)
GET  /reports/export/incident/<id>/ → PDF incident chain-of-custody
GET  /reports/export/csv/assets/  → CSV of all assets
GET  /reports/export/csv/events/  → CSV of security events (optional ?days=N)
"""

import csv
import io
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone

from kismet.models import Asset, HunterDispatchLog, SecurityEvent

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


# ── UI page ───────────────────────────────────────────────────────────────────

@login_required
def reports_view(request):
    return render(request, 'reports/reports.html')


# ── JSON summary for the page ─────────────────────────────────────────────────

@login_required
def api_summary(request):
    days = int(request.GET.get('days', 7))
    since = timezone.now() - timedelta(days=days)

    events_qs = SecurityEvent.objects.filter(timestamp__gte=since)

    total_assets  = Asset.objects.count()
    whitelisted   = Asset.objects.filter(is_whitelisted=True).count()
    rogue_aps     = Asset.objects.filter(asset_type='AP', is_whitelisted=False).count()

    open_events   = SecurityEvent.objects.filter(status='OPEN').count()
    resolved      = events_qs.filter(status='RESOLVED').count()
    critical      = events_qs.filter(severity='CRITICAL').count()
    dispatches    = HunterDispatchLog.objects.filter(timestamp__gte=since).count()

    by_severity = list(
        events_qs.values('severity').annotate(count=Count('id')).order_by('-count')
    )
    by_type = list(
        events_qs.values('event_type').annotate(count=Count('id')).order_by('-count')[:8]
    )

    return JsonResponse({
        'period_days':   days,
        'total_assets':  total_assets,
        'whitelisted':   whitelisted,
        'rogue_aps':     rogue_aps,
        'open_events':   open_events,
        'resolved':      resolved,
        'critical':      critical,
        'dispatches':    dispatches,
        'by_severity':   by_severity,
        'by_type':       by_type,
        'generated_at':  timezone.now().isoformat(),
    })


# ── PDF helpers ───────────────────────────────────────────────────────────────

def _render_pdf(html_string, filename):
    """Convert an HTML string to a PDF HttpResponse using WeasyPrint."""
    pdf_file = weasyprint.HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── Executive Summary PDF ─────────────────────────────────────────────────────

@login_required
def export_executive_pdf(request):
    if not WEASYPRINT_AVAILABLE:
        return HttpResponse('WeasyPrint is not installed.', status=501)

    days = int(request.GET.get('days', 7))
    since = timezone.now() - timedelta(days=days)

    events_qs = SecurityEvent.objects.filter(timestamp__gte=since)
    dispatches = HunterDispatchLog.objects.filter(timestamp__gte=since).select_related('target_asset')

    context = {
        'period_days':  days,
        'since':        since,
        'generated_at': timezone.now(),
        'generated_by': request.user.username,

        # Totals
        'total_assets': Asset.objects.count(),
        'whitelisted':  Asset.objects.filter(is_whitelisted=True).count(),
        'rogue_aps':    Asset.objects.filter(asset_type='AP', is_whitelisted=False).count(),
        'open_events':  SecurityEvent.objects.filter(status='OPEN').count(),
        'resolved':     events_qs.filter(status='RESOLVED').count(),
        'critical':     events_qs.filter(severity='CRITICAL').count(),
        'dispatches':   dispatches.count(),

        # Tables
        'by_severity':  list(events_qs.values('severity').annotate(count=Count('id')).order_by('-count')),
        'by_type':      list(events_qs.values('event_type').annotate(count=Count('id')).order_by('-count')[:10]),
        'recent_events':events_qs.select_related('asset').order_by('-timestamp')[:20],
        'dispatch_log': dispatches.order_by('-timestamp'),
    }

    html = render_to_string('reports/pdf_executive.html', context, request=request)
    filename = f"executive_summary_{timezone.now().strftime('%Y%m%d')}.pdf"
    return _render_pdf(html, filename)


# ── Incident Chain-of-Custody PDF ─────────────────────────────────────────────

@login_required
def export_incident_pdf(request, event_id):
    if not WEASYPRINT_AVAILABLE:
        return HttpResponse('WeasyPrint is not installed.', status=501)

    event   = get_object_or_404(SecurityEvent.objects.select_related('asset'), pk=event_id)
    asset   = event.asset
    history = SecurityEvent.objects.filter(asset=asset).order_by('timestamp')
    dispatches = HunterDispatchLog.objects.filter(target_asset=asset).order_by('timestamp')

    context = {
        'event':      event,
        'asset':      asset,
        'history':    history,
        'dispatches': dispatches,
        'generated_at': timezone.now(),
        'generated_by': request.user.username,
    }

    html = render_to_string('reports/pdf_incident.html', context, request=request)
    filename = f"incident_{event_id}_chain_of_custody_{timezone.now().strftime('%Y%m%d')}.pdf"
    return _render_pdf(html, filename)


# ── CSV: Assets ───────────────────────────────────────────────────────────────

@login_required
def export_assets_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="assets_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'MAC Address', 'Vendor/OUI', 'Asset Type', 'SSID/Alias',
        'Channel', 'RSSI (dBm)', 'Radius (m)', 'Whitelisted',
        'Encrypted', 'First Seen', 'Last Seen',
    ])

    for a in Asset.objects.all().order_by('-last_seen'):
        writer.writerow([
            a.id, a.mac_address, a.vendor_oui or '', a.asset_type,
            a.ssid_alias or '', a.operating_channel or '',
            a.smoothed_rssi or '', a.estimated_radius_meters or '',
            'Yes' if a.is_whitelisted else 'No',
            'Yes' if a.is_encrypted else 'No',
            a.first_seen.strftime('%Y-%m-%d %H:%M:%S') if a.first_seen else '',
            a.last_seen.strftime('%Y-%m-%d %H:%M:%S') if a.last_seen else '',
        ])

    return response


# ── CSV: Security Events ──────────────────────────────────────────────────────

@login_required
def export_events_csv(request):
    days = request.GET.get('days', '')
    qs = SecurityEvent.objects.select_related('asset').order_by('-timestamp')
    if days:
        try:
            since = timezone.now() - timedelta(days=int(days))
            qs = qs.filter(timestamp__gte=since)
        except ValueError:
            pass

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="events_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Timestamp', 'Event Type', 'Severity', 'Status',
        'MAC Address', 'Vendor', 'Asset Type', 'Channel',
        'RSSI (dBm)', 'Description', 'Analyst Notes',
        'Resolved By', 'Resolved At',
    ])

    for e in qs:
        writer.writerow([
            e.id,
            e.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            e.event_type, e.severity, e.status,
            e.asset.mac_address, e.asset.vendor_oui or '',
            e.asset.asset_type, e.asset.operating_channel or '',
            e.asset.smoothed_rssi or '',
            (e.description or '').replace('\n', ' '),
            (e.analyst_notes or '').replace('\n', ' '),
            e.resolved_by or '',
            e.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if e.resolved_at else '',
        ])

    return response
