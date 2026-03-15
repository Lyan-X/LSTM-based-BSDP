from django.urls import path
from . import views

app_name = 'data_process'

urlpatterns = [
    path('', views.data_manage_view, name='data_manage'),
    path('upload/', views.data_upload, name='data_upload'),
    path('weather/upload/', views.weather_data_upload, name='weather_upload'),
    path('list/', views.data_list, name='data_list'),
    path('export/ride/', views.export_ride_data, name='export_ride_data'),
    path('export/weather/', views.export_weather_data, name='export_weather_data'),
    path('api/stats/', views.data_stats_api, name='data_stats_api'),
]
