from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count

from kismet.models import SecurityEvent, HunterDispatchLog
from .serializers import SecurityEventSerializer, HunterDispatchLogSerializer


class StandardPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


class SecurityEventViewSet(viewsets.ModelViewSet):
    queryset = SecurityEvent.objects.select_related('asset').all()
    serializer_class = SecurityEventSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'severity', 'status']

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        by_severity = list(
            SecurityEvent.objects.values('severity')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        by_type = list(
            SecurityEvent.objects.values('event_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        recent = list(
            SecurityEvent.objects.order_by('-timestamp')[:5]
            .values('timestamp', 'event_type', 'severity', 'asset__mac_address')
        )
        return Response({
            'by_severity': by_severity,
            'by_type': by_type,
            'recent': recent,
        })

    @action(detail=False, methods=['get'], url_path='queue')
    def queue(self, request):
        """Return all events ordered by severity then timestamp."""
        SEVERITY_ORDER = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        events = SecurityEvent.objects.select_related('asset').order_by('-timestamp')
        data = SecurityEventSerializer(events, many=True).data
        data = sorted(data, key=lambda e: (SEVERITY_ORDER.get(e['severity'], 9), e['timestamp']))
        return Response(data)

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        event = self.get_object()
        event.status = 'ACKNOWLEDGED'
        event.analyst_notes = request.data.get('notes', event.analyst_notes)
        event.resolved_by = request.user.username
        event.save()
        return Response(SecurityEventSerializer(event).data)

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        event = self.get_object()
        event.status = 'RESOLVED'
        event.analyst_notes = request.data.get('notes', event.analyst_notes)
        event.resolved_at = timezone.now()
        event.resolved_by = request.user.username
        event.save()
        return Response(SecurityEventSerializer(event).data)

    @action(detail=True, methods=['post'], url_path='false-positive')
    def false_positive(self, request, pk=None):
        event = self.get_object()
        event.status = 'FALSE_POSITIVE'
        event.analyst_notes = request.data.get('notes', event.analyst_notes)
        event.resolved_at = timezone.now()
        event.resolved_by = request.user.username
        event.save()
        return Response(SecurityEventSerializer(event).data)

    @action(detail=True, methods=['post'], url_path='dispatch-hunter')
    def dispatch_hunter(self, request, pk=None):
        """Dispatch the Hunter Node to track this asset's channel."""
        event = self.get_object()
        asset = event.asset
        channel = asset.operating_channel
        if not channel:
            return Response({'error': 'Asset has no known channel.'}, status=400)
        log = HunterDispatchLog.objects.create(
            admin_id=request.user.username,
            target_asset=asset,
            locked_channel=channel,
            status='ACTIVE',
        )
        event.status = 'ACKNOWLEDGED'
        event.resolved_by = request.user.username
        event.save()
        return Response({
            'dispatch': HunterDispatchLogSerializer(log).data,
            'event': SecurityEventSerializer(event).data,
        })


class HunterDispatchLogViewSet(viewsets.ModelViewSet):
    queryset = HunterDispatchLog.objects.all()
    serializer_class = HunterDispatchLogSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'status']


@login_required
def triage_view(request):
    return render(request, 'triage/triage.html')
