from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
import json
from .models import Vehicle, ScheduleTask, ScheduleEvaluation, OperatorTrack
from demand_prediction.models import PredictionResult, REGION_CHOICES
from system_support.models import User
from system_support.views import role_required, get_client_ip
from system_support.models import SystemLog


@login_required
def dashboard(request):
    """运维管理首页"""
    user = request.user
    
    # 统计数据
    stats = {
        'total_vehicles': Vehicle.objects.count(),
        'normal_vehicles': Vehicle.objects.filter(status='normal').count(),
        'fault_vehicles': Vehicle.objects.filter(status='fault').count(),
        'pending_tasks': ScheduleTask.objects.filter(status='pending').count(),
        'in_progress_tasks': ScheduleTask.objects.filter(status='in_progress').count(),
    }
    
    # 根据角色过滤任务
    if user.is_operator():
        tasks = ScheduleTask.objects.filter(assign_to=user).order_by('-create_time')[:5]
    else:
        tasks = ScheduleTask.objects.all().order_by('-create_time')[:5]
    
    # 最近车辆状态
    recent_vehicles = Vehicle.objects.all().order_by('-update_time')[:10]
    
    context = {
        'stats': stats,
        'tasks': tasks,
        'recent_vehicles': recent_vehicles,
    }
    return render(request, 'operation_management/dashboard.html', context)


@login_required
def vehicle_monitor(request):
    """车辆状态实时监控（任务书核心功能）"""
    # 支持筛选
    status_filter = request.GET.get('status', '')
    region_filter = request.GET.get('region', '')
    
    vehicles = Vehicle.objects.all()
    
    if status_filter:
        vehicles = vehicles.filter(status=status_filter)
    if region_filter:
        vehicles = vehicles.filter(current_region=region_filter)
    
    # 分页
    paginator = Paginator(vehicles, 20)
    page = request.GET.get('page', 1)
    vehicles_page = paginator.get_page(page)
    
    # 统计各状态车辆数
    status_stats = Vehicle.objects.values('status').annotate(count=Count('id'))
    
    context = {
        'vehicles': vehicles_page,
        'status_filter': status_filter,
        'region_filter': region_filter,
        'status_stats': status_stats,
        'regions': REGION_CHOICES,
    }
    return render(request, 'operation_management/vehicle_monitor.html', context)


@login_required
@role_required('admin')
def vehicle_create(request):
    """创建车辆（仅管理员）"""
    if request.method == 'POST':
        bike_id = request.POST.get('bike_id')
        status = request.POST.get('status', 'normal')
        region = request.POST.get('region')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        if Vehicle.objects.filter(bike_id=bike_id).exists():
            messages.error(request, f'单车编号{bike_id}已存在')
            return redirect('operation_management:vehicle_monitor')
        
        Vehicle.objects.create(
            bike_id=bike_id,
            status=status,
            current_region=region,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
        )
        
        messages.success(request, f'车辆{bike_id}创建成功')
        return redirect('operation_management:vehicle_monitor')
    
    return render(request, 'operation_management/vehicle_create.html', {
        'regions': REGION_CHOICES,
    })


