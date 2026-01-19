from django.urls import path
from . import views

app_name = 'data_process'  # 命名空间，避免路由冲突
urlpatterns = [
    # 对应数据上传视图，路径是/data/upload/
    path('upload/', views.data_upload, name='data_upload'),
    # 数据列表页面，路径是/data/list/
    path('list/', views.data_list, name='data_list'),
]