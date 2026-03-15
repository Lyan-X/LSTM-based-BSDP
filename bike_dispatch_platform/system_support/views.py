from __future__ import annotations

import json
import shutil

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    resolve_model_selection,
    save_model_selection,
)
from bike_dispatch_platform.operation_management.services.station_service import get_runtime_settings
from bike_dispatch_platform.system_support.models import DataBackup, SystemLog
from bike_dispatch_platform.system_support.permissions import role_flags, role_required
from bike_dispatch_platform.system_support.services.dashboard_service import dashboard_service
from station_info.master_data import OFFICIAL_PROJECT_NAME


PROJECT_NAME = OFFICIAL_PROJECT_NAME
ROLE_PERMISSION_MATRIX = [
    {
        "role": "系统管理员",
        "permissions": "仪表盘、需求预测、调度监控、运维管理、系统设置、备份、日志、导出、训练触发",
    },
    {
        "role": "运维调度员",
        "permissions": "仪表盘、调度监控、手动调度、站点运维、车辆运维、工单处理、调度导出、预测结果只读查看",
    },
    {
        "role": "数据分析员",
        "permissions": "数据查看、需求预测查看、预测报告导出、仪表盘只读；无调度与系统设置权限",
    },
]


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def login(request):
    if request.user.is_authenticated:
        return redirect("system_support:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        role = request.POST.get("role", "predictor")

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "用户名或密码错误。")
            return render(request, "system_support/login.html", {"project_name": PROJECT_NAME})

        if user.role != role:
            messages.error(request, "所选角色与当前账号角色不匹配。")
            return render(request, "system_support/login.html", {"project_name": PROJECT_NAME})

        auth_login(request, user)
        SystemLog.objects.create(
            user=user,
            action="login",
            description=f"{user.username} 登录 {PROJECT_NAME}",
            ip_address=_client_ip(request),
        )
        return redirect("system_support:dashboard")

    return render(request, "system_support/login.html", {"project_name": PROJECT_NAME})


def logout(request):
    if request.user.is_authenticated:
        SystemLog.objects.create(
            user=request.user,
            action="logout",
            description=f"{request.user.username} 退出 {PROJECT_NAME}",
            ip_address=_client_ip(request),
        )
    auth_logout(request)
    messages.success(request, "已安全退出登录。")
    return redirect("system_support:login")


@login_required
@role_required("admin", "operator", "predictor", message="当前账号无权访问系统总览。")
def dashboard(request):
    context = {
        "project_name": PROJECT_NAME,
        "dashboard_payload": json.dumps(dashboard_service.build_payload(), ensure_ascii=False),
        "settings_obj": get_runtime_settings(),
        "access_flags": role_flags(request.user),
    }
    return render(request, "system_support/dashboard.html", context)


@login_required
@role_required("admin", "operator", "predictor", message="当前账号无权访问系统总览数据。")
def dashboard_api(request):
    return JsonResponse(dashboard_service.build_payload())


@login_required
@role_required("admin", message="仅系统管理员可以访问系统设置。")
def settings_view(request):
    settings_obj = get_runtime_settings()
    model_selection = resolve_model_selection()

    if request.method == "POST":
        settings_obj.dashboard_refresh_seconds = int(
            request.POST.get("dashboard_refresh_seconds", settings_obj.dashboard_refresh_seconds)
        )
        settings_obj.demand_warning_threshold = int(
            request.POST.get("demand_warning_threshold", settings_obj.demand_warning_threshold)
        )
        settings_obj.prediction_horizon_hours = int(
            request.POST.get("prediction_horizon_hours", settings_obj.prediction_horizon_hours)
        )
        settings_obj.dispatch_trigger_threshold = int(
            request.POST.get("dispatch_trigger_threshold", settings_obj.dispatch_trigger_threshold)
        )
        settings_obj.model_version = request.POST.get("model_version", settings_obj.model_version).strip() or settings_obj.model_version
        settings_obj.save()

        selected_alias = request.POST.get("active_model_alias", model_selection["active_model_alias"]).strip() or "production"
        selected_scheme_key = request.POST.get(
            "active_state_scheme_key",
            model_selection["active_state_scheme_key"],
        ).strip() or model_selection["active_state_scheme_key"]
        selection_payload = {
            "active_model_alias": selected_alias if selected_alias in model_selection["aliases"] else "production",
            "active_state_scheme_key": selected_scheme_key,
            "recommended_state_scheme_key": model_selection["recommended_state_scheme_key"],
            "aliases": model_selection["aliases"],
        }
        save_model_selection(selection_payload)

        SystemLog.objects.create(
            user=request.user,
            action="setting",
            description=f"{request.user.username} 更新 {PROJECT_NAME} 系统设置与预测模型配置",
            ip_address=_client_ip(request),
        )
        messages.success(request, "系统设置已更新。")
        return redirect("system_support:settings")

    return render(
        request,
        "system_support/settings.html",
        {
            "settings_obj": settings_obj,
            "project_name": PROJECT_NAME,
            "access_flags": role_flags(request.user),
            "role_permission_matrix": ROLE_PERMISSION_MATRIX,
            "available_prediction_models": [
                {
                    "alias": alias,
                    "description": spec.get("description", alias),
                    "selected": alias == model_selection["active_model_alias"],
                }
                for alias, spec in model_selection.get("aliases", {}).items()
            ],
            "active_prediction_model_alias": model_selection["active_model_alias"],
            "available_state_schemes": [
                {
                    **scheme,
                    "selected": scheme["scheme_key"] == model_selection["active_state_scheme_key"],
                    "recommended": scheme["scheme_key"] == model_selection["recommended_state_scheme_key"],
                }
                for scheme in model_selection["available_state_schemes"]
            ],
            "active_state_scheme_key": model_selection["active_state_scheme_key"],
            "recommended_state_scheme_key": model_selection["recommended_state_scheme_key"],
        },
    )


@login_required
@role_required("admin", message="仅系统管理员可以访问数据备份。")
def backup_list(request):
    backups = DataBackup.objects.select_related("backup_user").all().order_by("-create_time")
    return render(
        request,
        "system_support/backup_list.html",
        {"backups": backups, "project_name": PROJECT_NAME, "access_flags": role_flags(request.user)},
    )


@login_required
@role_required("admin", message="仅系统管理员可以创建数据备份。")
def create_backup(request):
    backup_dir = settings.BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    db_path = settings.BASE_DIR / "bike_dispatch_db.db"
    if not db_path.exists():
        raise Http404("数据库文件不存在。")

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{request.user.username}_{timestamp}.db"
    backup_path = backup_dir / backup_name
    shutil.copy2(db_path, backup_path)

    DataBackup.objects.create(
        backup_file=str(backup_path),
        backup_size=round(backup_path.stat().st_size / (1024 * 1024), 2),
        backup_user=request.user,
        is_encrypted=True,
    )
    SystemLog.objects.create(
        user=request.user,
        action="backup",
        description=f"{request.user.username} 创建数据库备份 {backup_name}",
        ip_address=_client_ip(request),
    )
    messages.success(request, f"数据库备份已创建：{backup_name}")
    return redirect("system_support:backup_list")


@login_required
@role_required("admin", message="仅系统管理员可以访问系统日志。")
def system_logs(request):
    logs = SystemLog.objects.select_related("user").all().order_by("-create_time")[:200]
    return render(
        request,
        "system_support/system_logs.html",
        {"logs": logs, "project_name": PROJECT_NAME, "access_flags": role_flags(request.user)},
    )
