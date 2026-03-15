"""Compatibility scheduler that delegates to the runtime service."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.utils import timezone

from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def generate_real_time_data() -> None:
    """Generate one deterministic runtime snapshot for all parking spots."""

    snapshot = runtime_service.ensure_snapshot(now=timezone.now())
    logger.info(
        "Generated deterministic runtime snapshot at %s for %s stations",
        snapshot.bucket_time.isoformat(),
        len(snapshot.station_rows),
    )


def start_scheduler() -> None:
    """Start the compatibility scheduler."""

    scheduler.remove_all_jobs()
    scheduler.add_job(
        generate_real_time_data,
        trigger=IntervalTrigger(minutes=1),
        id="generate_real_time_data",
        name="生成实时停车点数据",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
        logger.info("Data-process scheduler started")


def stop_scheduler() -> None:
    """Stop the compatibility scheduler."""

    if scheduler.running:
        scheduler.shutdown()
        logger.info("Data-process scheduler stopped")
