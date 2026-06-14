from __future__ import annotations

from typing import Dict, Iterable

from django.db import transaction

from bike_dispatch_platform.operation_management.models import ParkingSpot
from station_info.master_data import DEFAULT_REFRESH_SECONDS, load_station_master_data
from bike_dispatch_platform.system_support.models import SystemSetting


IMMUTABLE_STATION_FIELDS = (
    "ysu_id",
    "spot_name",
    "longitude",
    "latitude",
    "max_capacity",
    "washington_station_id",
    "washington_station_name",
    "initial_inventory",
    "campus_area",
    "spot_type",
)


def _detect_campus_area(longitude: float) -> str:
    return "west" if longitude < 119.533 else "east"


def _station_core_defaults(record) -> Dict[str, object]:
    return {
        "ysu_id": record.ysu_id,
        "spot_name": record.station_name,
        "longitude": record.longitude,
        "latitude": record.latitude,
        "max_capacity": record.max_capacity,
        "washington_station_id": record.washington_station_id,
        "washington_station_name": record.washington_station_name,
        "initial_inventory": record.initial_inventory,
        "campus_area": _detect_campus_area(record.longitude),
        "spot_type": record.station_type,
    }


def _station_editable_defaults(record) -> Dict[str, object]:
    return {
        "low_warning_threshold": record.low_warning_threshold,
        "high_warning_threshold": record.high_warning_threshold,
        "notes": record.notes,
        "is_active": record.is_active,
    }


def _requires_registry_rebuild(existing_stations: Iterable[ParkingSpot]) -> bool:
    existing_stations = list(existing_stations)
    if len(existing_stations) != 62:
        return True

    ysu_ids = [station.ysu_id for station in existing_stations]
    if sorted(ysu_ids) != list(range(1, 63)):
        return True

    if len(set(ysu_ids)) != len(existing_stations):
        return True

    names = [station.spot_name for station in existing_stations]
    return len(set(names)) != len(existing_stations)


def _rebuild_station_registry() -> Dict[int, ParkingSpot]:
    station_map: Dict[int, ParkingSpot] = {}
    with transaction.atomic():
        from bike_dispatch_platform.data_process.models import DataProcessLog, ParkingSpotRealTime, ParkingSpotSnapshot
        from bike_dispatch_platform.demand_prediction.models import StationPrediction
        from bike_dispatch_platform.operation_management.models import ScheduleTask, Vehicle

        StationPrediction.objects.all().delete()
        ParkingSpotRealTime.objects.all().delete()
        ParkingSpotSnapshot.objects.all().delete()
        DataProcessLog.objects.all().delete()
        ScheduleTask.objects.all().delete()
        Vehicle.objects.all().delete()
        ParkingSpot.objects.all().delete()

        create_batch = []
        for record in load_station_master_data():
            payload = {
                **_station_core_defaults(record),
                **_station_editable_defaults(record),
            }
            create_batch.append(ParkingSpot(**payload))
        ParkingSpot.objects.bulk_create(create_batch, batch_size=62)

    for station in ParkingSpot.objects.order_by("ysu_id"):
        station_map[station.ysu_id] = station
    return station_map


def sync_parking_spots() -> Dict[int, ParkingSpot]:
    """Synchronize immutable 62-station master data without overwriting editable fields."""

    existing_stations = list(ParkingSpot.objects.order_by("ysu_id"))
    if _requires_registry_rebuild(existing_stations):
        return _rebuild_station_registry()

    station_map: Dict[int, ParkingSpot] = {}
    existing_by_ysu = {station.ysu_id: station for station in existing_stations}

    for record in load_station_master_data():
        station = existing_by_ysu.get(record.ysu_id)
        if station is None:
            station = ParkingSpot.objects.create(
                **_station_core_defaults(record),
                **_station_editable_defaults(record),
            )
            station_map[record.ysu_id] = station
            continue

        update_fields = []
        for field_name, value in _station_core_defaults(record).items():
            if getattr(station, field_name) != value:
                setattr(station, field_name, value)
                update_fields.append(field_name)

        # Editable fields such as warning thresholds, notes and enabled status are
        # intentionally preserved so runtime settings and运维 edits remain effective.
        if update_fields:
            station.save(update_fields=update_fields)

        station_map[record.ysu_id] = station

    return station_map


def get_runtime_settings() -> SystemSetting:
    """Return the singleton runtime settings row."""

    settings_obj, created = SystemSetting.objects.get_or_create(
        pk=1,
        defaults={"dashboard_refresh_seconds": DEFAULT_REFRESH_SECONDS},
    )
    if created and settings_obj.dashboard_refresh_seconds != DEFAULT_REFRESH_SECONDS:
        settings_obj.dashboard_refresh_seconds = DEFAULT_REFRESH_SECONDS
        settings_obj.save(update_fields=["dashboard_refresh_seconds", "updated_at"])
    return settings_obj
