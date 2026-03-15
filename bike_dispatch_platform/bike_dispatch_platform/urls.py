from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/system/dashboard/'), name='home'),
    path('accounts/login/', RedirectView.as_view(url='/system/login/')),
    path('admin/', admin.site.urls),
    path('data/', include('bike_dispatch_platform.data_process.urls')),
    path('predict/', include('bike_dispatch_platform.demand_prediction.urls')),
    path('operation/', include('bike_dispatch_platform.operation_management.urls')),
    path('system/', include('bike_dispatch_platform.system_support.urls')),
]
