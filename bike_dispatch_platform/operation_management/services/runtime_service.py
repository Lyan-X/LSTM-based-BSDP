from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from django.db.utils import OperationalError
from django.utils import timezone
from scipy.optimize import linprog

from bike_dispatch_platform.data_process.models import ParkingSpotRealTime
from bike_dispatch_platform.demand_prediction.services.station_prediction_service import (
    station_prediction_service,
)
from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    classify_inventory_state,
    state_color,
    state_label,
    state_range_text,
)
from bike_dispatch_platform.operation_management.models import ParkingSpot, ScheduleTask
from bike_dispatch_platform.operation_management.services.station_service import (
    get_runtime_settings,
    sync_parking_spots,
)
from station_info.master_data import TOTAL_SYSTEM_VEHICLES


@dataclass
class RuntimeSnapshot:
    bucket_time: pd.Timestamp
    station_rows: List[Dict[str, object]]
    dispatch_suggestions: List[Dict[str, object]]
    metrics: Dict[str, object]


_SNAPSHOT_LOCK = threading.RLock()
_SNAPSHOT_CACHE: Dict[str, RuntimeSnapshot] = {}
PLAYBACK_SPEED_MULTIPLIER = 60
_OUTFLOW_BASELINE_CACHE: Dict[Tuple[int, int], float] | None = None
AUTO_APPLY_DISPATCH_COUNT_THRESHOLD = 15
MIN_DISPATCH_DISTANCE_METERS = 250


def dispatch_priority(dispatch_count: int) -> str:
    count = int(dispatch_count)
    if count >= 20:
        return "high"
    if count >= 10:
        return "medium"
    return "low"


def build_suggestion_fingerprint(*, from_station_id: int, to_station_id: int, dispatch_count: int, prediction_batch_time: object) -> str:
    raw = f"{from_station_id}|{to_station_id}|{dispatch_count}|{prediction_batch_time}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:40]


def _safe_upsert_runtime_row(
    *,
    station: ParkingSpot,
    bucket_time: pd.Timestamp,
    parked_count: int,
    demand_count: int,
    retries: int = 4,
) -> bool:
    for attempt in range(retries):
        try:
            ParkingSpotRealTime.objects.update_or_create(
                parking_spot=station,
                collect_time=bucket_time,
                defaults={
                    "parked_count": int(parked_count),
                    "riding_count": 0,
                    "in_transit_count": 0,
                    "fault_count": 0,
                    "demand_count": int(demand_count),
                },
            )
            return True
        except OperationalError:
            if attempt == retries - 1:
                return False
            time.sleep(0.15 * (attempt + 1))
    return False


def _distance_cost(source: ParkingSpot, target: ParkingSpot) -> float:
    return math.hypot(source.latitude - target.latitude, source.longitude - target.longitude)


def _distance_meters(source: ParkingSpot, target: ParkingSpot) -> int:
    return int(round(_distance_cost(source, target) * 100000))


def _transport_optimize(
    surplus: List[Tuple[ParkingSpot, float]],
    deficit: List[Tuple[ParkingSpot, float]],
) -> List[Dict[str, object]]:
    if not surplus or not deficit:
        return []

    supply = np.array([item[1] for item in surplus], dtype=float)
    demand = np.array([item[1] for item in deficit], dtype=float)
    total_transfer = float(min(supply.sum(), demand.sum()))
    if total_transfer <= 0:
        return []

    variable_count = len(surplus) * len(deficit)
    cost_vector = []
    for source_station, _ in surplus:
        for target_station, _ in deficit:
            cost_vector.append(_distance_cost(source_station, target_station))

    a_ub = []
    b_ub = []
    for source_index in range(len(surplus)):
        row = np.zeros(variable_count)
        row[source_index * len(deficit) : (source_index + 1) * len(deficit)] = 1
        a_ub.append(row)
        b_ub.append(supply[source_index])

    for target_index in range(len(deficit)):
        row = np.zeros(variable_count)
        for source_index in range(len(surplus)):
            row[source_index * len(deficit) + target_index] = 1
        a_ub.append(row)
        b_ub.append(demand[target_index])

    result = linprog(
        c=np.array(cost_vector),
        A_ub=np.array(a_ub) if a_ub else None,
        b_ub=np.array(b_ub) if b_ub else None,
        A_eq=np.ones((1, variable_count)),
        b_eq=np.array([total_transfer]),
        bounds=(0, None),
        method="highs",
    )
    if not result.success:
        return []

    suggestions: List[Dict[str, object]] = []
    solution = result.x.reshape((len(surplus), len(deficit)))
    for source_index, (source_station, source_amount) in enumerate(surplus):
        for target_index, (target_station, target_amount) in enumerate(deficit):
            flow = solution[source_index, target_index]
            if flow < 1:
                continue
            suggestions.append(
                {
                    "from": source_station.spot_name,
                    "to": target_station.spot_name,
                    "count": int(round(flow)),
                    "from_station_id": source_station.ysu_id,
                    "to_station_id": target_station.ysu_id,
                    "from_surplus": int(round(source_amount)),
                    "to_shortage": int(round(target_amount)),
                    "predicted_gap": round(float(target_amount), 2),
                    "distance_cost": round(_distance_cost(source_station, target_station), 6),
                    "cost": round(_distance_cost(source_station, target_station), 6),
                    "reason": (
                        f"站点 {source_station.spot_name} 当前存在可调出车辆，"
                        f"站点 {target_station.spot_name} 当前存在补车需求"
                    ),
                }
            )
    return suggestions


