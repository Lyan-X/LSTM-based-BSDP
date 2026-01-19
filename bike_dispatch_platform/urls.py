from django.contrib import admin
from django.urls import path, include  # 确保导入了include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # 必须添加这一行：关联数据处理模块的路由
    path('data/', include('data_process.urls')),
    # 其他模块路由（按需保留）
    path('prediction/', include('demand_prediction.urls')),
    path('operation/', include('operation_management.urls')),
    path('system/', include('system_support.urls')),
    path('', RedirectView.as_view(url='/operation/dashboard/')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)