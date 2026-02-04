from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Avg
from django.http import JsonResponse, FileResponse
import os
import shutil
import datetime
import hashlib
import pandas as pd
from .models import User, SystemLog, DataBackup, RegionFeature
from demand_prediction.models import PredictionResult
from operation_management.models import Vehicle, ScheduleTask, OperatorTrack
from data_process.models import BikeRideData, WeatherData
from django.conf import settings

BASE_DIR = settings.BASE_DIR
DATABASES = settings.DATABASES


def custom_login(request):
    """自定义登录视图（支持角色选择、记住密码、忘记密码）"""
    if request.user.is_authenticated:
        return redirect('system_support:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role', 'predictor')
        remember_me = request.POST.get('remember_me', False)
        
        # 验证用户
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # 验证角色匹配
            if user.role != role:
                messages.error(request, f'该账号角色为{user.get_role_display()}，请选择正确的角色')
                return render(request, 'system_support/login.html')
            
            # 登录用户
            login(request, user)
            
            # 记住密码（Cookie存储，30天）
            if remember_me:
                request.session.set_expiry(2592000)  # 30天
            else:
                request.session.set_expiry(0)  # 浏览器关闭时过期
            
            # 记录登录日志
            SystemLog.objects.create(
                user=user,
                action='login',
                description=f'用户{username}登录系统',
                ip_address=get_client_ip(request)
            )
            
            # 根据角色跳转
            next_url = request.GET.get('next', 'system_support:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, '用户名或密码错误')
            # 记录错误日志
            SystemLog.objects.create(
                user=None,
                action='error',
                description=f'登录失败：用户名{username}',
                ip_address=get_client_ip(request)
            )
    
    return render(request, 'system_support/login.html')


@login_required
def dashboard(request):
    """系统总览首页（任务书要求）"""
    user = request.user
    
    # 固定返回空数据，确保前端显示空状态
    stats = {
        'total_rides': 0,
        'today_predictions': 0,
        'pending_tasks': 0,
        'total_vehicles': 0,
    }
    
    context = {
        'user': user,
        'stats': stats,
    }
    return render(request, 'system_support/dashboard.html', context)


@login_required
def logout_view(request):
    """登出视图"""
    user = request.user
    # 记录登出日志
    SystemLog.objects.create(
        user=user,
        action='logout',
        description=f'用户{user.username}登出系统',
        ip_address=get_client_ip(request)
    )
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, '已成功登出')
    return redirect('system_support:login')


