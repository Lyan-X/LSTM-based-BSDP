from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bike_dispatch_platform.bike_dispatch_platform.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client

from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.operation_management.models import ParkingSpot, ScheduleTask, Vehicle, VehicleLocationHistory
from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service
from bike_dispatch_platform.operation_management.services.vehicle_service import ensure_vehicle_registry


REPORT_PATH = Path(__file__).resolve().parent / "verify_srs_compliance_report.json"
User = get_user_model()


def _ms(func):
    start = time.perf_counter()
    result = func()
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    return elapsed, result


def _build_temp_users():
    users = []
    for username, role in [
        ("srs_admin_tmp", "admin"),
        ("srs_operator_tmp", "operator"),
        ("srs_predictor_tmp", "predictor"),
    ]:
        user, _ = User.objects.get_or_create(username=username, defaults={"role": role})
        user.role = role
        user.set_password("SrsVerify!2026")
        user.save()
        users.append(user)
    return users


def _cleanup_temp_users():
    User.objects.filter(username__in=["srs_admin_tmp", "srs_operator_tmp", "srs_predictor_tmp"]).delete()


def _role_matrix(users):
    matrix = {}
    expected = {
        "admin": {
            "/system/dashboard/": 200,
            "/predict/": 200,
            "/operation/": 200,
            "/operation/stations/": 200,
            "/operation/vehicles/": 200,
            "/data/": 200,
            "/system/settings/": 200,
            "/system/backups/": 200,
            "/system/logs/": 200,
        },
        "operator": {
            "/system/dashboard/": 200,
            "/predict/": 200,
            "/operation/": 200,
            "/operation/stations/": 200,
            "/operation/vehicles/": 200,
            "/data/": 403,
            "/system/settings/": 403,
            "/system/backups/": 403,
            "/system/logs/": 403,
        },
        "predictor": {
            "/system/dashboard/": 200,
            "/predict/": 200,
            "/operation/": 403,
            "/operation/stations/": 403,
            "/operation/vehicles/": 403,
            "/data/": 200,
            "/system/settings/": 403,
            "/system/backups/": 403,
            "/system/logs/": 403,
        },
    }

    for user in users:
        client = Client()
        client.force_login(user)
        role_result = {}
        for path, expected_status in expected[user.role].items():
            response = client.get(path)
            role_result[path] = {
                "status": response.status_code,
                "expected": expected_status,
                "pass": response.status_code == expected_status,
            }
        matrix[user.role] = role_result
    return matrix


def _export_probe(users):
    admin_user = next(user for user in users if user.role == "admin")
    operator_user = next(user for user in users if user.role == "operator")
    predictor_user = next(user for user in users if user.role == "predictor")

    checks = []
    for user, path in [
        (admin_user, "/operation/stations/1/history/export/?format=xlsx"),
        (operator_user, "/operation/tasks/export/?format=csv"),
        (predictor_user, "/predict/export/report/?format=xlsx"),
    ]:
        client = Client()
        client.force_login(user)
        response = client.get(path)
        checks.append(
            {
                "role": user.role,
                "path": path,
                "status": response.status_code,
                "content_type": response.headers.get("Content-Type", ""),
                "pass": response.status_code == 200,
            }
        )
    return checks


def _heatmap_feature_probe(users):
    operator_user = next(user for user in users if user.role == "operator")
    client = Client()
    client.force_login(operator_user)
    page = client.get("/operation/heatmap/")
    payload = client.get("/operation/api/parking-data/")
    data = payload.json() if payload.status_code == 200 else {}
    first_row = (data.get("data") or [{}])[0]
    html = page.content.decode("utf-8", errors="ignore") if page.status_code == 200 else ""
    return {
        "heatmap_route_status": page.status_code,
        "api_status": payload.status_code,
        "station_count": len(data.get("data", [])),
        "marker_count_field_present": "count" in first_row,
        "t_plus_1_field_present": "t_plus_1_net_flow" in first_row,
        "table_chart_view_present": all(flag in html for flag in ["dispatchTableView", "dispatchChartView", "sortable"]),
        "map_linkage_present": "focusStation" in html,
    }


