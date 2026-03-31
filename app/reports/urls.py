from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # UI
    path('', views.reports_view, name='index'),

    # JSON summary
    path('api/summary/', views.api_summary, name='api_summary'),

    # PDF exports
    path('export/executive/', views.export_executive_pdf, name='export_executive'),
    path('export/incident/<int:event_id>/', views.export_incident_pdf, name='export_incident'),

    # CSV exports
    path('export/csv/assets/', views.export_assets_csv, name='export_csv_assets'),
    path('export/csv/events/', views.export_events_csv, name='export_csv_events'),
]
