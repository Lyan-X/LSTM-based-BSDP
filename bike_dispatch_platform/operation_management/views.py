from __future__ import annotations

import json
from urllib.parse import urlencode

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from bike_dispatch_platform.operation_management.models import ParkingSpot, ScheduleTask, Vehicle
from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service
from bike_dispatch_platform.operation_management.services.station_service import get_runtime_settings, sync_parking_spots
from bike_dispatch_platform.operation_management.services.vehicle_service import (
    build_vehicle_queryset,
    build_vehicle_stats,
    create_manual_dispatch_task,
    create_vehicle_fault_task,
    create_vehicle_work_order,
    ensure_vehicle_registry,
    get_vehicle_history,
    latest_ride_records,
    normalize_vehicle_status,
    paginate_vehicle_queryset,
    vehicle_status_label,
)
from bike_dispatch_platform.system_support.export_utils import dataframe_to_response, resolve_export_format
from bike_dispatch_platform.system_support.models import SystemLog
from bike_dispatch_platform.system_support.permissions import role_flags, role_required
from station_info.master_data import OFFICIAL_PROJECT_NAME


PROJECT_NAME = OFFICIAL_PROJECT_NAME


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _vehicle_query_string(request) -> str:
    query = {}
    for key in ("station_id", "status", "page"):
        value = request.GET.get(key, "").strip()
        if value:
            query[key] = value
    return urlencode(query)


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问调度监控。")
def supply_demand_heatmap(request):
    sync_parking_spots()
    snapshot = runtime_service.ensure_snapshot()
    context = {
        "project_name": PROJECT_NAME,
        "snapshot_payload": json.dumps(
            {
                "generated_at": snapshot.bucket_time.isoformat(),
                "data": snapshot.station_rows,
                "suggestions": snapshot.dispatch_suggestions,
                "metrics": snapshot.metrics,
            },
            ensure_ascii=False,
        ),
        "settings_obj": get_runtime_settings(),
        "access_flags": role_flags(request.user),
    }
    return render(request, "operation_management/heatmap.html", context)


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问调度监控实时数据。")
def get_realtime_parking_data(request):
    snapshot = runtime_service.ensure_snapshot()
    return JsonResponse(
        {
            "success": True,
            "current_time": snapshot.bucket_time.isoformat(),
            "data": snapshot.station_rows,
            "suggestions": snapshot.dispatch_suggestions,
            "metrics": snapshot.metrics,
        }
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问调度任务列表。")
def task_list(request):
    snapshot = runtime_service.ensure_snapshot()
    runtime_service.create_schedule_tasks(snapshot)
    tasks = ScheduleTask.objects.select_related("from_station", "to_station", "related_vehicle").order_by("-create_time")
    return render(
        request,
        "operation_management/task_list.html",
        {
            "project_name": PROJECT_NAME,
            "tasks": tasks,
            "parking_spots": ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"),
            "pending_tasks": tasks.filter(status="pending").count(),
            "in_progress_tasks": tasks.filter(status="in_progress").count(),
            "completed_tasks": tasks.filter(status="completed").count(),
            "cancelled_tasks": tasks.filter(status="cancelled").count(),
            "current_time": timezone.now(),
            "access_flags": role_flags(request.user),
        },
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以查看调度任务详情。")
def task_detail(request, task_id: int):
    task = get_object_or_404(
        ScheduleTask.objects.select_related("from_station", "to_station", "related_vehicle"),
        pk=task_id,
    )
    return render(
        request,
        "operation_management/task_detail.html",
        {"project_name": PROJECT_NAME, "task": task, "access_flags": role_flags(request.user)},
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以生成调度任务。")
def auto_generate_tasks(request):
    snapshot = runtime_service.ensure_snapshot()
    created_tasks = runtime_service.create_schedule_tasks(snapshot)
    SystemLog.objects.create(
        user=request.user,
        action="schedule",
        description=f"{request.user.username} 在 {PROJECT_NAME} 中生成 {len(created_tasks)} 条 T+1 预测驱动调度任务",
        ip_address=_client_ip(request),
    )
    messages.success(request, f"已生成 {len(created_tasks)} 条调度任务。")
    return redirect("operation_management:task_list")


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以创建手动调度任务。")
def manual_dispatch_create(request):
    if request.method != "POST":
        return redirect("operation_management:task_list")

    try:
        task = create_manual_dispatch_task(
            from_station_id=int(request.POST.get("from_station_id", "0")),
            to_station_id=int(request.POST.get("to_station_id", "0")),
            dispatch_count=int(request.POST.get("dispatch_count", "0")),
            operator_name=request.user.username,
            reason=request.POST.get("reason", ""),
        )
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("operation_management:task_list")

    SystemLog.objects.create(
        user=request.user,
        action="schedule",
        description=f"{request.user.username} 创建人工调度任务 #{task.id}",
        ip_address=_client_ip(request),
    )
    messages.success(request, f"人工调度任务 #{task.id} 已创建。")
    return redirect("operation_management:task_list")


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问调度实时任务数据。")
def get_realtime_task_data(request):
    snapshot = runtime_service.ensure_snapshot()
    runtime_service.create_schedule_tasks(snapshot)
    tasks = ScheduleTask.objects.select_related("from_station", "to_station", "related_vehicle").order_by("-create_time")[:20]
    payload = [
        {
            "id": task.id,
            "from": task.start_location,
            "to": task.end_location,
            "start_location": task.start_location,
            "end_location": task.end_location,
            "count": task.dispatch_count,
            "dispatch_count": task.dispatch_count,
            "status": task.status,
            "priority": task.priority,
            "predicted_gap": task.predicted_gap,
            "distance_cost": task.distance_cost,
            "reason": task.reason,
            "related_vehicle_id": task.related_vehicle_id or "",
            "predicted_time": task.predicted_time.isoformat() if task.predicted_time else "",
            "created_at": task.create_time.isoformat(),
        }
        for task in tasks
    ]
    return JsonResponse(
        {
            "success": True,
            "current_time": timezone.now().isoformat(),
            "tasks": payload,
            "data": payload,
        }
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以更新调度任务状态。")
def update_task_status(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    if request.content_type and "application/json" in request.content_type:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        task_id = payload.get("task_id")
        new_status = payload.get("status")
    else:
        task_id = request.POST.get("task_id")
        new_status = request.POST.get("status")

    task = get_object_or_404(ScheduleTask, pk=task_id)
    new_status = new_status or task.status
    if new_status not in dict(ScheduleTask.STATUS_CHOICES):
        return JsonResponse({"success": False, "error": "Invalid status"}, status=400)

    task.status = new_status
    task.save(update_fields=["status"])
    return JsonResponse({"success": True, "status": task.status})


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问运维管理页面。")
def station_list(request):
    sync_parking_spots()
    latest_snapshot = runtime_service.ensure_snapshot()
    snapshot_map = {row["station_id"]: row for row in latest_snapshot.station_rows}
    stations = []
    for station in ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"):
        runtime_row = snapshot_map.get(station.ysu_id, {})
        stations.append({"station": station, "runtime": runtime_row})
    return render(
        request,
        "operation_management/station_list.html",
        {
            "project_name": PROJECT_NAME,
            "stations": stations,
            "vehicle_stats": build_vehicle_stats(),
            "settings_obj": get_runtime_settings(),
            "access_flags": role_flags(request.user),
        },
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问运维管理实时数据。")
def station_runtime_api(request):
    snapshot = runtime_service.ensure_snapshot()
    snapshot_map = {row["station_id"]: row for row in snapshot.station_rows}
    rows = []
    for station in ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"):
        runtime_row = snapshot_map.get(station.ysu_id, {})
        rows.append(
            {
                "station_id": station.ysu_id,
                "station_name": station.spot_name,
                "count": runtime_row.get("count", station.initial_inventory),
                "target_inventory": runtime_row.get("target_inventory", round((station.low_warning_threshold + station.high_warning_threshold) / 2.0, 2)),
                "low_warning_threshold": station.low_warning_threshold,
                "high_warning_threshold": station.high_warning_threshold,
                "is_active": station.is_active,
                "demand": runtime_row.get("demand", 0),
                "gap": runtime_row.get("gap", 0),
                "t_plus_1_gap": runtime_row.get("t_plus_1_gap", 0),
                "t_plus_1_net_flow": runtime_row.get("t_plus_1_net_flow", 0),
                "current_state_label": runtime_row.get("current_state_label", "--"),
                "t_plus_1_state_label": runtime_row.get("t_plus_1_state_label", "--"),
            }
        )
    return JsonResponse(
        {
            "success": True,
            "generated_at": snapshot.bucket_time.isoformat(),
            "refresh_seconds": snapshot.metrics.get("refresh_seconds", get_runtime_settings().dashboard_refresh_seconds),
            "rows": rows,
        }
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以编辑站点运维字段。")
def station_edit(request, station_id: int):
    station = get_object_or_404(ParkingSpot, ysu_id=station_id)
    if request.method == "POST":
        station.low_warning_threshold = int(request.POST.get("low_warning_threshold", station.low_warning_threshold))
        station.high_warning_threshold = int(request.POST.get("high_warning_threshold", station.high_warning_threshold))
        station.notes = request.POST.get("notes", station.notes)
        station.is_active = "is_active" in request.POST
        station.save(update_fields=["low_warning_threshold", "high_warning_threshold", "notes", "is_active"])
        SystemLog.objects.create(
            user=request.user,
            action="setting",
            description=f"{request.user.username} 更新站点 {station.spot_name} 运维字段",
            ip_address=_client_ip(request),
        )
        messages.success(request, f"站点 {station.spot_name} 的运维字段已更新。")
        return redirect("operation_management:station_list")

    return render(
        request,
        "operation_management/station_edit.html",
        {"project_name": PROJECT_NAME, "station": station, "access_flags": role_flags(request.user)},
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以导出站点历史数据。")
def station_history_export(request, station_id: int):
    from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service

    station = get_object_or_404(ParkingSpot, ysu_id=station_id)
    dataset = station_prediction_service.dataset
    station_frame = dataset[dataset["ysu_id"] == station_id].copy()

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    if start_date:
        station_frame = station_frame[station_frame["hour"] >= start_date]
    if end_date:
        station_frame = station_frame[station_frame["hour"] <= f"{end_date} 23:59:59"]

    export_frame = pd.DataFrame(
        {
            "站点编号": station_frame["ysu_id"],
            "站点名称": station_frame["ysu_name"] if "ysu_name" in station_frame.columns else station.spot_name,
            "时间": station_frame["hour"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "流入量": station_frame["inflow"],
            "流出量": station_frame["outflow"],
            "净流量": station_frame["net_flow"],
            "站点库存": station_frame["inventory"],
            "最大容量": station_frame["max_capacity"],
            "节假日": station_frame["is_holiday"] if "is_holiday" in station_frame.columns else 0,
        }
    )
    export_format = resolve_export_format(request)
    SystemLog.objects.create(
        user=request.user,
        action="export",
        description=f"{request.user.username} 导出站点 {station.spot_name} 历史数据（{export_format.upper()}）",
        ip_address=_client_ip(request),
    )
    return dataframe_to_response(
        export_frame,
        filename_stem=f"station_{station_id}_history",
        export_format=export_format,
        sheet_name="station_history",
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以创建运维工单。")
def create_work_order(request, station_id: int):
    station = get_object_or_404(ParkingSpot, ysu_id=station_id)
    task = ScheduleTask.objects.create(
        task_type="operation_work_order",
        start_location=station.spot_name,
        end_location=station.spot_name,
        dispatch_count=0,
        priority="medium",
        status="pending",
        predicted_time=timezone.now(),
        reason=f"站点 {station.spot_name} 触发运维工单。",
    )
    messages.success(request, f"已为站点 {station.spot_name} 创建工单 #{task.id}。")
    return redirect("operation_management:task_detail", task_id=task.id)


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问车辆运维页面。")
def vehicle_management(request):
    ensure_vehicle_registry()
    next_query = _vehicle_query_string(request)

    if request.method == "POST":
        vehicle = get_object_or_404(Vehicle.objects.select_related("parking_spot"), pk=request.POST.get("vehicle_id"))
        action = request.POST.get("action")
        description = request.POST.get("description", "").strip()

        if action == "report_fault":
            fault_task = create_vehicle_fault_task(vehicle, description, request.user.username)
            work_order = create_vehicle_work_order(vehicle, description or "故障待维修处理", request.user.username)
            messages.success(
                request,
                f"车辆 {vehicle.id} 已标记为故障待维修，并生成故障记录 #{fault_task.id} 与工单 #{work_order.id}。",
            )
        elif action == "create_work_order":
            work_order = create_vehicle_work_order(vehicle, description, request.user.username)
            messages.success(request, f"车辆 {vehicle.id} 运维工单 #{work_order.id} 已创建。")

        target_url = "operation_management:vehicle_management"
        if next_query:
            return redirect(f"{redirect(target_url).url}?{next_query}")
        return redirect(target_url)

    station_filter = request.GET.get("station_id", "").strip()
    status_filter = request.GET.get("status", "").strip()
    page_number = request.GET.get("page", "1")

    vehicle_queryset = build_vehicle_queryset(station_filter=station_filter, status_filter=status_filter)
    vehicles_page = paginate_vehicle_queryset(vehicle_queryset, page_number=page_number, per_page=1200)
    for vehicle in vehicles_page.object_list:
        normalized = normalize_vehicle_status(vehicle.status)
        vehicle.normalized_status = normalized
        vehicle.normalized_status_label = vehicle_status_label(normalized)
    work_orders = ScheduleTask.objects.filter(
        task_type__in=["vehicle_fault_report", "maintenance_work_order", "operation_work_order"]
    ).select_related("related_vehicle").order_by("-create_time")[:100]

    return render(
        request,
        "operation_management/vehicle_management.html",
        {
            "project_name": PROJECT_NAME,
            "vehicles_page": vehicles_page,
            "station_filter": station_filter,
            "status_filter": status_filter,
            "stations": ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"),
            "work_orders": work_orders,
            "vehicle_stats": build_vehicle_stats(),
            "settings_obj": get_runtime_settings(),
            "access_flags": role_flags(request.user),
            "current_query": next_query,
        },
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问车辆运维实时数据。")
def vehicle_runtime_api(request):
    station_filter = request.GET.get("station_id", "").strip()
    status_filter = request.GET.get("status", "").strip()
    page_number = request.GET.get("page", "1")

    ensure_vehicle_registry()
    vehicle_queryset = build_vehicle_queryset(station_filter=station_filter, status_filter=status_filter)
    vehicles_page = paginate_vehicle_queryset(vehicle_queryset, page_number=page_number, per_page=1200)
    rows = []
    for vehicle in vehicles_page.object_list:
        normalized = normalize_vehicle_status(vehicle.status)
        rows.append(
            {
                "id": vehicle.id,
                "status": normalized,
                "status_label": vehicle_status_label(normalized),
                "station_name": vehicle.parking_spot.spot_name if vehicle.parking_spot else "-",
                "updated_at": vehicle.update_time.strftime("%Y-%m-%d %H:%M:%S"),
                "detail_url": f"/operation/vehicles/{vehicle.id}/?station_id={station_filter}&status={status_filter}&page={vehicles_page.number}",
            }
        )

    work_orders = ScheduleTask.objects.filter(
        task_type__in=["vehicle_fault_report", "maintenance_work_order", "operation_work_order"]
    ).select_related("related_vehicle").order_by("-create_time")[:20]
    work_order_rows = [
        {
            "id": task.id,
            "task_type": task.task_type,
            "related_vehicle_id": task.related_vehicle_id or "-",
            "status": task.get_status_display(),
            "created_at": task.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for task in work_orders
    ]

    snapshot = runtime_service.ensure_snapshot()
    return JsonResponse(
        {
            "success": True,
            "generated_at": snapshot.bucket_time.isoformat(),
            "refresh_seconds": snapshot.metrics.get("refresh_seconds", get_runtime_settings().dashboard_refresh_seconds),
            "stats": build_vehicle_stats(),
            "rows": rows,
            "work_orders": work_order_rows,
            "pagination": {
                "page": vehicles_page.number,
                "num_pages": vehicles_page.paginator.num_pages,
                "count": vehicles_page.paginator.count,
                "has_previous": vehicles_page.has_previous(),
                "has_next": vehicles_page.has_next(),
                "previous_page_number": vehicles_page.previous_page_number() if vehicles_page.has_previous() else None,
                "next_page_number": vehicles_page.next_page_number() if vehicles_page.has_next() else None,
            },
        }
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以访问车辆详情。")
def vehicle_detail(request, vehicle_id: str):
    ensure_vehicle_registry()
    vehicle = get_object_or_404(Vehicle.objects.select_related("parking_spot"), pk=vehicle_id)
    history_rows = get_vehicle_history(vehicle, limit=10)

    if request.method == "POST":
        action = request.POST.get("action")
        description = request.POST.get("description", "").strip()
        if action == "report_fault":
            fault_task = create_vehicle_fault_task(vehicle, description, request.user.username)
            work_order = create_vehicle_work_order(vehicle, description or "故障待维修处理", request.user.username)
            messages.success(
                request,
                f"车辆 {vehicle.id} 已标记为故障待维修，并生成故障记录 #{fault_task.id} 与工单 #{work_order.id}。",
            )
        elif action == "create_work_order":
            work_order = create_vehicle_work_order(vehicle, description, request.user.username)
            messages.success(request, f"车辆 {vehicle.id} 运维工单 #{work_order.id} 已创建。")
        return redirect("operation_management:vehicle_detail", vehicle_id=vehicle.id)

    return render(
        request,
        "operation_management/vehicle_detail.html",
        {
            "project_name": PROJECT_NAME,
            "vehicle": vehicle,
            "history_rows": history_rows,
            "normalized_status": vehicle_status_label(normalize_vehicle_status(vehicle.status)),
            "back_query": _vehicle_query_string(request),
            "access_flags": role_flags(request.user),
        },
    )


@login_required
@role_required("admin", "operator", message="仅系统管理员或运维调度员可以导出调度记录。")
def task_export(request):
    tasks = ScheduleTask.objects.select_related("from_station", "to_station", "related_vehicle").order_by("-create_time")
    export_frame = pd.DataFrame(
        [
            {
                "任务编号": task.id,
                "任务类型": task.task_type,
                "调出站点": task.from_station.spot_name if task.from_station else task.start_location,
                "调入站点": task.to_station.spot_name if task.to_station else task.end_location,
                "关联车辆ID": task.related_vehicle_id or "",
                "调运量": task.dispatch_count,
                "优先级": task.get_priority_display(),
                "状态": task.get_status_display(),
                "T+1预测缺口": task.predicted_gap,
                "距离成本": task.distance_cost,
                "预测批次时间": task.prediction_batch_time.strftime("%Y-%m-%d %H:%M:%S")
                if task.prediction_batch_time
                else "",
                "预测时刻": task.predicted_time.strftime("%Y-%m-%d %H:%M:%S") if task.predicted_time else "",
                "创建时间": task.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "触发原因": task.reason,
            }
            for task in tasks
        ]
    )
    export_format = resolve_export_format(request)
    SystemLog.objects.create(
        user=request.user,
        action="export",
        description=f"{request.user.username} 导出调度记录（{export_format.upper()}）",
        ip_address=_client_ip(request),
    )
    return dataframe_to_response(
        export_frame,
        filename_stem=f"dispatch_records_{timezone.now():%Y%m%d_%H%M%S}",
        export_format=export_format,
        sheet_name="dispatch_records",
    )
