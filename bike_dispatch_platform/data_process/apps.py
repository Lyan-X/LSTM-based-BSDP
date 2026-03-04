from django.apps import AppConfig


class DataProcessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data_process'

    def ready(self):
        """应用启动时执行"""
        from data_process.scheduler import start_scheduler
        start_scheduler()
