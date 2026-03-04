from django.urls import path
from . import views

app_name = 'operation_management'

urlpatterns = [
    # 运维管理首页
    path('', views.operation_dashboard, name='operation_dashboard'),
    
    # 供需热力图
    path('heatmap/', views.supply_demand_heatmap, name='supply_demand_heatmap'),
    
    # 车辆监控
    path('vehicles/', views.vehicle_monitor, name='vehicle_monitor'),
    
    # 调度任务
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/auto-generate/', views.auto_generate_tasks, name='auto_generate_tasks'),
    
    # 调度效果评估
    path('evaluation/', views.dispatch_evaluation, name='dispatch_evaluation'),
    
    # 运维人员轨迹追踪
    path('operator-track/', views.operator_track, name='operator_track'),
    
    # 生成测试数据
    path('generate-test-data/', views.generate_test_data, name='generate_test_data'),
    
    # API接口：实时数据
    path('api/vehicle-data/', views.get_realtime_vehicle_data, name='get_realtime_vehicle_data'),
    path('api/parking-data/', views.get_realtime_parking_data, name='get_realtime_parking_data'),
    path('api/task-data/', views.get_realtime_task_data, name='get_realtime_task_data'),
    
    # API接口：更新状态
    path('api/update-vehicle-status/', views.update_vehicle_status, name='update_vehicle_status'),
    path('api/update-task-status/', views.update_task_status, name='update_task_status'),

    # APScheduler 状态 API（供页面轮询使用）
    path('api/scheduler-status/', views.scheduler_status_api, name='scheduler_status'),
]