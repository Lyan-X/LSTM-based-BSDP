from django.urls import path

from . import views

app_name = "demand_prediction"

urlpatterns = [
    path("", views.model_predict_view, name="model_predict"),
    path("compare/", views.model_compare, name="model_compare"),
    path("results/", views.predict_result_view, name="predict_result"),
    path("spot/", views.spot_forecast, name="spot_forecast"),
    path("spot/api/", views.spot_forecast_api, name="spot_forecast_api"),
    path("api/48h/", views.predict_48h_api, name="predict_48h_api"),
    path("api/compare/", views.compare_api, name="compare_api"),
    path("api/station/<int:station_id>/", views.predict_station_api, name="predict_station_api"),
    path("export/report/", views.export_prediction_report, name="export_prediction_report"),
    path("train/manual/", views.manual_train, name="manual_train"),
    path("download/<str:model_type>/", views.download_model, name="download_model"),
    path("loss-curve/<str:model_type>/<str:date>/", views.get_loss_curve, name="get_loss_curve"),
]
