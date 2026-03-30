from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SecurityEventViewSet, HunterDispatchLogViewSet, triage_view

router = DefaultRouter()
router.register(r'events', SecurityEventViewSet, basename='events')
router.register(r'dispatch', HunterDispatchLogViewSet, basename='dispatch')

urlpatterns = [
    path('api/', include(router.urls)),
    path('triage/', triage_view, name='triage'),
]
