# demand_prediction/urls.py 空配置（后续补全业务路由）
from django.urls import path
from . import views

app_name = 'demand_prediction'
urlpatterns = [
    # 后续添加预测相关路由，如 path('predict/', views.predict_view, name='predict'),
]