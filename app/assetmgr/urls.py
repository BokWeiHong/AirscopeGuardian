from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetMgrViewSet, whitelist_view

router = DefaultRouter()
router.register(r'assets', AssetMgrViewSet, basename='assetmgr-assets')

urlpatterns = [
    path('api/', include(router.urls)),
    path('whitelist/', whitelist_view, name='assetmgr-whitelist'),
]
