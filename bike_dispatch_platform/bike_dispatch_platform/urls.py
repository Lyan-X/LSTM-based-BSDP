from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView  # 新增：导入重定向视图
from django.contrib.auth import views as auth_views

urlpatterns = [
    # 新增：根路径（/）重定向到数据上传页面
    path('', RedirectView.as_view(url='/data/upload/'), name='home'),
    
    path('admin/', admin.site.urls),
    path('data/', include('data_process.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/data/upload/'), name='logout'),
]