from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone

from bike_dispatch_platform.operation_management.models import (
    ParkingSpot,
    ScheduleTask,
    Vehicle,
    VehicleLocationHistory,
)
from bike_dispatch_platform.operation_management.services.runtime_service import dispatch_priority, runtime_service
from bike_dispatch_platform.operation_management.services.station_service import sync_parking_spots
from station_info.master_data import TOTAL_SYSTEM_VEHICLES


ROOT_DIR = Path(__file__).resolve().parents[3]
RIDE_DATA_PATH = ROOT_DIR / "ysu_bike_data.csv"
NORMAL_STATUSES = {"available", "ridden", "locked"}


def normalize_vehicle_status(status: str) -> str:
    if status in {"available", "normal"}:
        return "normal"
    if status == "faulty":
        return "faulty"
    if status in {"in_transit", "dispatching"}:
        return "dispatching"
    if status == "locked":
        return "locked"
    return "unknown"


def vehicle_status_label(status: str) -> str:
    mapping = {
        "normal": "正常",
        "available": "正常",
        "faulty": "故障",
        "dispatching": "调度中",
        "in_transit": "调度中",
        "locked": "锁定",
        "unknown": "未知",
    }
    return mapping.get(status, "未知")


def _build_vehicle(vehicle_id: str, station: ParkingSpot, status: str = "available") -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        status=status,
        latitude=station.latitude,
        longitude=station.longitude,
        parking_spot=station,
    )


def _append_history(
    *,
    vehicle: Vehicle,
    previous_station: ParkingSpot | None,
    current_station: ParkingSpot | None,
    previous_status: str,
    current_status: str,
    reason: str,
) -> VehicleLocationHistory:
    return VehicleLocationHistory(
        vehicle=vehicle,
        previous_station=previous_station,
        current_station=current_station,
        previous_status=previous_status,
        current_status=current_status,
        change_reason=reason,
    )


def _reconcile_vehicle_locations(vehicles: List[Vehicle], target_rows: List[Dict[str, object]]) -> None:
    station_map = {station.ysu_id: station for station in ParkingSpot.objects.filter(is_active=True)}
    target_counts = {int(row["station_id"]): int(row["count"]) for row in target_rows}
    vehicles_by_station: Dict[int | None, List[Vehicle]] = {}
    for vehicle in vehicles:
        vehicles_by_station.setdefault(vehicle.parking_spot.ysu_id if vehicle.parking_spot else None, []).append(vehicle)

    move_pool: List[Vehicle] = list(vehicles_by_station.get(None, []))
    for station_id, station_vehicles in list(vehicles_by_station.items()):
        if station_id is None:
            continue
        keep_count = target_counts.get(station_id, 0)
        if len(station_vehicles) > keep_count:
            move_pool.extend(sorted(station_vehicles, key=lambda item: item.id)[keep_count:])
            vehicles_by_station[station_id] = sorted(station_vehicles, key=lambda item: item.id)[:keep_count]
        else:
            vehicles_by_station[station_id] = sorted(station_vehicles, key=lambda item: item.id)

    updates: List[Vehicle] = []
    histories: List[VehicleLocationHistory] = []
    for station_id, required_count in target_counts.items():
        current_count = len(vehicles_by_station.get(station_id, []))
        if current_count >= required_count:
            continue
        target_station = station_map[station_id]
        deficit = required_count - current_count
        for _ in range(deficit):
            if not move_pool:
                break
            vehicle = move_pool.pop(0)
            previous_station = vehicle.parking_spot
            if previous_station and previous_station.ysu_id == station_id:
                continue
            vehicle.parking_spot = target_station
            vehicle.latitude = target_station.latitude
            vehicle.longitude = target_station.longitude
            updates.append(vehicle)
            histories.append(
                _append_history(
                    vehicle=vehicle,
                    previous_station=previous_station,
                    current_station=target_station,
                    previous_status=vehicle.status,
                    current_status=vehicle.status,
                    reason="实时站点库存同步",
                )
            )

    for vehicle in vehicles:
        if vehicle.parking_spot_id:
            station = vehicle.parking_spot
            changed = False
            if vehicle.latitude != station.latitude:
                vehicle.latitude = station.latitude
                changed = True
            if vehicle.longitude != station.longitude:
                vehicle.longitude = station.longitude
                changed = True
            if changed and vehicle not in updates:
                updates.append(vehicle)

    if updates:
        Vehicle.objects.bulk_update(updates, ["parking_spot", "latitude", "longitude", "update_time"])
    if histories:
        VehicleLocationHistory.objects.bulk_create(histories, batch_size=500)


