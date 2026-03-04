from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import json
import random
import os
from django.conf import settings

from operation_management.models import (
    Vehicle, ScheduleTask, ParkingSpot, ScheduleEvaluation, OperatorTrack
)
from demand_prediction.models import PredictionResult, REGION_CHOICES
from system_support.models import SystemLog, User


# ========== 使用config.py中的停车点数据初始化 ==========
def _ensure_parking_spots():
    """确保停车点数据已导入（使用config.py中预采集的经纬度数据）"""
    if ParkingSpot.objects.count() > 0:
        return
    import sys
    sys.path.insert(0, os.path.join(settings.BASE_DIR, '..'))
    try:
        from config import PARKING_SPOTS
        for idx, (name, (lon, lat)) in enumerate(PARKING_SPOTS.items(), 1):
            ParkingSpot.objects.get_or_create(
                spot_name=name,
                defaults={
                    'longitude': lon,
                    'latitude': lat,
                    'service_radius': 100,
                }
            )
    except ImportError:
        pass


def _ensure_vehicles():
    """确保有车辆数据（基于停车点生成）"""
    if Vehicle.objects.count() >= 200:
        return
    spots = list(ParkingSpot.objects.all())
    if not spots:
        return
    statuses = ['available'] * 6 + ['ridden'] * 2 + ['faulty'] * 1 + ['locked'] * 1
    for i in range(1, 521):
        spot = random.choice(spots)
        lat_off = random.uniform(-0.0003, 0.0003)
        lon_off = random.uniform(-0.0003, 0.0003)
        Vehicle.objects.get_or_create(
            id=f'B{i:04d}',
            defaults={
                'status': random.choice(statuses),
                'latitude': round(spot.latitude + lat_off, 6),
                'longitude': round(spot.longitude + lon_off, 6),
                'parking_spot': spot,
            }
        )


# 运维管理首页
@login_required
def operation_dashboard(request):
    _ensure_parking_spots()
    _ensure_vehicles()

    total_vehicles = Vehicle.objects.count()
    available = Vehicle.objects.filter(status='available').count()
    ridden = Vehicle.objects.filter(status='ridden').count()
    faulty = Vehicle.objects.filter(status='faulty').count()

    pending = ScheduleTask.objects.filter(status='pending').count()
    in_progress = ScheduleTask.objects.filter(status='in_progress').count()
    completed = ScheduleTask.objects.filter(status='completed').count()
    recent_tasks = ScheduleTask.objects.all().order_by('-create_time')[:10]

    context = {
        'total_vehicles': total_vehicles,
        'available_vehicles': available,
        'ridden_vehicles': ridden,
        'faulty_vehicles': faulty,
        'pending_tasks': pending,
        'in_progress_tasks': in_progress,
        'completed_tasks': completed,
        'recent_tasks': recent_tasks,
        'current_time': timezone.now(),
    }
    return render(request, 'operation_management/dashboard.html', context)


# 供需热力图（含30分钟预测缺口 + 调度建议）
@login_required
def supply_demand_heatmap(request):
    _ensure_parking_spots()

    # Import forecast helper from demand_prediction
    from demand_prediction.views import _compute_spot_demand

    now = timezone.now()
    target_hour = (now + timedelta(minutes=30)).hour
    weekday = (now + timedelta(minutes=30)).weekday()

    # Weather
    from data_process.models import WeatherData
    weather = WeatherData.objects.filter(date=now.date()).first()
    temp = weather.temperature if weather else 15
    wind = weather.wind_speed if weather else 2
    rain = weather.rainfall if weather else 0

    # Build per-spot data with demand-supply gap
    parking_spots_data = []
    surplus_spots = []
    deficit_spots = []

    from data_process.models import ParkingSpotRealTime
    
    for spot in ParkingSpot.objects.all():
        # Current available inventory from latest real-time data
        latest_real_time = ParkingSpotRealTime.objects.filter(
            parking_spot=spot
        ).order_by('-collect_time').first()
        supply = latest_real_time.parked_count if latest_real_time else 0
        
        # 30-min forecast demand
        demand = _compute_spot_demand(spot.spot_name, target_hour, weekday, temp, wind, rain)
        gap = demand - supply

        spot_data = {
            'name': spot.spot_name, 'lat': spot.latitude, 'lng': spot.longitude,
            'supply': supply, 'demand': demand, 'gap': gap,
        }
        parking_spots_data.append(spot_data)

        if gap >= 10:
            deficit_spots.append(spot_data)
        elif gap <= -10:
            surplus_spots.append(spot_data)

    # Generate auto-dispatch suggestions (match surplus → deficit)
    suggestions = []
    surplus_sorted = sorted(surplus_spots, key=lambda s: s['gap'])       # most surplus first (negative)
    deficit_sorted = sorted(deficit_spots, key=lambda s: s['gap'], reverse=True)  # most deficit first
    for deficit in deficit_sorted[:5]:
        if not surplus_sorted:
            break
        source = surplus_sorted[0]
        transfer = min(abs(source['gap']), deficit['gap'])
        if transfer >= 3:
            suggestions.append({
                'from': source['name'],
                'to': deficit['name'],
                'count': transfer,
                'from_surplus': abs(source['gap']),
                'to_shortage': deficit['gap'],
            })
            surplus_sorted[0] = dict(surplus_sorted[0], gap=surplus_sorted[0]['gap'] + transfer)
            if surplus_sorted[0]['gap'] >= -3:
                surplus_sorted.pop(0)

    context = {
        'parking_spots': json.dumps(parking_spots_data, ensure_ascii=False),
        'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'total_spots': len(parking_spots_data),
        'shortage_count': len(deficit_spots),
        'surplus_count': len(surplus_spots),
        'suggestions': suggestions,
        'suggestions_json': json.dumps(suggestions, ensure_ascii=False),
        'temperature': temp,
        'wind_speed': wind,
    }
    return render(request, 'operation_management/heatmap.html', context)


