from django.urls import path
from . import views

app_name = 'system_support'
urlpatterns = [
    # 登录/登出
    path('login/', views.custom_login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # 系统首页
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # 数据备份（仅管理员）
    path('backup/', views.backup_list, name='backup_list'),
    path('backup/create/', views.data_backup, name='backup_create'),
    path('backup/<int:backup_id>/download/', views.download_backup, name='backup_download'),
    
    # 系统日志（仅管理员）
    path('logs/', views.system_logs, name='system_logs'),
    
    # 报表导出
    path('report/export/', views.report_export, name='report_export'),
    
    # 区域特征管理（仅管理员）
    path('region/feature/list/', views.region_feature_list, name='region_feature_list'),
    path('region/feature/create/', views.region_feature_create, name='region_feature_create'),
    path('region/feature/edit/<int:feature_id>/', views.region_feature_edit, name='region_feature_edit'),
    path('region/feature/delete/<int:feature_id>/', views.region_feature_delete, name='region_feature_delete'),
    
    # 多源数据联动查询
    path('data/linkage/', views.data_linkage_query, name='data_linkage_query'),
]
