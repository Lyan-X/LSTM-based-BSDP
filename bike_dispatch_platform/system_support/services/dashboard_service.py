from __future__ import annotations

from typing import Dict, List

import pandas as pd

from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.operation_management.models import ScheduleTask, Vehicle
from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service
from bike_dispatch_platform.operation_management.services.vehicle_service import ensure_vehicle_registry, vehicle_status_label


class DashboardService:
    """Compose dashboard payloads from runtime and prediction services."""

    def build_payload(self) -> Dict[str, object]:
        snapshot = runtime_service.ensure_snapshot()
        ensure_vehicle_registry(sync_runtime=True)
        dataset = station_prediction_service.dataset
        source_hour = pd.Timestamp(snapshot.metrics.get("source_hour", snapshot.bucket_time))
        display_anchor = pd.Timestamp(snapshot.bucket_time)
        history_start = source_hour - pd.Timedelta(hours=47)
        history_frame = dataset[(dataset["hour"] >= history_start) & (dataset["hour"] <= source_hour)].copy()
        hourly_rides = (
            history_frame.groupby("hour")["outflow"]
            .sum()
            .sort_index()
            .tail(48)
            .round(2)
        )

        prediction_batch = {}
        prediction_error = None
        try:
            prediction_batch = station_prediction_service.get_batch_response(force=False)
        except FileNotFoundError as exc:
            prediction_error = str(exc)

        top_gap_station_ids = [
            row["station_id"]
            for row in sorted(snapshot.station_rows, key=lambda item: abs(float(item.get("gap", 0))), reverse=True)[:3]
        ]
        station_trends: Dict[str, List[Dict[str, object]]] = {}
        prediction_map = {
            int(item["station_id"]): item for item in prediction_batch.get("stations", [])
        } if prediction_batch else {}
        for station_id in top_gap_station_ids:
            station_frame = history_frame[history_frame["ysu_id"] == station_id].copy()
            hourly_inventory = (
                station_frame.groupby("hour")["inventory"]
                .last()
                .sort_index()
                .tail(48)
                .round(2)
            )
            next_hour_prediction = prediction_map.get(int(station_id), {})
            values = [float(value) for value in hourly_inventory.tolist()]
            trend_rows: List[Dict[str, object]] = []
            start_hour = display_anchor - pd.Timedelta(hours=max(len(values) - 1, 0))
            for idx, value in enumerate(values):
                trend_rows.append(
                    {
                        "timestamp": (start_hour + pd.Timedelta(hours=idx)).isoformat(),
                        "value": value,
                    }
                )
            if next_hour_prediction:
                prediction_hour = display_anchor + pd.Timedelta(hours=1)
                trend_rows.append(
                    {
                        "timestamp": prediction_hour.isoformat(),
                        "value": float(next_hour_prediction.get("t_plus_1_inventory", 0)),
                        "is_prediction": True,
                    }
                )
            station_trends[str(station_id)] = trend_rows

        vehicle_map: Dict[int, List[Dict[str, object]]] = {}
        for vehicle in Vehicle.objects.select_related("parking_spot").order_by("id"):
            if vehicle.parking_spot_id is None:
                continue
            vehicle_map.setdefault(vehicle.parking_spot.ysu_id, []).append(
                {
                    "id": vehicle.id,
                    "status": vehicle_status_label(vehicle.status),
                }
            )

        station_dispatch_map: Dict[int, List[Dict[str, object]]] = {}
        related_tasks = ScheduleTask.objects.select_related("from_station", "to_station").order_by("-create_time")[:200]
        for task in related_tasks:
            row = {
                "id": task.id,
                "task_type": task.task_type,
                "status": task.status,
                "status_label": task.get_status_display(),
                "start_location": task.start_location,
                "end_location": task.end_location,
                "dispatch_count": task.dispatch_count,
                "created_at": task.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if task.from_station_id:
                station_dispatch_map.setdefault(task.from_station.ysu_id, []).append(row)
            if task.to_station_id and task.to_station_id != task.from_station_id:
                station_dispatch_map.setdefault(task.to_station.ysu_id, []).append(row)

        def station_photo_url(station_id: int) -> str:
            return f"/static/images/stations/site_{station_id}.jpg"

        enriched_station_rows = []
        for row in snapshot.station_rows:
            station_id = int(row["station_id"])
            enriched_station_rows.append(
                {
                    **row,
                    "photo_url": station_photo_url(station_id),
                    "photo_fallback_url": "/static/images/stations/site_default.jpg",
                    "parked_vehicles": vehicle_map.get(station_id, []),
                    "vehicle_count": len(vehicle_map.get(station_id, [])),
                    "dispatch_tasks": station_dispatch_map.get(station_id, [])[:20],
                }
            )

        heatmap = [
            {
                "station_id": row["station_id"],
                "name": row["name"],
                "value": row["count"],
                "capacity": row["capacity"],
                "utilization": round(row["count"] / row["capacity"], 4) if row["capacity"] else 0,
            }
            for row in enriched_station_rows
        ]

        return {
            "generated_at": snapshot.bucket_time.isoformat(),
            "kpis": {
                "total_vehicles": snapshot.metrics["global_vehicle_total"],
                "online_stations": len(snapshot.station_rows),
                "today_total_rides": int(round(float(hourly_rides.sum()))),
                "current_gap_total": snapshot.metrics["current_gap_total"],
            },
            "stations": enriched_station_rows,
            "dispatch_suggestions": snapshot.dispatch_suggestions,
            "metrics": snapshot.metrics,
            "charts": {
                "ride_trend": [
                    {"timestamp": pd.Timestamp(hour).isoformat(), "value": float(value)}
                    for hour, value in hourly_rides.items()
                ],
                "station_trends": station_trends,
                "top_gap_station_ids": top_gap_station_ids,
                "inventory_heatmap": heatmap,
            },
            "prediction_error": prediction_error,
        }


dashboard_service = DashboardService()
