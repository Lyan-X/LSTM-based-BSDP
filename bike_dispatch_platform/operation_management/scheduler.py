"""APScheduler integration for the deterministic runtime pipeline."""

from __future__ import annotations

import logging

from django.utils import timezone

from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service

logger = logging.getLogger("scheduler")

_scheduler = None
SCHEDULER_INTERVAL_MINUTES = 1


def generate_real_time_data() -> None:
    """Refresh one runtime snapshot from the station-level 48-hour prediction batch."""

    snapshot = runtime_service.ensure_snapshot(now=timezone.now())
    created_tasks = runtime_service.create_schedule_tasks(snapshot)
    logger.info(
        "Realtime snapshot refreshed at %s with %s stations, %s dispatch suggestions and %s created tasks",
        snapshot.bucket_time.isoformat(),
        len(snapshot.station_rows),
        len(snapshot.dispatch_suggestions),
        len(created_tasks),
    )


def start_scheduler() -> None:
    """Start the APScheduler BackgroundScheduler."""

    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running, skip duplicate start")
        return

    _scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={"misfire_grace_time": 60, "coalesce": True},
    )
    _scheduler.add_job(
        generate_real_time_data,
        trigger=IntervalTrigger(minutes=SCHEDULER_INTERVAL_MINUTES),
        id="realtime_data_job",
        name="Deterministic runtime snapshot refresh",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Realtime scheduler started with %s-minute interval", SCHEDULER_INTERVAL_MINUTES)


def stop_scheduler() -> None:
    """Stop the APScheduler BackgroundScheduler."""

    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Realtime scheduler stopped")
