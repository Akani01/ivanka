# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Real Estate AI
    path('api/ai/property/<uuid:property_id>/analyze/', views.ai_analyze_property, name='ai_analyze_property'),
    
    # Jobs AI
    path('api/ai/job/<uuid:job_id>/analyze/', views.ai_analyze_job, name='ai_analyze_job'),
    
    # Maintenance AI
    path('api/ai/maintenance/<uuid:maintenance_id>/analyze/', views.ai_analyze_maintenance, name='ai_analyze_maintenance'),
    path('api/ai/status/', views.ai_status, name='ai_status'),
    # General AI
    path('api/ai/chat/', views.ai_chat, name='ai_chat'),
    path('api/ai/search/', views.ai_smart_search, name='ai_smart_search'),
]