# 车辆监控（使用ParkingSpotRealTime数据展示每个停车点的车辆统计）
@login_required
def vehicle_monitor(request):
    _ensure_parking_spots()
    from data_process.models import ParkingSpotRealTime

    # Get latest real-time data
    latest_real_time = ParkingSpotRealTime.objects.order_by('-collect_time').first()
    latest_ts = latest_real_time.collect_time if latest_real_time else None

    spot_data_list = []
    total_parked = 0
    total_riding = 0
    total_fault = 0

    if latest_ts:
        for real_time in ParkingSpotRealTime.objects.filter(collect_time=latest_ts):
            spot_data_list.append({
                'id': real_time.parking_spot.parking_spot_id,
                'name': real_time.parking_spot.spot_name,
                'parked': real_time.parked_count,
                'riding': real_time.riding_count,
                'fault': real_time.fault_count,
            })
            total_parked += real_time.parked_count
            total_riding += real_time.riding_count
            total_fault += real_time.fault_count

    # Also build map-compatible vehicle data from real-time data
    vehicles_data = []
    spots = ParkingSpot.objects.all()
    for spot in spots:
        real_time = ParkingSpotRealTime.objects.filter(
            parking_spot=spot, collect_time=latest_ts
        ).first() if latest_ts else None
        vehicles_data.append({
            'id': spot.parking_spot_id,
            'name': spot.spot_name,
            'lat': spot.latitude,
            'lng': spot.longitude,
            'parked': real_time.parked_count if real_time else 0,
        })

    context = {
        'vehicles': json.dumps(vehicles_data, ensure_ascii=False),
        'spot_data_list': spot_data_list,
        'total_vehicles': total_parked + total_riding + total_fault,
        'available_vehicles': total_parked,
        'ridden_vehicles': total_riding,
        'faulty_vehicles': total_fault,
        'locked_vehicles': 0,
        'snapshot_time': latest_ts.strftime('%Y-%m-%d %H:%M') if latest_ts else '无数据',
        'current_time': timezone.now(),
    }
    return render(request, 'operation_management/vehicle_monitor.html', context)


# 调度任务列表
@login_required
def task_list(request):
    tasks = ScheduleTask.objects.all().order_by('-create_time')

    # 筛选
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    pending = ScheduleTask.objects.filter(status='pending').count()
    in_progress = ScheduleTask.objects.filter(status='in_progress').count()
    completed = ScheduleTask.objects.filter(status='completed').count()
    cancelled = ScheduleTask.objects.filter(status='cancelled').count()

    context = {
        'tasks': tasks[:50],
        'pending_tasks': pending,
        'in_progress_tasks': in_progress,
        'completed_tasks': completed,
        'cancelled_tasks': cancelled,
        'current_time': timezone.now(),
        'status_filter': status_filter,
    }
    return render(request, 'operation_management/task_list.html', context)


# 调度任务详情
@login_required
def task_detail(request, task_id):
    task = get_object_or_404(ScheduleTask, id=task_id)

    # 获取关联评估
    evaluation = None
    try:
        evaluation = ScheduleEvaluation.objects.get(task=task)
    except ScheduleEvaluation.DoesNotExist:
        pass

    context = {
        'task': task,
        'evaluation': evaluation,
        'current_time': timezone.now(),
    }
    return render(request, 'operation_management/task_detail.html', context)


