from django.urls import path
from . import views

# 必须设置app_name，否则模板中{% url 'demand_prediction:model_predict' %}会报错
app_name = 'demand_prediction'

urlpatterns = [
    # 模型与预测主页面路由
    path('predict/', views.model_predict_view, name='model_predict'),
    # 预测结果子页面路由
    path('predict/result/', views.predict_result_view, name='predict_result'),
]