"""Compatibility sync service backed by the deterministic runtime pipeline."""

from __future__ import annotations

import logging
from typing import Dict

from demand_prediction.services.station_prediction_service import station_prediction_service
from operation_management.models import Vehicle
from operation_management.services.runtime_service import runtime_service

logger = logging.getLogger(__name__)


class DataSyncService:
    """Route legacy sync calls to the real prediction and runtime services."""

    @staticmethod
    def sync_vehicle_data() -> bool:
        """Validate the current vehicle registry without injecting synthetic movement."""

        total_vehicles = Vehicle.objects.count()
        logger.info("Vehicle registry sync completed with %s tracked vehicles", total_vehicles)
        return True

    @staticmethod
    def sync_prediction_data() -> bool:
        """Refresh the 48-hour station prediction batch from the LSTM artifacts."""

        station_prediction_service.get_batch_response(force=True)
        logger.info("Prediction batch refreshed from station-level LSTM artifacts")
        return True

    @staticmethod
    def generate_schedule_tasks() -> int:
        """Generate dispatch tasks from the current runtime snapshot."""

        snapshot = runtime_service.ensure_snapshot()
        tasks = runtime_service.create_schedule_tasks(snapshot)
        logger.info("Generated %s dispatch tasks from deterministic runtime snapshot", len(tasks))
        return len(tasks)

    @staticmethod
    def run_sync_cycle() -> Dict[str, object]:
        """Run one deterministic closed-loop sync cycle."""

        vehicle_sync_success = DataSyncService.sync_vehicle_data()
        prediction_sync_success = DataSyncService.sync_prediction_data()
        tasks_created = DataSyncService.generate_schedule_tasks()
        return {
            "vehicle_sync": vehicle_sync_success,
            "prediction_sync": prediction_sync_success,
            "tasks_created": tasks_created,
        }
