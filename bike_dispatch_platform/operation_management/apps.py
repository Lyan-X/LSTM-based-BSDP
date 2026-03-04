import os
from django.apps import AppConfig


class OperationManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'operation_management'

    def ready(self):
        # Guard 1: skip during manage.py commands that don't need the scheduler
        #          (makemigrations, migrate, collectstatic, shell, test …)
        import sys
        skip_commands = {'makemigrations', 'migrate', 'collectstatic', 'shell',
                         'test', 'check', 'inspectdb', 'dbshell', 'createsuperuser'}
        if len(sys.argv) > 1 and sys.argv[1] in skip_commands:
            return

        # Guard 2: with Django's auto-reloader (runserver), ready() is called
        #          twice — once in the parent watcher, once in the child server.
        #          Only start the scheduler in the actual server process.
        #          RUN_MAIN='true'  → child (actual server)
        #          RUN_MAIN not set → production / --noreload mode
        run_main = os.environ.get('RUN_MAIN')
        if run_main is not None and run_main != 'true':
            return  # parent watcher process — skip

        # Guard 3: prevent double-start if ready() is somehow called twice
        if getattr(OperationManagementConfig, '_scheduler_started', False):
            return
        OperationManagementConfig._scheduler_started = True

        # Seed parking spots on first launch so the scheduler has spots to work with
        try:
            self._seed_parking_spots()
        except Exception:
            pass  # non-fatal; spots may already exist

        # Start the background scheduler
        try:
            from operation_management.scheduler import start_scheduler
            start_scheduler()
        except Exception as exc:
            import logging
            logging.getLogger('scheduler').error(
                'Failed to start APScheduler: %s', exc, exc_info=True
            )

    @staticmethod
    def _seed_parking_spots():
        """Ensure all 62 YSU parking spots are present in the DB."""
        from operation_management.models import ParkingSpot
        if ParkingSpot.objects.count() >= 62:
            return
        import sys, os
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if root not in sys.path:
            sys.path.insert(0, root)
        from config import PARKING_SPOTS
        for name, (lon, lat) in PARKING_SPOTS.items():
            ParkingSpot.objects.get_or_create(
                spot_name=name,
                defaults={'longitude': lon, 'latitude': lat, 'service_radius': 100},
            )
