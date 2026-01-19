from django.contrib import admin
from django.urls import path, include
# 导入Django内置登录/登出视图
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('data/', include('data_process.urls')),
    # 核心：配置登录路由（解决/accounts/login/ 404）
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    # 可选：配置登出路由（登出后返回上传页面）
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/data/upload/'), name='logout'),
]