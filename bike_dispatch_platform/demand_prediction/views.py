from __future__ import annotations

import subprocess
import sys

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from bike_dispatch_platform.demand_prediction.models import StationPrediction
from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.operation_management.models import ParkingSpot
from bike_dispatch_platform.system_support.export_utils import dataframe_to_response, resolve_export_format
from bike_dispatch_platform.system_support.models import SystemLog
from bike_dispatch_platform.system_support.permissions import role_flags, role_required
from station_info.master_data import OFFICIAL_PROJECT_NAME


PROJECT_NAME = OFFICIAL_PROJECT_NAME


def _client_ip(request) -> str | None:
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR")


def _regression_metrics_for_station(station_id: int, hours: int = 48) -> dict[str, object]:
    payload = station_prediction_service.get_compare_response(station_id=station_id, hours=hours)
    actual = pd.Series(payload["actual_values"], dtype="float64")
    predicted = pd.Series(payload["predicted_values"], dtype="float64")
    if actual.empty:
        return {
            "mae": None,
            "rmse": None,
            "r2": None,
            "sample_count": 0,
            "error_score_accuracy": None,
            "smape": None,
        }

    errors = predicted - actual
    abs_errors = errors.abs()
    mae = float(abs_errors.mean())
    rmse = float((errors.pow(2).mean()) ** 0.5)
    actual_mean = float(actual.mean())
    ss_res = float(errors.pow(2).sum())
    ss_tot = float(((actual - actual_mean) ** 2).sum())
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot else 0.0

    # 更细粒度误差评分：结合相对误差、绝对误差并按样本平滑计分，不使用简单二值阈值
    denominator = ((actual.abs() + predicted.abs()) / 2.0).replace(0, 1.0)
    relative_error = (abs_errors / denominator).clip(lower=0.0)
    # 每个样本得分区间 [0, 1]，误差越小得分越高
    sample_scores = (1.0 - relative_error).clip(lower=0.0, upper=1.0)
    # 结合轻量绝对误差惩罚，避免低值样本相对误差失真
    abs_penalty = (abs_errors / (abs_errors.quantile(0.9) + 1.0)).clip(upper=1.0)
    sample_scores = (sample_scores * 0.8 + (1.0 - abs_penalty) * 0.2).clip(lower=0.0, upper=1.0)
    error_score_accuracy = float(sample_scores.mean())

    smape = float((2.0 * abs_errors / (actual.abs() + predicted.abs() + 1e-9)).mean())

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "sample_count": int(len(actual)),
        "error_score_accuracy": round(error_score_accuracy, 4),
        "smape": round(smape, 4),
    }


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问需求预测模块。")
def model_predict_view(request):
    prediction_error = None
    batch = None
    default_station_metrics = None
    try:
        batch = station_prediction_service.get_batch_response(force=False)
        stations = batch.get("stations", [])
        if stations:
            default_station_metrics = _regression_metrics_for_station(stations[0]["station_id"], hours=48)
    except FileNotFoundError as exc:
        prediction_error = str(exc)
    return render(
        request,
        "demand_prediction/model_predict.html",
        {
            "prediction_batch": batch,
            "prediction_error": prediction_error,
            "default_station_metrics": default_station_metrics,
            "project_name": PROJECT_NAME,
            "access_flags": role_flags(request.user),
        },
    )


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问需求预测模块。")
def model_compare(request):
    return redirect("demand_prediction:model_predict")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以查看预测结果。")
