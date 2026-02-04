from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import json
import random
import csv
import os
from django.conf import settings

from operation_management.models import Vehicle, ScheduleTask, ParkingSpot
from demand_prediction.models import PredictionResult
from operation_management.services.data_sync_service import DataSyncService

# 运维管理首页
def operation_dashboard(request):
    # 固定返回空数据，确保前端显示空状态
    context = {
        'total_vehicles': 0,
        'available_vehicles': 0,
        'ridden_vehicles': 0,
        'faulty_vehicles': 0,
        'pending_tasks': 0,
        'in_progress_tasks': 0,
        'completed_tasks': 0,
        'recent_tasks': [],
        'current_time': timezone.now(),
    }
    
    return render(request, 'operation_management/dashboard.html', context)

# 供需热力图
def supply_demand_heatmap(request):
    # 固定返回空数据，确保前端显示空状态
    parking_spots_data = []
    
    # 加载我们生成的地理热力图数据
    import os
    from django.conf import settings
    geo_map_path = os.path.join(settings.BASE_DIR, 'results', 'ysu_bike_geo_distribution.html')
    geo_map_exists = os.path.exists(geo_map_path)
    
    context = {
        'parking_spots': json.dumps(parking_spots_data),
        'current_time': timezone.now().strftime('%Y-%m-%d %H:00:00'),
        'geo_map_exists': geo_map_exists,
        'geo_map_url': '/results/ysu_bike_geo_distribution.html' if geo_map_exists else ''
    }
    
    return render(request, 'operation_management/heatmap.html', context)

# 车辆监控
def vehicle_monitor(request):
    # 固定返回空数据，确保前端显示空状态
    vehicles_data = []
    
    context = {
        'vehicles': json.dumps(vehicles_data),
        'total_vehicles': 0,
        'available_vehicles': 0,
        'ridden_vehicles': 0,
        'faulty_vehicles': 0,
        'locked_vehicles': 0,
        'current_time': timezone.now(),
    }
    
    return render(request, 'operation_management/vehicle_monitor.html', context)

# 调度任务列表
def task_list(request):
    # 固定返回空数据，确保前端显示空状态
    tasks = []
    
    context = {
        'tasks': tasks,
        'pending_tasks': 0,
        'in_progress_tasks': 0,
        'completed_tasks': 0,
        'cancelled_tasks': 0,
        'current_time': timezone.now(),
    }
    
    return render(request, 'operation_management/task_list.html', context)

# 调度任务详情
def task_detail(request, task_id):
    # 固定返回空数据，确保前端显示空状态
    context = {
        'task': None,
        'current_time': timezone.now(),
    }
    
    return render(request, 'operation_management/task_detail.html', context)

# 生成测试数据
def generate_test_data(request):
    # 燕大校园边界
    yanshan_bounds = {
        'north': 39.9550,
        'south': 39.9450,
        'east': 119.5400,
        'west': 119.5250
    }
    
    # 生成停车点
    if ParkingSpot.objects.count() == 0:
        # 燕大校园内的主要区域
        areas = [
            {'name': '燕山大学南门', 'lat': 39.9450, 'lon': 119.5300},
            {'name': '燕山大学北门', 'lat': 39.9550, 'lon': 119.5300},
            {'name': '燕山大学东门', 'lat': 39.9500, 'lon': 119.5400},
            {'name': '燕山大学西门', 'lat': 39.9500, 'lon': 119.5250},
            {'name': '燕山大学图书馆', 'lat': 39.9490, 'lon': 119.5320},
            {'name': '燕山大学教学楼', 'lat': 39.9480, 'lon': 119.5330},
            {'name': '燕山大学食堂', 'lat': 39.9470, 'lon': 119.5310},
            {'name': '燕山大学宿舍区', 'lat': 39.9460, 'lon': 119.5320},
            {'name': '燕山大学体育馆', 'lat': 39.9510, 'lon': 119.5330},
            {'name': '燕山大学行政楼', 'lat': 39.9500, 'lon': 119.5310},
        ]
        
        for i, area in enumerate(areas, 1):
            # 在每个区域周围生成多个停车点
            for j in range(1, 4):
                spot_id = f'P{i:03d}{j:02d}'
                # 在区域周围随机偏移
                lat_offset = random.uniform(-0.001, 0.001)
                lon_offset = random.uniform(-0.001, 0.001)
                lat = max(yanshan_bounds['south'], min(yanshan_bounds['north'], area['lat'] + lat_offset))
                lon = max(yanshan_bounds['west'], min(yanshan_bounds['east'], area['lon'] + lon_offset))
                
                ParkingSpot.objects.create(
                    id=spot_id,
                    name=f'{area["name"]}停车点{j}',
                    latitude=round(lat, 6),
                    longitude=round(lon, 6),
                    service_radius=random.randint(50, 150)
                )
    
    # 生成车辆数据
    if Vehicle.objects.count() < 1400:
        parking_spots = ParkingSpot.objects.all()
        status_options = ['available', 'ridden', 'faulty', 'locked']
        
        for i in range(1, 1401):
            # 随机选择一个停车点，在其附近生成车辆位置
            spot = random.choice(parking_spots)
            lat_offset = random.uniform(-0.0005, 0.0005)
            lon_offset = random.uniform(-0.0005, 0.0005)
            lat = max(yanshan_bounds['south'], min(yanshan_bounds['north'], spot.latitude + lat_offset))
            lon = max(yanshan_bounds['west'], min(yanshan_bounds['east'], spot.longitude + lon_offset))
            
            # 随机生成更新时间（过去24小时内）
            update_time = timezone.now() - timedelta(hours=random.randint(0, 24), minutes=random.randint(0, 59))
            
            Vehicle.objects.create(
                id=f'B{i:04d}',
                status=random.choice(status_options),
                latitude=round(lat, 6),
                longitude=round(lon, 6),
                update_time=update_time,
                parking_spot_id=spot.id
            )
    
    # 生成预测数据
    current_time = timezone.now()
    parking_spots = ParkingSpot.objects.all()
    
    for hour in range(24):
        predict_time = current_time + timedelta(hours=hour)
        
        for spot in parking_spots:
            # 基于时间和位置生成合理的需求预测
            base_demand = random.randint(5, 20)
            
            # 考虑时间因素：上课时间需求高
            hour_of_day = predict_time.hour
            if 8 <= hour_of_day <= 12 or 14 <= hour_of_day <= 18:
                demand_multiplier = random.uniform(1.5, 2.5)
            else:
                demand_multiplier = random.uniform(0.5, 1.0)
            
            demand = int(base_demand * demand_multiplier)
            supply = random.randint(demand - 5, demand + 5)
            supply = max(0, supply)  # 确保供给不为负数
            
            # 检查是否已存在该时间的预测数据
            existing_prediction = PredictionResult.objects.filter(
                region='region1',
                predict_date=predict_time.date(),
                predict_hour=predict_time.hour
            ).first()
            
            if existing_prediction:
                # 更新现有预测数据
                existing_prediction.demand_count = demand
                existing_prediction.supply_count = supply
                existing_prediction.save()
            else:
                # 创建新的预测数据
                PredictionResult.objects.create(
                    region='region1',
                    predict_date=predict_time.date(),
                    predict_hour=predict_time.hour,
                    demand_count=demand,
                    supply_count=supply,
                    model_used='LSTM',
                    accuracy=90.0,
                    user_id=1
                )
    
    return JsonResponse({'success': True, 'message': '测试数据生成完成'})