def _hourly_outflow_baselines() -> Dict[Tuple[int, int], float]:
    global _OUTFLOW_BASELINE_CACHE
    if _OUTFLOW_BASELINE_CACHE is None:
        dataset = station_prediction_service.dataset.copy()
        dataset["hour_of_day"] = dataset["hour"].dt.hour
        grouped = dataset.groupby(["ysu_id", "hour_of_day"])["outflow"].mean().round(4)
        _OUTFLOW_BASELINE_CACHE = {
            (int(station_id), int(hour_of_day)): float(value)
            for (station_id, hour_of_day), value in grouped.items()
        }
    return _OUTFLOW_BASELINE_CACHE


class RuntimeService:
    """Build 10-second runtime snapshots from raw mapped historical data."""

    def _bucket_time(self, now: pd.Timestamp) -> pd.Timestamp:
        second = (now.second // 10) * 10
        return now.replace(second=second, microsecond=0)

    def _cache_key(self, bucket_time: pd.Timestamp) -> str:
        return bucket_time.isoformat()

    def _state_payload(self, inventory: int, t_plus_1_net_flow: float, station: ParkingSpot = None) -> Dict[str, str]:
        scheme_key = "state_9"
        low_warning = station.low_warning_threshold if station else 8
        high_warning = station.high_warning_threshold if station else 40
        max_capacity = station.max_capacity if station else 60
        state_index = classify_inventory_state(
            inventory,
            low_warning,
            high_warning,
            max_capacity,
            scheme_key=scheme_key,
        )
        label = state_label(state_index, scheme_key=scheme_key)
        color = state_color(state_index, scheme_key=scheme_key)
        code = "scarce" if state_index < 3 else ("saturated" if state_index >= 6 else "balanced")
        badge = "danger" if state_index < 2 or state_index >= 8 else ("warning" if state_index < 3 or state_index >= 6 else "success")
        range_text = state_range_text(
            state_index,
            low_warning_threshold=low_warning,
            high_warning_threshold=high_warning,
            max_capacity=max_capacity,
            scheme_key=scheme_key,
        )
        return {
            "label": label,
            "group": code,
            "badge": badge,
            "color": color,
            "range": range_text,
        }

    def _balanced_target_inventory(self, station: ParkingSpot) -> float:
        return round((float(station.low_warning_threshold) + float(station.high_warning_threshold)) / 2.0, 2)

    def _estimate_next_hour_demand(
        self,
        *,
        station: ParkingSpot,
        current_count: int,
        current_row: pd.Series,
        next_row: pd.Series,
        predicted_net_flow: float,
        decision_hour: int,
    ) -> float:
        baseline_outflow = _hourly_outflow_baselines().get((station.ysu_id, decision_hour), float(next_row["outflow"]))
        current_outflow = max(0.0, float(current_row["outflow"]))
        next_outflow = max(0.0, float(next_row["outflow"]))
        historical_pressure = max(current_outflow, next_outflow, baseline_outflow)
        stock_adjustment = max(0.0, historical_pressure - float(current_count))
        forecast_departure_pressure = max(0.0, -float(predicted_net_flow))
        if current_count <= 0:
            return round(max(historical_pressure, forecast_departure_pressure), 2)
        return round(max(historical_pressure + stock_adjustment, forecast_departure_pressure), 2)

    def _historical_runtime_frames(
        self,
        bucket_time: pd.Timestamp,
        active_stations: List[ParkingSpot],
    ) -> tuple[pd.Timestamp, pd.Timestamp, pd.DataFrame, pd.DataFrame, float]:
        dataset = station_prediction_service.dataset.copy()
        dataset["source_date"] = dataset["hour"].dt.date

        daily_span = (
            dataset.groupby("source_date")["inventory"]
            .agg(["min", "max"])
            .assign(range=lambda frame: frame["max"] - frame["min"])
            .sort_values("range", ascending=False)
        )
        playback_date = daily_span.index[0]
        day_frame = dataset[dataset["source_date"] == playback_date].copy()
        day_hours = sorted(day_frame["hour"].drop_duplicates().tolist())
        if len(day_hours) < 2:
            raise ValueError("高波动映射日缺少足够的小时级时序数据")

        hour_index = min(bucket_time.hour, len(day_hours) - 2)
        current_hour = pd.Timestamp(day_hours[hour_index])
        next_hour = pd.Timestamp(day_hours[min(hour_index + 1, len(day_hours) - 1)])

        current_frame = (
            day_frame[day_frame["hour"] == current_hour]
            .sort_values("ysu_id")
            .set_index("ysu_id")
        )
        next_frame = (
            day_frame[day_frame["hour"] == next_hour]
            .sort_values("ysu_id")
            .set_index("ysu_id")
        )
        if len(current_frame) != len(active_stations):
            raise ValueError("真实映射时序当前小时的站点数量不完整")

        # Accelerate the within-hour playback so 10-second refreshes produce
        # observable but still deterministic movements from the real hourly frames.
        second_in_hour = ((bucket_time.minute * 60 + bucket_time.second) * PLAYBACK_SPEED_MULTIPLIER) % 3600
        interpolation_ratio = second_in_hour / 3600.0
        return current_hour, next_hour, current_frame, next_frame, interpolation_ratio

    def ensure_snapshot(self, now: pd.Timestamp | None = None, _retry: bool = False) -> RuntimeSnapshot:
        source_now = now or timezone.now()
        if getattr(source_now, "tzinfo", None) is not None:
            source_now = timezone.localtime(source_now)
        now = pd.Timestamp(source_now)
        bucket_time = self._bucket_time(now)
        cache_key = self._cache_key(bucket_time)

        with _SNAPSHOT_LOCK:
            sync_parking_spots()
            settings_obj = get_runtime_settings()
            active_stations = list(ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"))
            expected_station_count = len(active_stations)

            cached_snapshot = _SNAPSHOT_CACHE.get(cache_key)
            if (
                cached_snapshot
                and len(cached_snapshot.station_rows) == expected_station_count
                and cached_snapshot.metrics.get("global_vehicle_total") == TOTAL_SYSTEM_VEHICLES
            ):
                return cached_snapshot

            existing_rows = list(
                ParkingSpotRealTime.objects.filter(collect_time=bucket_time)
                .select_related("parking_spot")
                .order_by("parking_spot__ysu_id")
            )
            if existing_rows and len(existing_rows) != expected_station_count:
                ParkingSpotRealTime.objects.filter(collect_time=bucket_time).delete()
                existing_rows = []

            current_hour, next_hour, current_frame, next_frame, interp_ratio = self._historical_runtime_frames(bucket_time, active_stations)
            prediction_error = None
            prediction_map: Dict[int, Dict[str, object]] = {}
            try:
                prediction_batch = station_prediction_service.generate_predictions(force=False)
                prediction_map = prediction_batch.station_payloads
            except Exception as exc:  # pragma: no cover - graceful fallback for UI continuity
                prediction_error = str(exc)

            if not existing_rows:
                latest_previous = (
                    ParkingSpotRealTime.objects.filter(collect_time__lt=bucket_time)
                    .select_related("parking_spot")
                    .order_by("-collect_time", "parking_spot__ysu_id")
                )
                previous_time = latest_previous.values_list("collect_time", flat=True).first()
                fallback_rows = []
                if previous_time is not None:
                    fallback_rows = list(
                        ParkingSpotRealTime.objects.filter(collect_time=previous_time)
                        .select_related("parking_spot")
                        .order_by("parking_spot__ysu_id")
                    )

                write_failed = False
                for station in active_stations:
                    cur_row = current_frame.loc[station.ysu_id]
                    nxt_row = next_frame.loc[station.ysu_id]
                    cur_inv = float(cur_row["inventory"])
                    nxt_inv = float(nxt_row["inventory"])
                    parked_count = int(round(cur_inv + (nxt_inv - cur_inv) * interp_ratio))
                    demand_count = int(round(float(max(cur_row["inflow"], cur_row["outflow"], abs(cur_row["net_flow"])))))
                    if not _safe_upsert_runtime_row(
                        station=station,
                        bucket_time=bucket_time,
                        parked_count=parked_count,
                        demand_count=demand_count,
                    ):
                        write_failed = True
                        break

                if write_failed:
                    existing_rows = list(
                        ParkingSpotRealTime.objects.filter(collect_time=bucket_time)
                        .select_related("parking_spot")
                        .order_by("parking_spot__ysu_id")
                    )
                    if len(existing_rows) != expected_station_count:
                        if fallback_rows:
                            existing_rows = fallback_rows
                            bucket_time = pd.Timestamp(previous_time)
                            cache_key = self._cache_key(bucket_time)
                            current_hour, next_hour, current_frame, next_frame, interp_ratio = self._historical_runtime_frames(bucket_time, active_stations)
                        else:
                            raise ValueError("实时快照写入失败，且不存在可回退的完整快照")
                else:
                    existing_rows = list(
                        ParkingSpotRealTime.objects.filter(collect_time=bucket_time)
                        .select_related("parking_spot")
                        .order_by("parking_spot__ysu_id")
                    )

            station_rows: List[Dict[str, object]] = []
            surplus: List[Tuple[ParkingSpot, float]] = []
            deficit: List[Tuple[ParkingSpot, float]] = []
            total_gap = 0.0
            raw_counts: List[int] = []

            for row in existing_rows:
                station = row.parking_spot
                current_row = current_frame.loc[station.ysu_id]
                next_row = next_frame.loc[station.ysu_id]

                cur_inv = float(current_row["inventory"])
                nxt_inv = float(next_row["inventory"])
                current_count = int(round(cur_inv + (nxt_inv - cur_inv) * interp_ratio))
                raw_counts.append(current_count)
                prediction_row = prediction_map.get(station.ysu_id, {})
                t_plus_1_inventory = float(prediction_row.get("t_plus_1_inventory", next_row["inventory"]))
                t_plus_1_net_flow = float(prediction_row.get("t_plus_1_prediction", next_row["net_flow"]))
                current_state = self._state_payload(current_count, t_plus_1_net_flow, station=station)
                future_state = self._state_payload(int(round(t_plus_1_inventory)), t_plus_1_net_flow, station=station)
                if prediction_row:
                    future_state["label"] = str(prediction_row.get("t_plus_1_state_label", future_state["label"]))
                    future_state["color"] = str(prediction_row.get("t_plus_1_state_color", future_state["color"]))
                    future_state["range"] = str(prediction_row.get("t_plus_1_state_range", future_state["range"]))

                target_inventory = self._balanced_target_inventory(station)
                current_gap = round(target_inventory - current_count, 2)
                predicted_gap_t1 = round(target_inventory - t_plus_1_inventory, 2)
                decision_hour = pd.Timestamp(
                    prediction_row.get("decision_basis_hour", next_hour.isoformat())
                ).hour
                demand = self._estimate_next_hour_demand(
                    station=station,
                    current_count=current_count,
                    current_row=current_row,
                    next_row=next_row,
                    predicted_net_flow=t_plus_1_net_flow,
                    decision_hour=decision_hour,
                )
                effective_gap = current_gap
                if (
                    current_state["group"] == "balanced"
                    and future_state["group"] != "balanced"
                    and abs(predicted_gap_t1) >= settings_obj.dispatch_trigger_threshold
                ):
                    effective_gap = predicted_gap_t1

                if effective_gap >= settings_obj.dispatch_trigger_threshold:
                    deficit.append((station, abs(effective_gap)))
                elif effective_gap <= -settings_obj.dispatch_trigger_threshold:
                    surplus.append((station, abs(effective_gap)))
                total_gap += abs(effective_gap)

                station_rows.append(
                    {
                        "station_id": station.ysu_id,
                        "name": station.spot_name,
                        "lat": station.latitude,
                        "lng": station.longitude,
                        "count": current_count,
                        "capacity": max(station.max_capacity, current_count),
                        "target_inventory": target_inventory,
                        "warning_status": "low" if current_state["group"] == "scarce" else ("high" if current_state["group"] == "saturated" else "normal"),
                        "current_state_label": current_state["label"],
                        "current_state_color": current_state["color"],
                        "current_state_group": current_state["group"],
                        "current_state_badge": current_state["badge"],
                        "current_state_range": current_state.get("range", ""),
                        "demand": demand,
                        "gap": current_gap,
                        "t_plus_1_gap": predicted_gap_t1,
                        "predicted_inventory_t1": round(t_plus_1_inventory, 2),
                        "t_plus_1_net_flow": round(t_plus_1_net_flow, 2),
                        "decision_basis_hour": prediction_row.get("decision_basis_hour", next_hour.isoformat()),
                        "needs_operation": current_state["group"] != "balanced" or abs(predicted_gap_t1) >= settings_obj.dispatch_trigger_threshold,
                        "t_plus_1_state_index": prediction_row.get("t_plus_1_state_index"),
                        "t_plus_1_state_code": prediction_row.get("t_plus_1_state_code", future_state["group"]),
                        "t_plus_1_state_label": future_state["label"],
                        "t_plus_1_state_color": future_state["color"],
                        "t_plus_1_state_range": future_state.get("range", ""),
                        "t_plus_1_state_midpoint": round(float(prediction_row.get("t_plus_1_state_midpoint", t_plus_1_inventory)), 2),
                    }
                )

            total_raw = sum(raw_counts)
            diff = TOTAL_SYSTEM_VEHICLES - total_raw
            if diff != 0 and len(station_rows) > 0:
                sorted_indices = sorted(
                    range(len(station_rows)),
                    key=lambda i: raw_counts[i],
                    reverse=(diff < 0),
                )
                remaining = abs(diff)
                for idx in sorted_indices:
                    if remaining <= 0:
                        break
                    if diff > 0:
                        station_rows[idx]["count"] += 1
                        remaining -= 1
                    elif raw_counts[idx] > 0:
                        station_rows[idx]["count"] -= 1
                        remaining -= 1

            station_lookup = {station.ysu_id: station for station in active_stations}
            suggestions = [
                item for item in _transport_optimize(surplus, deficit)
                if _distance_meters(
                    station_lookup[item["from_station_id"]],
                    station_lookup[item["to_station_id"]],
                ) >= MIN_DISPATCH_DISTANCE_METERS
            ]
            if not suggestions and surplus and deficit:
                source_station, source_amount = sorted(surplus, key=lambda item: item[1], reverse=True)[0]
                target_station, target_amount = sorted(deficit, key=lambda item: item[1], reverse=True)[0]
                fallback_count = int(max(1, min(round(source_amount), round(target_amount), 8)))
                suggestions = [
                    {
                        "from": source_station.spot_name,
                        "to": target_station.spot_name,
                        "count": fallback_count,
                        "from_station_id": source_station.ysu_id,
                        "to_station_id": target_station.ysu_id,
                        "from_surplus": int(round(source_amount)),
                        "to_shortage": int(round(target_amount)),
                        "predicted_gap": round(float(target_amount), 2),
                        "distance_cost": round(_distance_cost(source_station, target_station), 6),
                        "cost": round(_distance_cost(source_station, target_station), 6),
                        "reason": "自动兜底建议：按当前最大盈余站点与最大短缺站点生成最小可执行调度任务。",
                    }
                ]
            elif not suggestions and len(station_rows) >= 2:
                sorted_rows = sorted(station_rows, key=lambda item: item.get("count", 0))
                target_row = sorted_rows[0]
                source_row = sorted_rows[-1]
                if source_row["station_id"] != target_row["station_id"] and int(source_row.get("count", 0)) > 0:
                    from_station_obj = ParkingSpot.objects.filter(ysu_id=source_row["station_id"]).first()
                    to_station_obj = ParkingSpot.objects.filter(ysu_id=target_row["station_id"]).first()
                    if from_station_obj and to_station_obj:
                        suggestions = [
                            {
                                "from": source_row["name"],
                                "to": target_row["name"],
                                "count": 1,
                                "from_station_id": source_row["station_id"],
                                "to_station_id": target_row["station_id"],
                                "from_surplus": int(max(0, source_row.get("count", 0) - source_row.get("target_inventory", 0))),
                                "to_shortage": int(max(0, target_row.get("target_inventory", 0) - target_row.get("count", 0))),
                                "predicted_gap": round(float(target_row.get("gap", 0)), 2),
                                "distance_cost": round(_distance_cost(from_station_obj, to_station_obj), 6),
                                "cost": round(_distance_cost(from_station_obj, to_station_obj), 6),
                                "reason": "自动演示建议：当前无明显调度缺口时，按最低库存站点与最高库存站点生成 1 辆示例任务。",
                            }
                        ]
            station_row_map = {item["station_id"]: item for item in station_rows}
            for item in suggestions:
                source_row = station_row_map.get(item["from_station_id"], {})
                target_row = station_row_map.get(item["to_station_id"], {})
                item["reason"] = (
                    f"来源站点供需缺口 {float(source_row.get('gap', 0)):+.2f}，"
                    f"目标站点供需缺口 {float(target_row.get('gap', 0)):+.2f}；"
                    f"目标站点 T+1 状态 {target_row.get('t_plus_1_state_label', '--')}，"
                    f"T+1 净流量 {float(target_row.get('t_plus_1_net_flow', 0)):+.2f}"
                )
            metrics = {
                "global_vehicle_total": int(sum(item["count"] for item in station_rows)),
                "dispatchable_vehicles": int(round(sum(item[1] for item in surplus))),
                "locked_vehicles": 0,
                "total_surplus": int(round(sum(item[1] for item in surplus))),
                "total_shortage": int(round(sum(item[1] for item in deficit))),
                "matching_rate": round(
                    min(
                        1.0,
                        sum(item["count"] for item in suggestions)
                        / max(1, int(round(sum(item[1] for item in deficit)))),
                    ),
                    3,
                ),
                "dispatch_cost": round(sum(item["cost"] * item["count"] for item in suggestions), 6),
                "global_total_check": int(sum(item["count"] for item in station_rows)),
                "current_gap_total": round(total_gap, 2),
                "refresh_seconds": settings_obj.dashboard_refresh_seconds,
                "warning_threshold": settings_obj.demand_warning_threshold,
                "dispatch_threshold": settings_obj.dispatch_trigger_threshold,
                "source_hour": current_hour.isoformat(),
                "source_next_hour": next_hour.isoformat(),
                "prediction_error": prediction_error,
            }
            if metrics["global_vehicle_total"] != TOTAL_SYSTEM_VEHICLES:
                _SNAPSHOT_CACHE.pop(cache_key, None)

            snapshot = RuntimeSnapshot(
                bucket_time=bucket_time,
                station_rows=station_rows,
                dispatch_suggestions=suggestions,
                metrics=metrics,
            )
            _SNAPSHOT_CACHE.clear()
            _SNAPSHOT_CACHE[cache_key] = snapshot
            return snapshot

    def create_schedule_tasks(self, snapshot: RuntimeSnapshot) -> List[ScheduleTask]:
        created_tasks: List[ScheduleTask] = []
        if snapshot.station_rows and snapshot.station_rows[0].get("decision_basis_hour"):
            prediction_batch_time = pd.Timestamp(snapshot.station_rows[0]["decision_basis_hour"]).to_pydatetime()
        else:
            prediction_batch_time = snapshot.bucket_time.to_pydatetime()

        for suggestion in snapshot.dispatch_suggestions:
            from_station = ParkingSpot.objects.filter(ysu_id=suggestion["from_station_id"]).first()
            to_station = ParkingSpot.objects.filter(ysu_id=suggestion["to_station_id"]).first()
            if not from_station or not to_station:
                continue
            if _distance_meters(from_station, to_station) < MIN_DISPATCH_DISTANCE_METERS:
                continue
            fingerprint = build_suggestion_fingerprint(
                from_station_id=suggestion["from_station_id"],
                to_station_id=suggestion["to_station_id"],
                dispatch_count=suggestion["count"],
                prediction_batch_time=prediction_batch_time,
            )
            if ScheduleTask.objects.filter(suggestion_fingerprint=fingerprint).exists():
                continue
            auto_apply = int(suggestion["count"]) >= AUTO_APPLY_DISPATCH_COUNT_THRESHOLD
            task = ScheduleTask.objects.create(
                task_type="vehicle_dispatch",
                from_station=from_station,
                to_station=to_station,
                start_location=suggestion["from"],
                end_location=suggestion["to"],
                dispatch_count=suggestion["count"],
                priority=dispatch_priority(suggestion["count"]),
                predicted_gap=suggestion["to_shortage"],
                distance_cost=suggestion["cost"],
                prediction_batch_time=prediction_batch_time,
                predicted_time=snapshot.bucket_time.to_pydatetime(),
                status="in_progress" if auto_apply else "pending",
                reason=("系统自动实施：" if auto_apply else "系统建议待确认：") + suggestion["reason"],
                suggestion_fingerprint=fingerprint,
            )
            created_tasks.append(task)
        return created_tasks


runtime_service = RuntimeService()
