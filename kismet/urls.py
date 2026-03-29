from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, SecurityEventViewSet, HunterDispatchLogViewSet, SystemMessageViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet)
router.register(r'events', SecurityEventViewSet)
router.register(r'dispatch', HunterDispatchLogViewSet)
router.register(r'messages', SystemMessageViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
