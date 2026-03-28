from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Avg, Count

from .models import Asset, SecurityEvent, HunterDispatchLog
from .serializers import (
    AssetSerializer, SecurityEventSerializer, HunterDispatchLogSerializer
)


class StandardPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['mac_address', 'ssid_alias', 'vendor_oui']
    ordering_fields = ['last_seen', 'first_seen', 'smoothed_rssi', 'estimated_radius_meters']

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        qs = Asset.objects.all()
        return Response({
            'total_assets': qs.count(),
            'access_points': qs.filter(asset_type='AP').count(),
            'clients': qs.filter(asset_type='CLIENT').count(),
            'unknown': qs.filter(asset_type='UNKNOWN').count(),
            'whitelisted': qs.filter(is_whitelisted=True).count(),
            'avg_signal': round(qs.aggregate(avg=Avg('smoothed_rssi'))['avg'] or 0, 2),
        })

    @action(detail=False, methods=['get'], url_path='by-type')
    def by_type(self, request):
        data = list(
            Asset.objects.values('asset_type')
            .annotate(count=Count('id'))
            .order_by('asset_type')
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='channel-usage')
    def channel_usage(self, request):
        data = list(
            Asset.objects.exclude(operating_channel__isnull=True)
            .values('operating_channel')
            .annotate(count=Count('id'))
            .order_by('operating_channel')
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='vendor-distribution')
    def vendor_distribution(self, request):
        data = list(
            Asset.objects.exclude(vendor_oui__isnull=True)
            .exclude(vendor_oui='')
            .values('vendor_oui')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='encryption-breakdown')
    def encryption_breakdown(self, request):
        encrypted = Asset.objects.filter(is_encrypted=True).count()
        unencrypted = Asset.objects.filter(is_encrypted=False).count()
        return Response({'encrypted': encrypted, 'unencrypted': unencrypted})

    @action(detail=False, methods=['get'], url_path='signal-distribution')
    def signal_distribution(self, request):
        histogram = {}
        for val in Asset.objects.exclude(smoothed_rssi__isnull=True).values_list('smoothed_rssi', flat=True):
            bucket = 5 * (val // 5)
            histogram[bucket] = histogram.get(bucket, 0) + 1
        data = [{'bin': k, 'count': v} for k, v in sorted(histogram.items())]
        return Response(data)


class SecurityEventViewSet(viewsets.ModelViewSet):
    queryset = SecurityEvent.objects.all()
    serializer_class = SecurityEventSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'severity']

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


class HunterDispatchLogViewSet(viewsets.ModelViewSet):
    queryset = HunterDispatchLog.objects.all()
    serializer_class = HunterDispatchLogSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'status']
