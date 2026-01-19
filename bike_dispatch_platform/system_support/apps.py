from django.apps import AppConfig

class SystemSupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'system_support'  # 必须与应用目录名、INSTALLED_APPS中的名称完全一致