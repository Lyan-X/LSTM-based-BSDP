import os
import sys

from django.apps import AppConfig


class DataProcessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bike_dispatch_platform.data_process"

    def ready(self):
        """Start the legacy compatibility scheduler only when explicitly enabled."""

        skip_commands = {
            "makemigrations",
            "migrate",
            "collectstatic",
            "shell",
            "test",
            "check",
            "inspectdb",
            "dbshell",
            "createsuperuser",
        }
        if len(sys.argv) > 1 and sys.argv[1] in skip_commands:
            return

        run_main = os.environ.get("RUN_MAIN")
        if run_main is not None and run_main != "true":
            return

        # The main realtime scheduler is owned by operation_management.
        # Keeping this compatibility scheduler opt-in avoids duplicate APScheduler
        # workers repeatedly writing the same SQLite runtime tables.
        if os.environ.get("BSDP_ENABLE_COMPAT_SCHEDULER") != "1":
            return

        if getattr(DataProcessConfig, "_scheduler_started", False):
            return
        DataProcessConfig._scheduler_started = True

        from bike_dispatch_platform.data_process.scheduler import start_scheduler

        start_scheduler()