def predict_result_view(request):
    station_predictions = (
        StationPrediction.objects.select_related("station")
        .order_by("-batch_time", "station__ysu_id", "prediction_hour")[: 62 * 48]
    )
    return render(
        request,
        "demand_prediction/predict_result.html",
        {
            "station_predictions": station_predictions,
            "project_name": PROJECT_NAME,
            "access_flags": role_flags(request.user),
        },
    )


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以查看站点预测详情。")
def spot_forecast(request):
    prediction_error = None
    batch = None
    try:
        batch = station_prediction_service.get_batch_response(force=False)
    except FileNotFoundError as exc:
        prediction_error = str(exc)
    return render(
        request,
        "demand_prediction/spot_forecast.html",
        {
            "prediction_batch": batch,
            "prediction_error": prediction_error,
            "project_name": PROJECT_NAME,
            "access_flags": role_flags(request.user),
        },
    )


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问预测 API。")
def spot_forecast_api(request):
    try:
        payload = station_prediction_service.get_batch_response(force=False)
    except FileNotFoundError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=503)
    return JsonResponse({"success": True, **payload})


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问预测 API。")
def predict_48h_api(request):
    try:
        payload = station_prediction_service.get_batch_response(force=request.GET.get("refresh") == "1")
    except FileNotFoundError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=503)
    return JsonResponse(payload)


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问站点预测 API。")
def predict_station_api(request, station_id: int):
    station = get_object_or_404(ParkingSpot, ysu_id=station_id)
    try:
        payload = station_prediction_service.get_batch_response(force=request.GET.get("refresh") == "1")
    except FileNotFoundError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=503)

    station_payload = next((row for row in payload["stations"] if row["station_id"] == station_id), None)
    if station_payload is None:
        return JsonResponse({"success": False, "error": "Station prediction not found"}, status=404)
    station_payload["station_name"] = station.spot_name
    return JsonResponse(
        {
            "batch_time": payload["batch_time"],
            "model_version": payload["model_version"],
            "model_alias": payload.get("model_alias"),
            "metrics": payload["metrics"],
            **station_payload,
        }
    )


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问预测对比接口。")
def compare_api(request):
    try:
        station_id = int(request.GET.get("station_id", 1))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid station_id"}, status=400)
    try:
        hours = int(request.GET.get("hours", 48))
    except (TypeError, ValueError):
        hours = 48
    try:
        payload = station_prediction_service.get_compare_response(station_id=station_id, hours=hours)
    except ParkingSpot.DoesNotExist:
        return JsonResponse({"success": False, "error": "Station not found"}, status=404)
    payload["regression_metrics"] = _regression_metrics_for_station(station_id=station_id, hours=hours)
    return JsonResponse(payload)


@login_required
@role_required("admin", message="仅系统管理员可以触发模型训练。")
def manual_train(request):
    if request.method == "POST":
        root_dir = station_prediction_service.active_artifact_paths()[0].parents[3]
        active_alias = station_prediction_service.active_model_alias()
        if active_alias == "t1_state_classifier":
            script_path = root_dir / "build_t1_state_classifier.py"
        else:
            script_path = root_dir / "build_lstm_system.py"

        if not script_path.exists():
            return JsonResponse({"success": False, "error": f"Training script not found: {script_path.name}"}, status=404)

        subprocess.Popen([sys.executable, str(script_path)], cwd=str(script_path.parent))
        SystemLog.objects.create(
            user=request.user,
            action="predict",
            description=f"手动触发预测模型训练任务：{script_path.name}",
            ip_address=_client_ip(request),
        )
        messages.success(request, f"训练任务已在后台启动：{script_path.name}")
    return redirect("demand_prediction:model_predict")


@login_required
@role_required("admin", message="仅系统管理员可以下载模型文件。")
def download_model(request, model_type: str):
    if model_type != "lstm":
        return JsonResponse({"success": False, "error": "Only lstm download is supported"}, status=404)

    model_path, _, _ = station_prediction_service.active_artifact_paths()
    if not model_path.exists():
        return JsonResponse({"success": False, "error": "Model file not found"}, status=404)
    return FileResponse(open(model_path, "rb"), as_attachment=True, filename=model_path.name)


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以导出预测报告。")
def export_prediction_report(request):
    try:
        payload = station_prediction_service.get_batch_response(force=False)
    except FileNotFoundError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=503)

    rows = []
    for station in payload["stations"]:
        for hour_index, timestamp in enumerate(station["timestamps"]):
            rows.append(
                {
                    "站点编号": station["station_id"],
                    "站点名称": station["station_name"],
                    "预测时刻": timestamp,
                    "T+1决策时刻": station["decision_basis_hour"],
                    "预测净流量": station["predictions"][hour_index],
                    "预测库存": station["inventory_predictions"][hour_index],
                    "T+1状态标签": station["t_plus_1_state_label"],
                    "T+1状态区间": station["t_plus_1_state_range"],
                    "T+1状态代表值": station["t_plus_1_state_midpoint"],
                    "T+1净流量": station["t_plus_1_prediction"],
                    "T+1库存": station["t_plus_1_inventory"],
                    "T+1供需缺口": station["t_plus_1_gap"],
                    "活动模型别名": payload.get("model_alias", "unknown"),
                }
            )

    export_frame = pd.DataFrame(rows)
    export_format = resolve_export_format(request)
    SystemLog.objects.create(
        user=request.user,
        action="export",
        description=f"{request.user.username} 导出站点级 48 小时预测报告（{export_format.upper()}）",
        ip_address=_client_ip(request),
    )
    return dataframe_to_response(
        export_frame,
        filename_stem="station_prediction_report",
        export_format=export_format,
        sheet_name="prediction_report",
    )


@login_required
@role_required("admin", "predictor", message="仅系统管理员或预测人员可以访问预测产物说明。")
def get_loss_curve(request, model_type: str, date: str):
    return JsonResponse({"success": False, "error": "Loss curve is generated in the training artifacts directory"}, status=404)