def _ensure_initial_history_entries(vehicles: Iterable[Vehicle]) -> None:
    vehicles = list(vehicles)
    existing_ids = set(
        VehicleLocationHistory.objects.filter(vehicle_id__in=[vehicle.id for vehicle in vehicles]).values_list("vehicle_id", flat=True)
    )
    missing_entries = [
        _append_history(
            vehicle=vehicle,
            previous_station=None,
            current_station=vehicle.parking_spot,
            previous_status="",
            current_status=vehicle.status,
            reason="当前位置初始化",
        )
        for vehicle in vehicles
        if vehicle.id not in existing_ids
    ]
    if missing_entries:
        VehicleLocationHistory.objects.bulk_create(missing_entries, batch_size=500)


def ensure_vehicle_registry(*, sync_runtime: bool = False) -> List[Vehicle]:
    """Ensure the platform has exactly 1200 vehicles.

    When ``sync_runtime`` is enabled the registry is reconciled to the latest
    runtime snapshot. Read-only pages should keep this disabled to avoid
    unnecessary snapshot writes under SQLite.
    """

    sync_parking_spots()
    vehicles = list(Vehicle.objects.select_related("parking_spot").order_by("id"))
    snapshot = runtime_service.ensure_snapshot() if (sync_runtime or len(vehicles) != TOTAL_SYSTEM_VEHICLES) else None

    if len(vehicles) != TOTAL_SYSTEM_VEHICLES:
        with transaction.atomic():
            Vehicle.objects.all().delete()
            create_batch: List[Vehicle] = []
            sequence = 1
            station_lookup = {station.ysu_id: station for station in ParkingSpot.objects.filter(is_active=True)}
            for row in snapshot.station_rows:
                station = station_lookup[int(row["station_id"])]
                for _ in range(int(row["count"])):
                    create_batch.append(_build_vehicle(f"VEH{sequence:04d}", station))
                    sequence += 1
            Vehicle.objects.bulk_create(create_batch, batch_size=500)
            vehicles = list(Vehicle.objects.select_related("parking_spot").order_by("id"))
            VehicleLocationHistory.objects.bulk_create(
                [
                    _append_history(
                        vehicle=vehicle,
                        previous_station=None,
                        current_station=vehicle.parking_spot,
                        previous_status="",
                        current_status=vehicle.status,
                        reason="车辆注册初始化",
                    )
                    for vehicle in vehicles
                ],
                batch_size=500,
            )
    elif sync_runtime and snapshot is not None:
        _reconcile_vehicle_locations(vehicles, snapshot.station_rows)
        vehicles = list(Vehicle.objects.select_related("parking_spot").order_by("id"))
        _ensure_initial_history_entries(vehicles)
    else:
        _ensure_initial_history_entries(vehicles)

    return list(Vehicle.objects.select_related("parking_spot").order_by("id"))


def latest_ride_records(limit: int = 100) -> List[Dict[str, object]]:
    if not RIDE_DATA_PATH.exists():
        return []
    frame = pd.read_csv(RIDE_DATA_PATH)
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame = frame.sort_values("timestamp")
    records = frame.tail(limit).to_dict("records")
    return records[::-1]


def build_vehicle_queryset(*, station_filter: str = "", status_filter: str = ""):
    ensure_vehicle_registry(sync_runtime=False)
    queryset = Vehicle.objects.select_related("parking_spot").order_by("id")
    if station_filter:
        queryset = queryset.filter(parking_spot__ysu_id=station_filter)
    if status_filter == "normal":
        queryset = queryset.filter(status__in=sorted(NORMAL_STATUSES))
    elif status_filter == "faulty":
        queryset = queryset.filter(status="faulty")
    elif status_filter == "dispatching":
        queryset = queryset.filter(status="in_transit")
    return queryset


def paginate_vehicle_queryset(queryset, *, page_number: int | str = 1, per_page: int = 1200):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)


def get_vehicle_history(vehicle: Vehicle, limit: int = 10):
    return vehicle.location_histories.select_related("previous_station", "current_station").all()[:limit]


def build_vehicle_stats() -> Dict[str, int]:
    queryset = Vehicle.objects.all()
    return {
        "total": queryset.count(),
        "normal": queryset.filter(status__in=sorted(NORMAL_STATUSES)).count(),
        "faulty": queryset.filter(status="faulty").count(),
        "dispatching": queryset.filter(status="in_transit").count(),
    }