# API接口：获取实时车辆数据
@csrf_exempt
def get_realtime_vehicle_data(request):
    if request.method == 'GET':
        # 固定返回空数组，确保前端显示空状态
        vehicles_data = []
        
        return JsonResponse({'success': True, 'data': vehicles_data, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')})
    
    return JsonResponse({'success': False, 'message': '方法不允许'})

# API接口：获取实时停车点数据
@csrf_exempt
def get_realtime_parking_data(request):
    if request.method == 'GET':
        # 固定返回空数组，确保前端显示空状态
        parking_spots_data = []
        
        return JsonResponse({'success': True, 'data': parking_spots_data, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')})
    
    return JsonResponse({'success': False, 'message': '方法不允许'})

# API接口：获取实时任务数据
@csrf_exempt
def get_realtime_task_data(request):
    if request.method == 'GET':
        # 固定返回空数组，确保前端显示空状态
        tasks_data = []
        
        return JsonResponse({'success': True, 'data': tasks_data, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')})
    
    return JsonResponse({'success': False, 'message': '方法不允许'})

# API接口：更新车辆状态
@csrf_exempt
def update_vehicle_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            vehicle_id = data.get('vehicle_id')
            new_status = data.get('status')
            
            if not vehicle_id or not new_status:
                return JsonResponse({'success': False, 'message': '缺少必要参数'})
            
            # 验证状态值
            valid_statuses = ['available', 'ridden', 'faulty', 'locked']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': '无效的状态值'})
            
            # 更新车辆状态
            vehicle = get_object_or_404(Vehicle, id=vehicle_id)
            vehicle.status = new_status
            vehicle.update_time = timezone.now()
            vehicle.save()
            
            return JsonResponse({'success': True, 'message': '车辆状态更新成功'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': '方法不允许'})

# API接口：更新任务状态
@csrf_exempt
def update_task_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            task_id = data.get('task_id')
            new_status = data.get('status')
            
            if not task_id or not new_status:
                return JsonResponse({'success': False, 'message': '缺少必要参数'})
            
            # 验证状态值
            valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': '无效的状态值'})
            
            # 更新任务状态
            task = get_object_or_404(ScheduleTask, id=task_id)
            task.status = new_status
            task.save()
            
            return JsonResponse({'success': True, 'message': '任务状态更新成功'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': '方法不允许'})

# 计算停车点车辆数
def calculate_parking_spot_vehicles():
    """计算每个停车点的车辆数量"""
    parking_spots = ParkingSpot.objects.all()
    vehicles = Vehicle.objects.filter(status='available')
    
    parking_vehicle_counts = {}
    
    for spot in parking_spots:
        count = 0
        for vehicle in vehicles:
            # 使用Haversine公式计算距离
            distance = DataSyncService.calculate_distance(
                spot.latitude, spot.longitude,
                vehicle.latitude, vehicle.longitude
            )
            if distance <= spot.service_radius:
                count += 1
        parking_vehicle_counts[spot.id] = count
    
    return parking_vehicle_counts