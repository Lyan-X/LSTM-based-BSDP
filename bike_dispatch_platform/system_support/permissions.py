from __future__ import annotations

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import render


ROLE_DISPLAY_NAMES = {
    "admin": "系统管理员",
    "predictor": "数据分析员",
    "operator": "运维调度员",
}

ROLE_PRIORITY = {
    "admin": 3,
    "predictor": 2,
    "operator": 1,
}


def is_json_request(request) -> bool:
    accept = request.headers.get("Accept", "")
    requested_with = request.headers.get("X-Requested-With", "")
    return (
        request.path.startswith("/predict/api/")
        or request.path.startswith("/operation/api/")
        or request.path.startswith("/system/api/")
        or requested_with == "XMLHttpRequest"
        or "application/json" in accept
    )


def forbidden_response(request, message: str):
    if is_json_request(request):
        return JsonResponse({"success": False, "error": message}, status=403)
    return render(
        request,
        "system_support/forbidden.html",
        {"project_name": "基于深度学习的城市共享单车调度需求预测与运维管理平台", "error_message": message},
        status=403,
    )


def role_required(*allowed_roles: str, message: str | None = None):
    allowed_roles = tuple(dict.fromkeys(allowed_roles))
    default_message = message or "当前账号无权访问该功能。"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return forbidden_response(request, "请先登录后再访问。")

            user_role = getattr(user, "role", "")
            if user.is_superuser or user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return forbidden_response(request, default_message)

        return wrapper

    return decorator


def role_flags(user) -> dict[str, bool]:
    role = getattr(user, "role", "")
    is_authenticated = getattr(user, "is_authenticated", False)
    is_admin = bool(is_authenticated and (getattr(user, "is_superuser", False) or role == "admin"))
    is_operator = bool(is_authenticated and role == "operator")
    is_predictor = bool(is_authenticated and role == "predictor")
    priority = ROLE_PRIORITY.get("admin" if is_admin else role, 0)
    return {
        "role": "admin" if is_admin else role,
        "role_priority": priority,
        "is_admin": is_admin,
        "is_operator": is_operator,
        "is_predictor": is_predictor,
        "can_view_data": is_admin or is_predictor,
        "can_view_prediction": is_admin or is_predictor,
        "can_manage_dispatch": is_admin or is_predictor or is_operator,
        "can_manage_operation_pages": is_admin or is_operator,
        "can_manage_system": is_admin,
    }