def _vehicle_feature_probe(users):
    operator_user = next(user for user in users if user.role == "operator")
    client = Client()
    client.force_login(operator_user)

    ensure_vehicle_registry()
    vehicle_count = Vehicle.objects.count()
    first_vehicle = Vehicle.objects.order_by("id").first()
    list_latency_ms, list_response = _ms(lambda: client.get("/operation/vehicles/?status=normal"))
    detail_response = client.get(f"/operation/vehicles/{first_vehicle.id}/") if first_vehicle else None

    history_before = VehicleLocationHistory.objects.filter(vehicle=first_vehicle).count() if first_vehicle else 0
    tasks_before = ScheduleTask.objects.filter(related_vehicle=first_vehicle).count() if first_vehicle else 0
    fault_response = None
    tasks_after = tasks_before
    history_after = history_before
    created_task_ids = []
    previous_status = None

    if first_vehicle:
        previous_status = first_vehicle.status
        fault_response = client.post(
            "/operation/vehicles/",
            {"action": "report_fault", "vehicle_id": first_vehicle.id, "description": "自动化验收故障标记"},
            follow=False,
        )
        tasks_after = ScheduleTask.objects.filter(related_vehicle=first_vehicle).count()
        history_after = VehicleLocationHistory.objects.filter(vehicle=first_vehicle).count()
        created_task_ids = list(
            ScheduleTask.objects.filter(related_vehicle=first_vehicle).order_by("-id").values_list("id", flat=True)[:2]
        )
        first_vehicle.refresh_from_db()
        first_vehicle.status = previous_status
        first_vehicle.save(update_fields=["status", "update_time"])
        ScheduleTask.objects.filter(id__in=created_task_ids).delete()
        extra_history_ids = list(
            VehicleLocationHistory.objects.filter(vehicle=first_vehicle).order_by("-id").values_list("id", flat=True)[
                : max(0, history_after - history_before)
            ]
        )
        if extra_history_ids:
            VehicleLocationHistory.objects.filter(id__in=extra_history_ids).delete()

    return {
        "vehicle_count": vehicle_count,
        "vehicle_list_status": list_response.status_code,
        "vehicle_filter_latency_ms": list_latency_ms,
        "vehicle_detail_status": detail_response.status_code if detail_response else 404,
        "filter_latency_ok": list_response.status_code == 200 and list_latency_ms < 2000,
        "history_before": history_before,
        "history_after": history_after,
        "fault_mark_status": fault_response.status_code if fault_response else 404,
        "work_order_generated": tasks_after >= tasks_before + 2 if first_vehicle else False,
        "vehicle_total_locked_to_1200": vehicle_count == 1200,
    }


def _concurrency_probe(workers: int = 20):
    errors = []
    totals = []

    def _task():
        snapshot = runtime_service.ensure_snapshot()
        return snapshot.metrics["global_vehicle_total"]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_task) for _ in range(workers)]
        for future in as_completed(futures):
            try:
                totals.append(future.result())
            except Exception as exc:
                errors.append(str(exc))

    return {
        "workers": workers,
        "errors": errors,
        "all_totals_locked_to_1200": all(total == 1200 for total in totals) if totals else False,
        "completed": len(totals),
    }


def run_checks():
    users = _build_temp_users()
    try:
        root_client = Client()
        root_response = root_client.get("/")
        admin_user = next(user for user in users if user.role == "admin")
        admin_client = Client()
        admin_client.force_login(admin_user)
        admin_client.get("/predict/api/48h/")
        runtime_service.ensure_snapshot()
        prediction_api_latency_ms, prediction_payload = _ms(lambda: admin_client.get("/predict/api/48h/"))
        snapshot_latency_ms, snapshot = _ms(runtime_service.ensure_snapshot)

        station_count = ParkingSpot.objects.filter(is_active=True).count()
        first_station = prediction_payload.json()["stations"][0] if prediction_payload.status_code == 200 else {}

        results = {
            "root_redirect": {
                "status": root_response.status_code,
                "location": root_response.headers.get("Location"),
                "pass": root_response.status_code == 302 and root_response.headers.get("Location") == "/system/dashboard/",
            },
            "data_constraints": {
                "active_station_count": station_count,
                "global_vehicle_total": snapshot.metrics["global_vehicle_total"],
                "station_count_pass": station_count == 62,
                "vehicle_total_pass": snapshot.metrics["global_vehicle_total"] == 1200,
            },
            "prediction_api": {
                "status": prediction_payload.status_code,
                "latency_ms": prediction_api_latency_ms,
                "station_count": len(prediction_payload.json().get("stations", [])) if prediction_payload.status_code == 200 else 0,
                "horizon_length": len(first_station.get("timestamps", [])),
                "t_plus_1_field_present": "t_plus_1_prediction" in first_station and "decision_basis_hour" in first_station,
            },
            "runtime_snapshot": {
                "latency_ms": snapshot_latency_ms,
                "station_rows": len(snapshot.station_rows),
                "uses_t_plus_1": all("t_plus_1_net_flow" in row and "decision_basis_hour" in row for row in snapshot.station_rows),
                "global_total_check": snapshot.metrics["global_total_check"],
            },
            "operation_heatmap_features": _heatmap_feature_probe(users),
            "vehicle_management_features": _vehicle_feature_probe(users),
            "concurrency": _concurrency_probe(),
            "exports": _export_probe(users),
            "rbac": _role_matrix(users),
            "parallel_srs_assets": {
                "srs_training_script_exists": Path("build_lstm_system_srs.py").exists(),
                "srs_model_exists": Path("bike_dispatch_platform/demand_prediction/model_assets/bike_sharing_lstm_model_srs.keras").exists(),
                "srs_scaler_exists": Path("bike_dispatch_platform/demand_prediction/model_assets/scaler_srs.pkl").exists(),
            },
        }
    finally:
        _cleanup_temp_users()

    REPORT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_checks()
