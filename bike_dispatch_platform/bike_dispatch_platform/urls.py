from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    # 根路径重定向到系统首页
    path('', RedirectView.as_view(url='/system/dashboard/'), name='home'),
    
    # 登录页面（覆盖默认的accounts/login）
    path('accounts/login/', RedirectView.as_view(url='/system/login/')),
    
    path('admin/', admin.site.urls),
    
    # 四大核心模块路由
    path('data/', include('data_process.urls')),
    path('predict/', include('demand_prediction.urls')),
    path('operation/', include('operation_management.urls')),
    path('system/', include('system_support.urls')),
    
    # 新增模型与预测管理路由
    path('model/', include('demand_prediction.model_urls')),
    


]