# 创建调度任务
@login_required
def task_create(request):
    if request.method == 'POST':
        start_loc = request.POST.get('start_location', '')
        end_loc = request.POST.get('end_location', '')
        count = int(request.POST.get('dispatch_count', 0))
        priority = request.POST.get('priority', 'medium')

        if not start_loc or not end_loc or count <= 0:
            messages.error(request, '请填写完整的任务信息')
            return redirect('operation_management:task_create')

        task = ScheduleTask.objects.create(
            task_type='vehicle_dispatch',
            start_location=start_loc,
            end_location=end_loc,
            dispatch_count=count,
            priority=priority,
            status='pending',
        )

        SystemLog.objects.create(
            user=request.user, action='schedule',
            description=f'创建调度任务：{start_loc} -> {end_loc}，数量{count}',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'调度任务 #{task.id} 创建成功！')
        return redirect('operation_management:task_list')

    spots = ParkingSpot.objects.all()
    context = {'spots': spots}
    return render(request, 'operation_management/task_create.html', context)


# 自动生成调度任务（基于实时需求）
@login_required
def auto_generate_tasks(request):
    """根据实时数据自动生成调度任务"""
    from data_process.models import ParkingSpotRealTime

    # 获取最新的实时数据
    latest_real_time = ParkingSpotRealTime.objects.order_by('-collect_time').first()
    if not latest_real_time:
        messages.warning(request, '无实时数据，无法生成任务')
        return redirect('operation_management:task_list')

    # 获取所有停车点的最新实时数据
    latest_ts = latest_real_time.collect_time
    real_time_data = ParkingSpotRealTime.objects.filter(collect_time=latest_ts)

    count = 0
    spots = list(ParkingSpot.objects.all())
    if not spots:
        messages.warning(request, '无停车点数据，无法生成任务')
        return redirect('operation_management:task_list')

    for data in real_time_data:
        # 当需求量 - 停放数 ≥ 10 时生成调度任务
        gap = data.demand_count - data.parked_count
        if gap >= 10:
            # 随机选择一个起点停车点（排除当前停车点）
            available_spots = [s for s in spots if s.parking_spot_id != data.parking_spot.parking_spot_id]
            if not available_spots:
                available_spots = spots
            start_spot = random.choice(available_spots)
            
            # 创建调度任务
            ScheduleTask.objects.create(
                task_type='vehicle_dispatch',
                start_location=start_spot.spot_name,
                end_location=data.parking_spot.spot_name,
                dispatch_count=gap,
                priority='high' if gap > 15 else 'medium',
                status='pending',
                predicted_time=timezone.now(),
            )
            count += 1

    messages.success(request, f'根据实时数据自动生成{count}个调度任务')
    return redirect('operation_management:task_list')


# 调度效果评估
@login_required
def dispatch_evaluation(request):
    """调度效果评估页面"""
    total_tasks = ScheduleTask.objects.count()
    completed_tasks = ScheduleTask.objects.filter(status='completed').count()
    completion_rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0

    # 各状态统计
    status_stats = {
        'pending': ScheduleTask.objects.filter(status='pending').count(),
        'in_progress': ScheduleTask.objects.filter(status='in_progress').count(),
        'completed': completed_tasks,
        'cancelled': ScheduleTask.objects.filter(status='cancelled').count(),
    }

    # 近7天完成率趋势
    trend = []
    for i in range(7):
        day = timezone.now().date() - timedelta(days=i)
        day_total = ScheduleTask.objects.filter(create_time__date=day).count()
        day_completed = ScheduleTask.objects.filter(create_time__date=day, status='completed').count()
        rate = round(day_completed / day_total * 100, 1) if day_total > 0 else 0
        trend.append({'date': day.strftime('%m-%d'), 'rate': rate, 'total': day_total})

    evaluations = ScheduleEvaluation.objects.all().order_by('-evaluation_time')[:20]

    context = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': completion_rate,
        'status_stats': status_stats,
        'trend': json.dumps(list(reversed(trend)), ensure_ascii=False),
        'evaluations': evaluations,
    }
    return render(request, 'operation_management/dispatch_evaluation.html', context)


# 运维人员轨迹追踪
@login_required
def operator_track(request):
    """运维人员轨迹追踪页面"""
    operators = User.objects.filter(role='operator')
    selected_operator = request.GET.get('operator_id')

    tracks = []
    if selected_operator:
        tracks = OperatorTrack.objects.filter(
            operator_id=selected_operator
        ).order_by('-track_time')[:100]

    tracks_data = []
    for t in tracks:
        tracks_data.append({
            'lat': t.latitude,
            'lng': t.longitude,
            'time': t.track_time.strftime('%Y-%m-%d %H:%M'),
            'desc': t.description,
        })

    context = {
        'operators': operators,
        'selected_operator': selected_operator,
        'tracks': tracks,
        'tracks_data': json.dumps(tracks_data, ensure_ascii=False),
    }
    return render(request, 'operation_management/operator_track.html', context)