def create_manual_dispatch_task(
    *,
    from_station_id: int,
    to_station_id: int,
    dispatch_count: int,
    operator_name: str,
    creator_user=None,
    reason: str = "",
) -> ScheduleTask:
    if from_station_id == to_station_id:
        raise ValueError("起点站和终点站不能相同。")
    if dispatch_count <= 0:
        raise ValueError("调运量必须大于 0。")

    snapshot = runtime_service.ensure_snapshot()
    if snapshot.metrics["global_vehicle_total"] != TOTAL_SYSTEM_VEHICLES:
        raise ValueError("1200 辆车辆守恒校验失败，拒绝创建手动调度任务。")

    station_rows = {row["station_id"]: row for row in snapshot.station_rows}
    if from_station_id not in station_rows or to_station_id not in station_rows:
        raise ValueError("手动调度站点不在 62 个燕山大学停车点范围内。")

    from_row = station_rows[from_station_id]
    to_row = station_rows[to_station_id]
    from_station = ParkingSpot.objects.get(ysu_id=from_station_id)
    to_station = ParkingSpot.objects.get(ysu_id=to_station_id)

    if dispatch_count > int(from_row["count"]):
        raise ValueError("起点站当前库存不足，无法完成指定调运量。")

    distance_cost = round(
        math.hypot(from_station.latitude - to_station.latitude, from_station.longitude - to_station.longitude),
        6,
    )
    reason_text = (
        reason.strip()
        or f"人工调度：{operator_name} 发起 {from_station.spot_name} -> {to_station.spot_name} 调运 {dispatch_count} 辆，保持 1200 辆车辆守恒。"
    )

    creator_role = getattr(creator_user, "role", "") if creator_user else ""
    return ScheduleTask.objects.create(
        task_type="manual_dispatch",
        from_station=from_station,
        to_station=to_station,
        start_location=from_station.spot_name,
        end_location=to_station.spot_name,
        dispatch_count=dispatch_count,
        priority=dispatch_priority(dispatch_count),
        status="pending",
        predicted_gap=float(to_row.get("gap", 0)),
        distance_cost=distance_cost,
        prediction_batch_time=snapshot.bucket_time,
        predicted_time=timezone.now(),
        created_by=creator_user,
        creator_role=creator_role,
        reason=reason_text,
    )


def create_vehicle_fault_task(vehicle: Vehicle, description: str, reporter_name: str, reporter_user=None) -> ScheduleTask:
    previous_status = vehicle.status
    if vehicle.status != "faulty":
        vehicle.status = "faulty"
        vehicle.save(update_fields=["status", "update_time"])
        VehicleLocationHistory.objects.create(
            vehicle=vehicle,
            previous_station=vehicle.parking_spot,
            current_station=vehicle.parking_spot,
            previous_status=previous_status,
            current_status=vehicle.status,
            change_reason="故障标记为待维修",
        )

    location = vehicle.parking_spot.spot_name if vehicle.parking_spot else "未知位置"
    creator_role = getattr(reporter_user, "role", "") if reporter_user else ""
    return ScheduleTask.objects.create(
        task_type="vehicle_fault_report",
        related_vehicle=vehicle,
        start_location=location,
        end_location=location,
        dispatch_count=0,
        priority="high",
        status="pending",
        predicted_time=timezone.now(),
        created_by=reporter_user,
        creator_role=creator_role,
        reason=f"车辆 {vehicle.id} 故障上报：{description or '未填写说明'}。上报人：{reporter_name}",
    )


def create_vehicle_work_order(vehicle: Vehicle, description: str, reporter_name: str, reporter_user=None) -> ScheduleTask:
    location = vehicle.parking_spot.spot_name if vehicle.parking_spot else "未知位置"
    creator_role = getattr(reporter_user, "role", "") if reporter_user else ""
    return ScheduleTask.objects.create(
        task_type="maintenance_work_order",
        related_vehicle=vehicle,
        start_location=location,
        end_location=location,
        dispatch_count=0,
        priority="medium",
        status="pending",
        predicted_time=timezone.now(),
        created_by=reporter_user,
        creator_role=creator_role,
        reason=f"车辆 {vehicle.id} 运维工单：{description or '例行巡检'}。提交人：{reporter_name}",
    )



def update_vehicle_status(vehicle: Vehicle, target_status: str, operator_name: str, description: str = "") -> None:
    allowed = {"available", "normal", "faulty", "in_transit", "dispatching", "locked"}
    if target_status not in allowed:
        raise ValueError("状态值无效")

    current_status = vehicle.status
    previous_status = normalize_vehicle_status(current_status)
    if target_status == "normal":
        new_status = "available"
    elif target_status == "dispatching":
        new_status = "in_transit"
    else:
        new_status = target_status

    if current_status == new_status:
        return

    vehicle.status = new_status
    vehicle.save(update_fields=["status", "update_time"])
    VehicleLocationHistory.objects.create(
        vehicle=vehicle,
        previous_station=vehicle.parking_spot,
        current_station=vehicle.parking_spot,
        previous_status=previous_status,
        current_status=normalize_vehicle_status(new_status),
        change_reason=description or f"{operator_name} 将车辆状态从 {vehicle_status_label(previous_status)} 更改为 {vehicle_status_label(new_status)}",
    )
