"""
bike_sharing URL Configuration
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('bike_dispatch_platform.urls')),  # 包含主应用的路由
]
