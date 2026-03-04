from django.urls import path
from . import views

app_name = 'system_support'
urlpatterns = [
    # 登录/登出
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # 系统首页
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # 数据备份（仅管理员）
    path('backup/', views.backup_list, name='backup_list'),
    path('backup/create/', views.create_backup, name='create_backup'),
    
    # 系统日志（仅管理员）
    path('logs/', views.system_logs, name='system_logs'),
    
    # 区域特征管理（仅管理员）
    path('region/feature/list/', views.region_feature_list, name='region_feature_list'),
    path('region/feature/form/<int:pk>/', views.region_feature_form, name='region_feature_form'),
    path('region/feature/form/', views.region_feature_form, name='region_feature_form'),
    path('region/feature/delete/<int:pk>/', views.region_feature_delete, name='region_feature_delete'),
    
    # 多源数据联动查询
    path('data/linkage/', views.data_linkage_query, name='data_linkage_query'),

]