@login_required
def supply_demand_heatmap(request):
    """供需热力图动态展示（任务书核心功能）"""
    from data_process.models import BikeRideData
    import os
    import json
    from django.conf import settings
    
    # 获取日期范围（默认最近7天）
    days = int(request.GET.get('days', 7))
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=days)
    
    # 统计各区域-时段的骑行需求
    ride_data = BikeRideData.objects.filter(
        ride_datetime__date__gte=start_date,
        ride_datetime__date__lte=end_date,
        status='cleaned'
    ).extra(
        select={'hour': "strftime('%%H', ride_datetime)"}
    ).values('start_point', 'hour').annotate(
        demand=Count('id')
    )
    
    # 构建热力图数据
    regions = list(set([item['start_point'] for item in ride_data]))
    hours = [str(i).zfill(2) for i in range(24)]
    
    heatmap_data = []
    for item in ride_data:
        region_idx = regions.index(item['start_point']) if item['start_point'] in regions else 0
        hour_idx = int(item['hour'])
        heatmap_data.append([hour_idx, region_idx, item['demand']])
    
    # 查询需求预测数据
    from demand_prediction.models import PredictionResult
    prediction_data = []
    predictions = PredictionResult.objects.filter(
        predict_date=end_date
    ).order_by('predict_hour', 'region')
    
    for pred in predictions:
        prediction_data.append({
            'region': pred.get_region_display(),
            'hour': pred.predict_hour,
            'demand': pred.demand_count,
            'supply': pred.supply_count,
            'model': pred.model_used
        })
    
    # 如果没有数据，从Vehicle模型获取实际车辆数据
    if not heatmap_data:
        # 从Vehicle模型获取车辆数据
        vehicles = Vehicle.objects.all()
        
        # 如果有车辆数据，使用实际车辆数据
        if vehicles.exists():
            for vehicle in vehicles:
                if vehicle.latitude and vehicle.longitude:
                    # 根据车辆状态调整需求值
                    if vehicle.status == 'normal':
                        demand = 100
                    elif vehicle.status == 'fault':
                        demand = 50
                    else:
                        demand = 20
                    heatmap_data.append([0, 0, demand, vehicle.latitude, vehicle.longitude, vehicle.bike_id, vehicle.status])
        else:
            # 如果没有车辆数据，生成燕山大学附近的示例车辆数据
            vehicle_locations = [
                [119.5285, 39.9487, 'YS001', 'normal'],  # 燕山大学西校区南门
                [119.5280, 39.9520, 'YS002', 'normal'],  # 燕山大学西校区北门
                [119.5380, 39.9460, 'YS003', 'normal'],  # 燕山大学东校区南门
                [119.5375, 39.9490, 'YS004', 'fault'],   # 燕山大学东校区北门
                [119.5320, 39.9495, 'YS005', 'normal'],  # 燕山大学科技楼
                [119.5300, 39.9480, 'YS006', 'normal'],  # 燕山大学图书馆
                [119.5340, 39.9470, 'YS007', 'normal'],  # 燕山大学体育馆
                [119.5260, 39.9475, 'YS008', 'normal'],  # 燕山大学学生宿舍区
                [119.5250, 39.9465, 'YS009', 'normal'],  # 燕山大学商业区
                [119.5350, 39.9500, 'YS010', 'normal'],  # 燕山大学教职工区
            ]
            
            for loc in vehicle_locations:
                heatmap_data.append([0, 0, 100, loc[0], loc[1], loc[2], loc[3]])
    
    # 燕山大学测试区域坐标
    city_coords = {
        'center': [119.5320, 39.9495],  # 燕山大学中心坐标
        'zoom': 15,  # 放大级别，更清晰显示校园细节
        'bounds': {
            'north': 39.9550,  # 北边界
            'south': 39.9450,  # 南边界
            'east': 119.5400,  # 东边界
            'west': 119.5250   # 西边界
        }
    }
    
    # 燕山大学测试区域停靠点信息（精确经纬度）
    stations = [
        {'name': '燕山大学西校区南门', 'coords': [119.5285, 39.9487], 'demand': 150},
        {'name': '燕山大学西校区北门', 'coords': [119.5280, 39.9520], 'demand': 120},
        {'name': '燕山大学东校区南门', 'coords': [119.5380, 39.9460], 'demand': 100},
        {'name': '燕山大学东校区北门', 'coords': [119.5375, 39.9490], 'demand': 90},
        {'name': '燕山大学科技楼', 'coords': [119.5320, 39.9495], 'demand': 130},
        {'name': '燕山大学图书馆', 'coords': [119.5300, 39.9480], 'demand': 110},
        {'name': '燕山大学体育馆', 'coords': [119.5340, 39.9470], 'demand': 80},
        {'name': '燕山大学学生宿舍区', 'coords': [119.5260, 39.9475], 'demand': 70},
        {'name': '燕山大学商业区', 'coords': [119.5250, 39.9465], 'demand': 60},
        {'name': '燕山大学教职工区', 'coords': [119.5350, 39.9500], 'demand': 50}
    ]
    
    context = {
        'regions': json.dumps(regions),
        'hours': json.dumps(hours),
        'heatmap_data': json.dumps(heatmap_data),
        'prediction_data': json.dumps(prediction_data),
        'days': days,
        'city_coords': json.dumps(city_coords),
        'stations': json.dumps(stations)
    }
    return render(request, 'operation_management/heatmap.html', context)


@login_required
def task_list(request):
    """调度任务列表"""
    user = request.user
    
    # 根据角色过滤
    if user.is_operator():
        tasks = ScheduleTask.objects.filter(assign_to=user)
    elif user.is_admin():
        tasks = ScheduleTask.objects.all()
    else:
        tasks = ScheduleTask.objects.none()
    
    # 状态筛选
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    tasks = tasks.order_by('-create_time')
    
    # 分页
    paginator = Paginator(tasks, 15)
    page = request.GET.get('page', 1)
    tasks_page = paginator.get_page(page)
    
    context = {
        'tasks': tasks_page,
        'status_filter': status_filter,
    }
    return render(request, 'operation_management/task_list.html', context)


@login_required
@role_required('admin')
def task_create(request):
    """调度任务生成与分配（基于预测结果，仅管理员）"""
    if request.method == 'POST':
        target_region = request.POST.get('target_region')
        source_region = request.POST.get('source_region') or None
        demand_count = int(request.POST.get('demand_count', 0))
        assign_to_id = request.POST.get('assign_to')
        prediction_id = request.POST.get('prediction_id') or None
        
        # 生成唯一任务编号
        task_id = f"SCHED_{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        task = ScheduleTask.objects.create(
            task_id=task_id,
            target_region=target_region,
            source_region=source_region,
            demand_count=demand_count,
            assign_to_id=assign_to_id if assign_to_id else None,
            prediction_result_id=prediction_id,
            created_by=request.user,
            status='assigned' if assign_to_id else 'pending',
        )
        
        # 记录操作日志
        SystemLog.objects.create(
            user=request.user,
            action='schedule',
            description=f'创建调度任务：{task_id}，目标区域：{task.get_target_region_display()}，需求：{demand_count}辆',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, f'调度任务{task_id}创建成功')
        return redirect('operation_management:task_list')
    
    # 获取可用的预测结果
    predictions = PredictionResult.objects.filter(
        predict_date__gte=timezone.now().date()
    ).order_by('-create_time')[:20]
    
    # 获取运维人员
    operators = User.objects.filter(role='operator')
    
    context = {
        'predictions': predictions,
        'operators': operators,
        'regions': REGION_CHOICES,
    }
    return render(request, 'operation_management/task_create.html', context)


