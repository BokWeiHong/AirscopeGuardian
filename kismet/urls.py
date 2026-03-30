from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, SystemMessageViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet, basename='assets')
router.register(r'messages', SystemMessageViewSet, basename='messages')

urlpatterns = [
    path('api/', include(router.urls)),
]
