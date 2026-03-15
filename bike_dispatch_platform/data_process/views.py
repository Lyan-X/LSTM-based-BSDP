from __future__ import annotations

from pathlib import Path

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from bike_dispatch_platform.system_support.export_utils import dataframe_to_response, resolve_export_format
from bike_dispatch_platform.system_support.permissions import role_flags, role_required
from station_info.master_data import OFFICIAL_PROJECT_NAME

from .models import BikeRideData, WeatherData


PROJECT_NAME = OFFICIAL_PROJECT_NAME


def _get_dataset_path() -> Path:
    return Path(__file__).resolve().parents[2] / "ysu_bike_data.csv"


def _load_real_dataset() -> pd.DataFrame:
    return pd.read_csv(_get_dataset_path())


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据管理模块。")
def data_upload(request):
    messages.info(request, "当前版本已收敛为真实映射数据只读展示，不再提供上传功能。")
    return redirect("data_process:data_manage")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据管理模块。")
def weather_data_upload(request):
    messages.info(request, "当前版本已收敛为真实映射数据只读展示，不再提供天气上传功能。")
    return redirect("data_process:data_manage")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据管理模块。")
def data_list(request):
    return redirect("data_process:data_manage")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据管理模块。")
def data_manage_view(request):
    df = _load_real_dataset().copy()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        start_time = df["timestamp"].min().strftime("%Y-%m-%d %H:%M:%S")
        end_time = df["timestamp"].max().strftime("%Y-%m-%d %H:%M:%S")
    else:
        start_time = "-"
        end_time = "-"

    sample_spots = (
        df[["location_name", "longitude", "latitude"]]
        .drop_duplicates()
        .head(10)
        .to_dict("records")
        if {"location_name", "longitude", "latitude"}.issubset(df.columns)
        else []
    )

    preview_rows = df.head(20).fillna("").values.tolist()

    context = {
        "page_title": f"真实数据概览 - {PROJECT_NAME}",
        "project_name": PROJECT_NAME,
        "access_flags": role_flags(request.user),
        "dataset": {
            "file_path": str(_get_dataset_path()),
            "total_rows": int(len(df)),
            "total_spots": int(df["location_name"].nunique()) if "location_name" in df.columns else 0,
            "start_time": start_time,
            "end_time": end_time,
            "columns": list(df.columns),
            "sample_spots": sample_spots,
            "preview_rows": preview_rows,
        },
    }
    return render(request, "data_process/data_manage.html", context)


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据管理模块。")
def local_ride_entry(request):
    messages.info(request, "当前版本不再提供手动录入功能。")
    return redirect("data_process:data_manage")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据管理模块。")
def local_weather_entry(request):
    messages.info(request, "当前版本不再提供手动天气录入功能。")
    return redirect("data_process:data_manage")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以导出数据。")
def export_ride_data(request):
    df = _load_real_dataset()
    export_format = resolve_export_format(request)
    return dataframe_to_response(df.head(5000), "ysu_bike_data_export", export_format, sheet_name="ride_data")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以导出数据。")
def export_weather_data(request):
    export_format = resolve_export_format(request)
    df = pd.DataFrame([{"message": "当前精简版本未维护独立天气数据文件"}])
    return dataframe_to_response(df, "weather_data_export", export_format, sheet_name="weather_data")


@login_required
@role_required("admin", "predictor", message="仅系统管理员或数据分析员可以访问数据统计接口。")
def data_stats_api(request):
    df = _load_real_dataset()
    payload = {
        "total_rows": int(len(df)),
        "total_spots": int(df["location_name"].nunique()) if "location_name" in df.columns else 0,
        "columns": list(df.columns),
        "db_ride_count": BikeRideData.objects.count(),
        "db_weather_count": WeatherData.objects.count(),
    }
    return JsonResponse(payload)
