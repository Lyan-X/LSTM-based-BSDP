from django.urls import path
from . import views

# 必须设置app_name，否则模板中{% url 'data_process:data_upload' %}会报错
app_name = 'data_process'

urlpatterns = [
    # 数据上传页面（别名要和视图中的redirect匹配）
    path('upload/', views.data_upload, name='data_upload'),
    # 数据列表页面
    path('list/', views.data_list, name='data_list'),
    # 新增天气数据上传路由（关键！）
    path("weather/upload/", views.weather_data_upload, name="weather_upload"),
]