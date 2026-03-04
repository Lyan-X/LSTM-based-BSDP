from django.urls import path
from . import views

# 必须设置app_name，否则模板中{% url 'data_process:data_upload' %}会报错
app_name = 'data_process'

urlpatterns = [
    # 数据上传页面
    path('upload/', views.data_upload, name='data_upload'),
    # 数据列表页面
    path('list/', views.data_list, name='data_list'),
    # 天气数据上传路由
    path("weather/upload/", views.weather_data_upload, name="weather_upload"),
    # 数据管理页面路由（核心页面）
    path('manage/', views.data_manage_view, name='data_manage'),
    # 本地数据手动录入（任务书"本地数据录入"要求）
    path('entry/ride/', views.local_ride_entry, name='local_ride_entry'),
    path('entry/weather/', views.local_weather_entry, name='local_weather_entry'),
    # 数据导出（任务书"预测结果导出"要求）
    path('export/ride/', views.export_ride_data, name='export_ride_data'),
    path('export/weather/', views.export_weather_data, name='export_weather_data'),
    # 数据统计API
    path('api/stats/', views.data_stats_api, name='data_stats_api'),
    # 实时数据模拟状态API
    path('api/realtime-status/', views.realtime_data_status_api, name='realtime_data_status'),
]