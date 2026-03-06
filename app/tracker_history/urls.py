from django.urls import path
from .views import history_view, history_wifi_data

urlpatterns = [
    path('', history_view, name='tracker_history'),
    path('wifi-data/', history_wifi_data, name='history_wifi_data'),
]