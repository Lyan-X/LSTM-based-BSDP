from django.urls import path

from . import views

app_name = "system_support"

urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("api/dashboard/", views.dashboard_api, name="dashboard_api"),
    path("settings/", views.settings_view, name="settings"),
    path("backups/", views.backup_list, name="backup_list"),
    path("backups/create/", views.create_backup, name="create_backup"),
    path("logs/", views.system_logs, name="system_logs"),
]
