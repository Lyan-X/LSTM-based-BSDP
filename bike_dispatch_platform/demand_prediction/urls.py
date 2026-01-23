from django.urls import path
from . import views

app_name = 'demand_prediction'
urlpatterns = [
    path('predict/', views.demand_predict, name='predict'),
    path('list/', views.prediction_list, name='prediction_list'),
    path('compare/', views.model_compare, name='model_compare'),
]
