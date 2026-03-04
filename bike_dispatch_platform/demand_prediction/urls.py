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
    # 新增模型下载和损失曲线展示API路由
    path('loss-curve/<str:model_type>/<str:date>/', views.get_loss_curve, name='get_loss_curve'),
    path('download/<str:model_type>/', views.download_model, name='download_model'),
]