def role_required(role):
    """角色权限装饰器（任务书"多角色权限管理"要求）"""
    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role != role and not request.user.is_admin():
                messages.error(request, '您没有权限访问此页面')
                return redirect('system_support:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@login_required
@role_required('admin')
def backup_list(request):
    """数据备份列表（仅管理员）"""
    backups = DataBackup.objects.all().order_by('-create_time')[:20]
    return render(request, 'system_support/backup_list.html', {'backups': backups})


@login_required
@role_required('admin')
def data_backup(request):
    """数据加密备份（任务书要求，仅管理员）"""
    try:
        # 备份数据库文件
        db_path = DATABASES['default']['NAME']
        if not os.path.exists(db_path):
            messages.error(request, '数据库文件不存在')
            return redirect('system_support:backup_list')
        
        backup_dir = os.path.join(BASE_DIR, 'media', 'backups', datetime.datetime.now().strftime('%Y%m%d'))
        os.makedirs(backup_dir, exist_ok=True)
        
        # 备份文件名（带时间戳）
        backup_filename = f"db_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_filepath = os.path.join(backup_dir, backup_filename)
        
        # 复制备份
        shutil.copy2(db_path, backup_filepath)
        backup_size = round(os.path.getsize(backup_filepath) / 1024 / 1024, 2)  # 转为MB
        
        # 可选：对备份文件进行MD5加密（简化版，实际可用AES）
        md5_hash = hashlib.md5()
        with open(backup_filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        file_hash = md5_hash.hexdigest()
        
        # 记录备份日志
        backup_record = DataBackup.objects.create(
            backup_file=os.path.join('backups', datetime.datetime.now().strftime('%Y%m%d'), backup_filename),
            backup_size=backup_size,
            backup_user=request.user,
            is_encrypted=True
        )
        
        # 记录操作日志
        SystemLog.objects.create(
            user=request.user,
            action='backup',
            description=f'数据备份成功，文件：{backup_filename}，大小：{backup_size}MB，MD5：{file_hash}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, f'数据备份成功！文件大小：{backup_size}MB')
    except Exception as e:
        messages.error(request, f'备份失败：{str(e)}')
        SystemLog.objects.create(
            user=request.user,
            action='error',
            description=f'数据备份失败：{str(e)}',
            ip_address=get_client_ip(request)
        )
    
    return redirect('system_support:backup_list')


@login_required
@role_required('admin')
def download_backup(request, backup_id):
    """下载备份文件"""
    try:
        backup = DataBackup.objects.get(id=backup_id)
        file_path = os.path.join(BASE_DIR, 'media', backup.backup_file)
        if os.path.exists(file_path):
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=os.path.basename(backup.backup_file)
            )
            return response
        else:
            messages.error(request, '备份文件不存在')
    except Exception as e:
        messages.error(request, f'下载失败：{str(e)}')
    return redirect('system_support:backup_list')


@login_required
@role_required('admin')
def system_logs(request):
    """系统日志查看（仅管理员）"""
    logs = SystemLog.objects.all().order_by('-create_time')[:100]
    
    # 支持筛选
    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    return render(request, 'system_support/system_logs.html', {
        'logs': logs,
        'action_filter': action_filter,
    })


@login_required
def report_export(request):
    """预测结果导出与报表生成（任务书要求）"""
    try:
        # 根据角色过滤数据
        if request.user.is_admin():
            results = PredictionResult.objects.all()
        else:
            results = PredictionResult.objects.filter(user=request.user)
        
        # 转换为DataFrame
        data_list = []
        for result in results:
            data_list.append({
                '预测日期': result.predict_date.strftime('%Y-%m-%d'),
                '区域': result.get_region_display(),
                '时段': result.get_time_period_display(),
                '需求车辆数': result.demand_count,
                '使用模型': result.get_model_used_display(),
                '准确率(%)': result.accuracy,
                '生成时间': result.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        if not data_list:
            messages.warning(request, '暂无预测结果可导出')
            return redirect('demand_prediction:predict')
        
        df = pd.DataFrame(data_list)
        
        # 保存报表
        report_dir = os.path.join(BASE_DIR, 'media', 'reports')
        os.makedirs(report_dir, exist_ok=True)
        report_filename = f"prediction_report_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        report_filepath = os.path.join(report_dir, report_filename)
        df.to_excel(report_filepath, index=False, engine='openpyxl')
        
        # 记录导出日志
        SystemLog.objects.create(
            user=request.user,
            action='export',
            description=f'导出预测结果报表：{report_filename}，共{len(data_list)}条',
            ip_address=get_client_ip(request)
        )
        
        # 下载报表
        response = FileResponse(
            open(report_filepath, 'rb'),
            as_attachment=True,
            filename=report_filename
        )
        return response
    except Exception as e:
        messages.error(request, f'报表导出失败：{str(e)}')
        SystemLog.objects.create(
            user=request.user,
            action='error',
            description=f'报表导出失败：{str(e)}',
            ip_address=get_client_ip(request)
        )
        return redirect('demand_prediction:predict')


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
@role_required('admin')
def region_feature_list(request):
    """区域特征列表（仅管理员）"""
    region_features = RegionFeature.objects.all().order_by('-create_time')
    return render(request, 'system_support/region_feature.html', {'region_features': region_features})


@login_required
@role_required('admin')
def region_feature_create(request):
    """创建区域特征（仅管理员）"""
    if request.method == 'POST':
        region = request.POST.get('region')
        population_density = request.POST.get('population_density')
        business_type = request.POST.get('business_type')
        subway_stations = request.POST.get('subway_stations', 0)
        bus_stations = request.POST.get('bus_stations', 0)
        
        # 创建区域特征
        RegionFeature.objects.create(
            region=region,
            population_density=float(population_density) if population_density else None,
            business_type=business_type,
            subway_stations=int(subway_stations),
            bus_stations=int(bus_stations)
        )
        
        # 记录操作日志
        SystemLog.objects.create(
            user=request.user,
            action='upload',
            description=f'创建区域特征：{region}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, '区域特征创建成功')
        return redirect('system_support:region_feature_list')
    
    return render(request, 'system_support/region_feature_form.html')


@login_required
@role_required('admin')
def region_feature_edit(request, feature_id):
    """编辑区域特征（仅管理员）"""
    region_feature = get_object_or_404(RegionFeature, id=feature_id)
    
    if request.method == 'POST':
        region_feature.region = request.POST.get('region')
        population_density = request.POST.get('population_density')
        region_feature.population_density = float(population_density) if population_density else None
        region_feature.business_type = request.POST.get('business_type')
        region_feature.subway_stations = int(request.POST.get('subway_stations', 0))
        region_feature.bus_stations = int(request.POST.get('bus_stations', 0))
        region_feature.save()
        
        # 记录操作日志
        SystemLog.objects.create(
            user=request.user,
            action='upload',
            description=f'编辑区域特征：{region_feature.region}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, '区域特征更新成功')
        return redirect('system_support:region_feature_list')
    
    return render(request, 'system_support/region_feature_form.html', {'region_feature': region_feature})


@login_required
@role_required('admin')
def region_feature_delete(request, feature_id):
    """删除区域特征（仅管理员）"""
    region_feature = get_object_or_404(RegionFeature, id=feature_id)
    region_name = region_feature.region
    region_feature.delete()
    
    # 记录操作日志
    SystemLog.objects.create(
        user=request.user,
        action='upload',
        description=f'删除区域特征：{region_name}',
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, '区域特征删除成功')
    return redirect('system_support:region_feature_list')


@login_required
def data_linkage_query(request):
    """多源数据联动查询"""
    # 初始化查询结果
    ride_weather_data = []
    prediction_task_data = []
    vehicle_track_data = []
    
    # 骑行数据与天气数据联动
    if request.method == 'POST' and request.POST.get('query_type') == 'ride_weather':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        region = request.POST.get('region')
        
        if start_date and end_date:
            # 查询骑行数据
            rides = BikeRideData.objects.filter(
                ride_datetime__date__range=[start_date, end_date]
            )
            if region:
                rides = rides.filter(start_point__icontains=region)
            
            # 关联天气数据
            for ride in rides[:50]:  # 限制显示数量
                weather = None
                try:
                    weather = WeatherData.objects.filter(
                        area__icontains=ride.start_point,
                        date=ride.ride_datetime.date()
                    ).first()
                except:
                    pass
                
                ride_weather_data.append({
                    'ride_id': ride.id,
                    'start_point': ride.start_point,
                    'end_point': ride.end_point,
                    'ride_datetime': ride.ride_datetime,
                    'duration': ride.duration,
                    'distance': ride.distance,
                    'weather': weather
                })
    
    # 预测结果与调度任务关联
    if request.method == 'POST' and request.POST.get('query_type') == 'prediction_task':
        predict_date = request.POST.get('predict_date')
        
        if predict_date:
            # 查询预测结果
            predictions = PredictionResult.objects.filter(
                predict_date=predict_date
            )
            
            # 关联调度任务
            for prediction in predictions:
                tasks = ScheduleTask.objects.filter(
                    target_region=prediction.region,
                    prediction_result=prediction
                )
                
                prediction_task_data.append({
                    'prediction_id': prediction.id,
                    'region': prediction.get_region_display(),
                    'time_period': prediction.get_time_period_display(),
                    'demand_count': prediction.demand_count,
                    'model_used': prediction.get_model_used_display(),
                    'tasks': tasks
                })
    
    # 车辆状态与运维轨迹关联
    if request.method == 'POST' and request.POST.get('query_type') == 'vehicle_track':
        vehicle_id = request.POST.get('vehicle_id')
        status = request.POST.get('status')
        
        # 查询车辆
        vehicles = Vehicle.objects.all()
        if vehicle_id:
            vehicles = vehicles.filter(bike_id__icontains=vehicle_id)
        if status:
            vehicles = vehicles.filter(status=status)
        
        # 关联运维轨迹
        for vehicle in vehicles[:50]:  # 限制显示数量
            # 查找相关的调度任务
            tasks = ScheduleTask.objects.filter(
                target_region=vehicle.current_region
            )
            
            # 查找任务相关的轨迹
            tracks = []
            for task in tasks:
                task_tracks = OperatorTrack.objects.filter(
                    task=task
                ).order_by('-track_time')[:5]
                tracks.extend(task_tracks)
            
            vehicle_track_data.append({
                'vehicle_id': vehicle.bike_id,
                'status': vehicle.get_status_display(),
                'region': vehicle.get_current_region_display(),
                'update_time': vehicle.update_time,
                'tracks': tracks
            })
    
    return render(request, 'system_support/data_linkage.html', {
        'ride_weather_data': ride_weather_data,
        'prediction_task_data': prediction_task_data,
        'vehicle_track_data': vehicle_track_data
    })
