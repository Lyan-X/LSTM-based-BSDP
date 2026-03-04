from django.urls import path
from . import views

# 使用独立的app_name避免与demand_prediction.urls冲突
app_name = 'model_management'

urlpatterns = [
    # 模型与预测主页面路由
    path('predict/', views.model_predict_view, name='model_predict'),
    # 预测结果子页面路由
    path('predict/result/', views.predict_result_view, name='predict_result'),
    # 批量预测
    path('predict/batch/', views.batch_predict, name='batch_predict'),
    # 导出预测结果
    path('predict/export/', views.export_predictions, name='export_predictions'),
    # 停车点级短期预测（30min/1hr）
    path('predict/spot/', views.spot_forecast, name='spot_forecast'),
    # 停车点预测API（供热力图使用）
    path('api/spot-forecast/', views.spot_forecast_api, name='spot_forecast_api'),
    # 手动触发训练
    path('train/manual/', views.manual_train, name='manual_train'),
    # 模型下载
    path('download/<str:model_type>/', views.download_model, name='download_model'),
    # 损失曲线图片
    path('loss-curve/<str:model_type>/', views.loss_curve_image, name='loss_curve_image'),
]