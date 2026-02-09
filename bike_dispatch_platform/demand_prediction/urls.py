from django.urls import path
from . import views

app_name = 'demand_prediction'
urlpatterns = [
    path('predict/', views.demand_predict, name='predict'),
    path('list/', views.prediction_list, name='prediction_list'),
    path('compare/', views.model_compare, name='model_compare'),
    # 新增模型与预测主页面路由
    path('manage/predict/', views.model_predict_view, name='model_predict'),
    # 新增预测结果子页面路由
    path('manage/predict/result/', views.predict_result_view, name='predict_result'),
]