# 生成测试数据（使用config.py中的停车点数据）
@login_required
def generate_test_data(request):
    _ensure_parking_spots()
    _ensure_vehicles()

    # 生成一些调度任务
    spots = list(ParkingSpot.objects.all())
    if spots and ScheduleTask.objects.count() < 20:
        statuses = ['pending', 'in_progress', 'completed', 'completed', 'completed']
        priorities = ['high', 'medium', 'medium', 'low']
        for i in range(20):
            s1 = random.choice(spots)
            s2 = random.choice([s for s in spots if s.parking_spot_id != s1.parking_spot_id] or spots)
            ScheduleTask.objects.create(
                task_type='vehicle_dispatch',
                start_location=s1.spot_name,
                end_location=s2.spot_name,
                dispatch_count=random.randint(3, 25),
                priority=random.choice(priorities),
                status=random.choice(statuses),
            )

    return JsonResponse({'success': True, 'message': '测试数据生成完成'})


# ========== API接口 ==========

@csrf_exempt
def get_realtime_vehicle_data(request):
    if request.method == 'GET':
        vehicles_data = []
        for v in Vehicle.objects.all()[:500]:
            vehicles_data.append({
                'id': v.id, 'lat': v.latitude, 'lng': v.longitude,
                'status': v.status, 'spot': v.parking_spot.parking_spot_id if v.parking_spot else None,
            })
        return JsonResponse({
            'success': True, 'data': vehicles_data,
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse({'success': False, 'message': '方法不允许'})


@csrf_exempt
def get_realtime_parking_data(request):
    if request.method == 'GET':
        from data_process.models import ParkingSpotRealTime
        
        data = []
        for spot in ParkingSpot.objects.all():
            # 获取最新的实时数据
            latest_real_time = ParkingSpotRealTime.objects.filter(
                parking_spot=spot
            ).order_by('-collect_time').first()
            count = latest_real_time.parked_count if latest_real_time else 0
            
            data.append({
                'id': spot.parking_spot_id, 'name': spot.spot_name,
                'lat': spot.latitude, 'lng': spot.longitude,
                'count': count, 'radius': spot.service_radius,
            })
        return JsonResponse({
            'success': True, 'data': data,
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse({'success': False, 'message': '方法不允许'})


@csrf_exempt
def get_realtime_task_data(request):
    if request.method == 'GET':
        data = []
        for t in ScheduleTask.objects.all().order_by('-create_time')[:50]:
            data.append({
                'id': t.id, 'start': t.start_location, 'end': t.end_location,
                'count': t.dispatch_count, 'priority': t.priority,
                'status': t.status, 'time': t.create_time.strftime('%Y-%m-%d %H:%M'),
            })
        return JsonResponse({
            'success': True, 'data': data,
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse({'success': False, 'message': '方法不允许'})


@csrf_exempt
def update_vehicle_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            vehicle_id = data.get('vehicle_id')
            new_status = data.get('status')
            if not vehicle_id or not new_status:
                return JsonResponse({'success': False, 'message': '缺少必要参数'})
            valid_statuses = ['available', 'ridden', 'faulty', 'locked']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': '无效的状态值'})
            vehicle = get_object_or_404(Vehicle, id=vehicle_id)
            vehicle.status = new_status
            vehicle.save()
            return JsonResponse({'success': True, 'message': '车辆状态更新成功'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': '方法不允许'})


@csrf_exempt
def update_task_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            task_id = data.get('task_id')
            new_status = data.get('status')
            if not task_id or not new_status:
                return JsonResponse({'success': False, 'message': '缺少必要参数'})
            valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': '无效的状态值'})
            task = get_object_or_404(ScheduleTask, id=task_id)
            task.status = new_status
            task.save()
            return JsonResponse({'success': True, 'message': '任务状态更新成功'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': '方法不允许'})


def scheduler_status_api(request):
    """Return scheduler running status + latest real-time data stats for dashboard polling."""
    from data_process.models import ParkingSpotRealTime
    from operation_management.scheduler import _scheduler, SCHEDULER_INTERVAL_MINUTES

    running = _scheduler is not None and _scheduler.running
    jobs = []
    if running:
        for job in _scheduler.get_jobs():
            nf = job.next_run_time
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': nf.strftime('%Y-%m-%d %H:%M:%S') if nf else None,
            })

    latest = ParkingSpotRealTime.objects.order_by('-collect_time').first()
    total_rt = ParkingSpotRealTime.objects.count()

    return JsonResponse({
        'scheduler_running': running,
        'interval_minutes': SCHEDULER_INTERVAL_MINUTES,
        'jobs': jobs,
        'total_realtime_records': total_rt,
        'latest_collect_time': latest.collect_time.strftime('%Y-%m-%d %H:%M:%S') if latest else None,
        'parking_spots': ParkingSpot.objects.count(),
        'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    })
