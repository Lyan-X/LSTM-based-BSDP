"""
自行车调度平台 URL 配置
"""

from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/system/dashboard/', permanent=False), name='home'),
    path('system/', include('bike_dispatch_platform.system_support.urls')),
    path('predict/', include('bike_dispatch_platform.demand_prediction.urls')),
    path('operation/', include('bike_dispatch_platform.operation_management.urls')),
    path('dashboard/', RedirectView.as_view(url='/system/dashboard/', permanent=False), name='dashboard_alias'),
    path('login/', RedirectView.as_view(url='/system/login/', permanent=False), name='login_alias'),
    path('logout/', RedirectView.as_view(url='/system/logout/', permanent=False), name='logout_alias'),
    path('api/dashboard/', RedirectView.as_view(url='/system/api/dashboard/', permanent=False), name='dashboard_api_alias'),
    path('demand/', RedirectView.as_view(url='/predict/', permanent=False), name='predict_alias'),
]
