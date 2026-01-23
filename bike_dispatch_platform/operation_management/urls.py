from django.urls import path
from . import views

app_name = 'operation_management'
urlpatterns = [
    # 首页
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # 车辆监控
    path('vehicles/', views.vehicle_monitor, name='vehicle_monitor'),
    path('vehicles/create/', views.vehicle_create, name='vehicle_create'),
    
    # 供需热力图
    path('heatmap/', views.supply_demand_heatmap, name='heatmap'),
    
    # 调度任务
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<str:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<str:task_id>/update-status/', views.task_update_status, name='task_update_status'),
    path('tasks/<str:task_id>/evaluation/', views.schedule_evaluation, name='schedule_evaluation'),
    
    # 运维轨迹
    path('track/', views.operator_track, name='operator_track'),
]
