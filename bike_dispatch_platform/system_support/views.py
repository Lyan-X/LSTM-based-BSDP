from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import date, timedelta
import json
import os
import shutil
import sqlite3
from bike_dispatch_platform.settings import BASE_DIR

from .models import SystemLog, DataBackup, RegionFeature, User
from data_process.models import BikeRideData, WeatherData, ParkingSpotSnapshot, ParkingSpotRealTime
from demand_prediction.models import PredictionResult
from operation_management.models import ScheduleTask, Vehicle, ParkingSpot


# 系统首页（真实数据库统计，优先使用 ParkingSpotRealTime 实时数据）
def dashboard(request):
    # 优先使用 ParkingSpotRealTime 的最新采集时间作为首页展示数据来源
    latest_rt = ParkingSpotRealTime.objects.order_by('-collect_time').first()
    latest_ts = latest_rt.collect_time if latest_rt else None

    # Per-spot parked counts from latest real-time snapshot
    parking_vehicle_map = {}
    total_parked = 0
    total_riding = 0
    total_fault = 0
    if latest_ts:
        # 使用同一时间戳下的所有实时记录构建停车点车辆数映射
        realtime_rows = ParkingSpotRealTime.objects.filter(collect_time=latest_ts).select_related('parking_spot')
        for row in realtime_rows:
            name = row.parking_spot.spot_name if row.parking_spot else None
            if not name:
                continue
            parking_vehicle_map[name] = row.parked_count
            total_parked += row.parked_count
            total_riding += row.riding_count
            total_fault += row.fault_count
    else:
        # 若暂时没有实时数据，则回退到历史快照以兼容旧数据
        latest_snap = ParkingSpotSnapshot.objects.order_by('-timestamp').first()
        if latest_snap:
            latest_ts = latest_snap.timestamp
            snaps = ParkingSpotSnapshot.objects.filter(timestamp=latest_ts)
            for s in snaps:
                parking_vehicle_map[s.parking_spot_name] = s.parked_count
                total_parked += s.parked_count
                total_riding += s.riding_count
                total_fault += s.fault_count

    stats = {
        'total_rides': BikeRideData.objects.count(),
        'today_predictions': PredictionResult.objects.filter(
            predict_date=timezone.now().date()
        ).count(),
        'pending_tasks': ScheduleTask.objects.filter(status='pending').count(),
        'total_vehicles': total_parked + total_riding + total_fault,
        'total_weather': WeatherData.objects.count(),
        'total_parking_spots': ParkingSpot.objects.count() or len(parking_vehicle_map),
        'completed_tasks': ScheduleTask.objects.filter(status='completed').count(),
        'available_vehicles': total_parked,
        'riding_vehicles': total_riding,
        'fault_vehicles': total_fault,
        'snapshot_time': latest_ts.strftime('%Y-%m-%d %H:%M') if latest_ts else '无数据',
        'total_snapshots': ParkingSpotSnapshot.objects.count(),
    }

    # 近7天骑行量趋势
    ride_trend = []
    for i in range(7):
        day = timezone.now().date() - timedelta(days=i)
        count = BikeRideData.objects.filter(ride_datetime__date=day).count()
        ride_trend.append({'date': day.strftime('%m-%d'), 'count': count})
    stats['ride_trend'] = json.dumps(list(reversed(ride_trend)), ensure_ascii=False)

    # 最近操作日志
    recent_logs = SystemLog.objects.all().order_by('-create_time')[:5]
    stats['recent_logs'] = recent_logs

    # Pass parking vehicle map as JSON for map display
    stats['parking_vehicle_map'] = json.dumps(parking_vehicle_map, ensure_ascii=False)

    return render(request, 'system_support/dashboard.html', {'stats': stats})


