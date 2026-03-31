from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from kismet.models import Asset
from .serializers import AssetMgrSerializer

class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

class AssetMgrViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Asset.objects.all().order_by('-last_seen')
    serializer_class = AssetMgrSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['mac_address', 'vendor_oui', 'ssid_alias', 'asset_type']
    ordering_fields = ['last_seen', 'first_seen', 'smoothed_rssi']

    def get_queryset(self):
        qs = super().get_queryset()
        vendor   = self.request.query_params.get('vendor_oui', '').strip()
        orphaned = self.request.query_params.get('orphaned', '')
        wl       = self.request.query_params.get('whitelisted', '')
        if vendor:
            qs = qs.filter(vendor_oui__icontains=vendor)
        if orphaned.lower() in ['1', 'true', 'yes']:
            cutoff = timezone.now() - timezone.timedelta(hours=24)
            qs = qs.filter(first_seen__lte=cutoff, is_whitelisted=False)
        if wl.lower() in ['0', 'false', 'no']:
            qs = qs.filter(is_whitelisted=False)
        elif wl.lower() in ['1', 'true', 'yes']:
            qs = qs.filter(is_whitelisted=True)
        return qs

    @action(detail=False, methods=['post'], url_path='bulk-whitelist')
    def bulk_whitelist(self, request):
        """Bulk mark assets as whitelisted by vendor_oui or list of ids."""
        vendor = request.data.get('vendor_oui')
        ids = request.data.get('ids')
        updated = 0
        if vendor:
            updated = Asset.objects.filter(vendor_oui__iexact=vendor).update(is_whitelisted=True)
        elif isinstance(ids, list):
            updated = Asset.objects.filter(id__in=ids).update(is_whitelisted=True)
        else:
            return Response({'error': 'Provide vendor_oui or ids list'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'updated': updated})

    @action(detail=True, methods=['post'], url_path='tag')
    def tag(self, request, pk=None):
        """Tag an asset with ssid_alias or update whitelist state."""
        asset = self.get_object()
        ssid = request.data.get('ssid_alias')
        whitelist = request.data.get('is_whitelisted')
        changed = False
        if ssid is not None:
            asset.ssid_alias = ssid
            changed = True
        if whitelist is not None:
            asset.is_whitelisted = bool(whitelist)
            changed = True
        if changed:
            asset.save()
        return Response(AssetMgrSerializer(asset).data)


@login_required
def whitelist_view(request):
    return render(request, 'assetmgr/whitelist.html')
