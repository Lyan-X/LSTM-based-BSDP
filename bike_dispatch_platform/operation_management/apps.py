import os
import sys

from django.apps import AppConfig


class OperationManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bike_dispatch_platform.operation_management"

    def ready(self):
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

        if getattr(OperationManagementConfig, "_scheduler_started", False):
            return
        OperationManagementConfig._scheduler_started = True

        try:
            self._seed_parking_spots()
        except Exception:
            pass

        # The realtime dashboard/heatmap now refresh on-demand through API polling.
        # Keep APScheduler opt-in so SQLite does not receive a second background write
        # stream while pages and verification scripts are building snapshots.
        if os.environ.get("BSDP_ENABLE_RUNTIME_SCHEDULER") != "1":
            return

        try:
            from bike_dispatch_platform.operation_management.scheduler import start_scheduler

            start_scheduler()
        except Exception as exc:
            import logging

            logging.getLogger("scheduler").error(
                "Failed to start APScheduler: %s", exc, exc_info=True
            )

    @staticmethod
    def _seed_parking_spots():
        from bike_dispatch_platform.operation_management.services.station_service import sync_parking_spots

        sync_parking_spots()
