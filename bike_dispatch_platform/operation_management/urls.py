from django.urls import path

from . import views

app_name = "operation_management"

urlpatterns = [
    path("", views.supply_demand_heatmap, name="dispatch_dashboard"),
    path("heatmap/", views.supply_demand_heatmap, name="heatmap"),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/export/", views.task_export, name="task_export"),
    path("tasks/<int:task_id>/", views.task_detail, name="task_detail"),
    path("tasks/auto-generate/", views.auto_generate_tasks, name="auto_generate_tasks"),
    path("tasks/manual-create/", views.manual_dispatch_create, name="manual_dispatch_create"),
    path("stations/", views.station_list, name="station_list"),
    path("stations/<int:station_id>/edit/", views.station_edit, name="station_edit"),
    path("stations/<int:station_id>/history/export/", views.station_history_export, name="station_history_export"),
    path("stations/<int:station_id>/work-order/", views.create_work_order, name="create_work_order"),
    path("vehicles/", views.vehicle_management, name="vehicle_management"),
    path("vehicles/<str:vehicle_id>/", views.vehicle_detail, name="vehicle_detail"),
    path("api/parking-data/", views.get_realtime_parking_data, name="get_realtime_parking_data"),
    path("api/station-runtime/", views.station_runtime_api, name="station_runtime_api"),
    path("api/vehicle-runtime/", views.vehicle_runtime_api, name="vehicle_runtime_api"),
    path("api/task-data/", views.get_realtime_task_data, name="get_realtime_task_data"),
    path("api/update-task-status/", views.update_task_status, name="update_task_status"),
]