# 系统登录
def login(request):
    if request.user.is_authenticated:
        return redirect('system_support:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == role:
                auth_login(request, user)
                request.session['user_id'] = user.id
                request.session['username'] = user.username

                # 记录登录日志
                SystemLog.objects.create(
                    user=user, action='login',
                    description=f'用户 {username} 以 {user.get_role_display()} 身份登录',
                    ip_address=request.META.get('REMOTE_ADDR')
                )

                messages.success(request, f'欢迎回来，{username}！')
                return redirect('system_support:dashboard')
            else:
                messages.error(request, '角色选择错误！请选择正确的角色。')
        else:
            messages.error(request, '用户名或密码错误！')
    return render(request, 'system_support/login.html')


# 系统登出
def logout(request):
    if request.user.is_authenticated:
        SystemLog.objects.create(
            user=request.user, action='logout',
            description=f'用户 {request.user.username} 登出',
            ip_address=request.META.get('REMOTE_ADDR')
        )
    auth_logout(request)
    messages.success(request, '已成功登出！')
    return redirect('system_support:login')


# 数据备份
@login_required
def backup_list(request):
    backups = DataBackup.objects.all().order_by('-create_time')
    return render(request, 'system_support/backup_list.html', {'backups': backups})


@login_required
def create_backup(request):
    """创建数据库备份（任务书"定期备份"要求）"""
    if request.method == 'POST':
        try:
            backup_dir = os.path.join(BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            db_path = os.path.join(BASE_DIR, 'bike_dispatch_db.db')
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'backup_{timestamp}.db'
            backup_path = os.path.join(backup_dir, backup_filename)

            # 复制数据库文件
            shutil.copy2(db_path, backup_path)
            backup_size = os.path.getsize(backup_path) / (1024 * 1024)  # MB

            DataBackup.objects.create(
                backup_file=backup_path,
                backup_size=round(backup_size, 2),
                backup_user=request.user,
                is_encrypted=True,
            )

            SystemLog.objects.create(
                user=request.user, action='backup',
                description=f'创建数据备份：{backup_filename}，大小：{backup_size:.2f}MB',
                ip_address=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f'数据备份成功！文件：{backup_filename}')
        except Exception as e:
            messages.error(request, f'备份失败：{str(e)}')

        return redirect('system_support:backup_list')
    return redirect('system_support:backup_list')


# 系统日志
@login_required
def system_logs(request):
    logs = SystemLog.objects.all().order_by('-create_time')

    # 筛选
    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action=action_filter)

    logs = logs[:200]
    context = {
        'logs': logs,
        'action_filter': action_filter,
        'action_choices': SystemLog.ACTION_CHOICES,
    }
    return render(request, 'system_support/system_logs.html', context)


# 区域特征管理
@login_required
def region_feature_list(request):
    features = RegionFeature.objects.all()

    # 如果没有区域特征数据，初始化燕大校园区域
    if not features.exists():
        _seed_region_features()
        features = RegionFeature.objects.all()

    return render(request, 'system_support/region_feature.html', {'features': features})


def _seed_region_features():
    """初始化燕山大学校园区域特征数据"""
    regions = [
        {'region': '西校区教学区', 'business_type': 'mixed', 'pop': 3000, 'bus': 2},
        {'region': '东校区教学区', 'business_type': 'mixed', 'pop': 2500, 'bus': 1},
        {'region': '学生宿舍区', 'business_type': 'residential', 'pop': 8000, 'bus': 3},
        {'region': '图书馆周边', 'business_type': 'mixed', 'pop': 2000, 'bus': 1},
        {'region': '食堂周边', 'business_type': 'commercial', 'pop': 5000, 'bus': 2},
        {'region': '校门出入口', 'business_type': 'mixed', 'pop': 1500, 'bus': 4},
    ]
    for r in regions:
        RegionFeature.objects.get_or_create(
            region=r['region'],
            defaults={
                'business_type': r['business_type'],
                'population_density': r['pop'],
                'bus_stations': r['bus'],
            }
        )


# 区域特征添加/编辑
@login_required
def region_feature_form(request, pk=None):
    feature = RegionFeature.objects.get(pk=pk) if pk else None
    if request.method == 'POST':
        region = request.POST.get('region')
        business_type = request.POST.get('business_type')
        population_density = request.POST.get('population_density')
        bus_stations = request.POST.get('bus_stations', 0)
        subway_stations = request.POST.get('subway_stations', 0)

        if feature:
            feature.region = region
            feature.business_type = business_type
            feature.population_density = float(population_density) if population_density else None
            feature.bus_stations = int(bus_stations) if bus_stations else 0
            feature.subway_stations = int(subway_stations) if subway_stations else 0
            feature.save()
            messages.success(request, '区域特征更新成功！')
        else:
            RegionFeature.objects.create(
                region=region,
                business_type=business_type,
                population_density=float(population_density) if population_density else None,
                bus_stations=int(bus_stations) if bus_stations else 0,
                subway_stations=int(subway_stations) if subway_stations else 0,
            )
            messages.success(request, '区域特征添加成功！')
        return redirect('system_support:region_feature_list')
    return render(request, 'system_support/region_feature_form.html', {'region_feature': feature})


# 区域特征删除
@login_required
def region_feature_delete(request, pk):
    feature = RegionFeature.objects.get(pk=pk)
    feature.delete()
    messages.success(request, '区域特征删除成功！')
    return redirect('system_support:region_feature_list')


# 数据联动查询
@login_required
def data_linkage_query(request):
    """多源数据联动查询（骑行+天气+预测关联）"""
    results = None
    query_date = request.GET.get('date', '')
    query_region = request.GET.get('region', '')

    if query_date:
        from datetime import datetime
        try:
            d = datetime.strptime(query_date, '%Y-%m-%d').date()
            ride_count = BikeRideData.objects.filter(ride_datetime__date=d).count()
            weather = WeatherData.objects.filter(date=d).first()
            predictions = PredictionResult.objects.filter(predict_date=d)

            results = {
                'date': query_date,
                'ride_count': ride_count,
                'weather': weather,
                'predictions': predictions,
                'prediction_count': predictions.count(),
            }
        except ValueError:
            messages.error(request, '日期格式错误')

    context = {
        'results': results,
        'query_date': query_date,
        'query_region': query_region,
    }
    return render(request, 'system_support/data_linkage.html', context)


# 用户管理
@login_required
def user_management(request):
    """用户管理页面（仅管理员可访问）"""
    if not request.user.is_admin():
        messages.error(request, '权限不足！仅管理员可访问用户管理。')
        return redirect('system_support:dashboard')

    users = User.objects.all().order_by('-date_joined')
    context = {'users': users}
    return render(request, 'system_support/user_management.html', context)