@login_required
def task_detail(request, task_id):
    """调度任务详情"""
    task = get_object_or_404(ScheduleTask, task_id=task_id)
    
    # 权限检查：运维人员只能查看分配给自己的任务
    if request.user.is_operator() and task.assign_to != request.user:
        messages.error(request, '您没有权限查看此任务')
        return redirect('operation_management:task_list')
    
    # 获取关联的轨迹
    tracks = OperatorTrack.objects.filter(task=task).order_by('-track_time')
    
    # 获取评估结果
    evaluation = None
    try:
        evaluation = ScheduleEvaluation.objects.get(task=task)
    except ScheduleEvaluation.DoesNotExist:
        pass
    
    context = {
        'task': task,
        'tracks': tracks,
        'evaluation': evaluation,
    }
    return render(request, 'operation_management/task_detail.html', context)


@login_required
def task_update_status(request, task_id):
    """更新任务状态（运维人员）"""
    task = get_object_or_404(ScheduleTask, task_id=task_id)
    
    # 权限检查
    if request.user.is_operator() and task.assign_to != request.user:
        return JsonResponse({'success': False, 'message': '无权限'})
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        actual_count = request.POST.get('actual_count', 0)
        
        if new_status in dict(ScheduleTask.STATUS_CHOICES).keys():
            task.status = new_status
            if actual_count:
                task.actual_count = int(actual_count)
            if new_status == 'completed':
                task.complete_time = timezone.now()
            task.save()
            
            return JsonResponse({'success': True, 'message': '状态更新成功'})
    
    return JsonResponse({'success': False, 'message': '请求错误'})


@login_required
@role_required('operator')
def operator_track(request):
    """运维人员轨迹追踪（任务书要求）"""
    if request.method == 'POST':
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        task_id = request.POST.get('task_id')
        description = request.POST.get('description', '')
        
        task = None
        if task_id:
            try:
                task = ScheduleTask.objects.get(task_id=task_id, assign_to=request.user)
            except ScheduleTask.DoesNotExist:
                pass
        
        OperatorTrack.objects.create(
            operator=request.user,
            latitude=float(latitude),
            longitude=float(longitude),
            task=task,
            description=description,
        )
        
        return JsonResponse({'success': True, 'message': '位置记录成功'})
    
    # GET请求：显示轨迹列表
    tracks = OperatorTrack.objects.filter(operator=request.user).order_by('-track_time')[:50]
    
    context = {
        'tracks': tracks,
    }
    return render(request, 'operation_management/operator_track.html', context)


@login_required
@role_required('admin')
def schedule_evaluation(request, task_id):
    """调度效果评估（任务书要求，仅管理员）"""
    task = get_object_or_404(ScheduleTask, task_id=task_id)
    
    if request.method == 'POST':
        completion_rate = float(request.POST.get('completion_rate', 0))
        time_efficiency = float(request.POST.get('time_efficiency', 0))
        cost_efficiency = request.POST.get('cost_efficiency')
        satisfaction_score = request.POST.get('satisfaction_score')
        notes = request.POST.get('notes', '')
        
        evaluation, created = ScheduleEvaluation.objects.get_or_create(
            task=task,
            defaults={
                'completion_rate': completion_rate,
                'time_efficiency': time_efficiency,
                'cost_efficiency': float(cost_efficiency) if cost_efficiency else None,
                'satisfaction_score': float(satisfaction_score) if satisfaction_score else None,
                'notes': notes,
                'evaluator': request.user,
            }
        )
        
        if not created:
            evaluation.completion_rate = completion_rate
            evaluation.time_efficiency = time_efficiency
            evaluation.cost_efficiency = float(cost_efficiency) if cost_efficiency else None
            evaluation.satisfaction_score = float(satisfaction_score) if satisfaction_score else None
            evaluation.notes = notes
            evaluation.save()
        
        messages.success(request, '评估完成')
        return redirect('operation_management:task_detail', task_id=task_id)
    
    # GET请求：显示评估表单
    evaluation = None
    try:
        evaluation = ScheduleEvaluation.objects.get(task=task)
    except ScheduleEvaluation.DoesNotExist:
        pass
    
    context = {
        'task': task,
        'evaluation': evaluation,
    }
    return render(request, 'operation_management/schedule_evaluation.html', context)
