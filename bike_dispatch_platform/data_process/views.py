from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta, datetime
from .forms import WeatherDataUploadForm, RideDataEntryForm, WeatherDataEntryForm
from .models import BikeRideData, WeatherData, DataProcessLog
from .services.data_service import data_service
import json
import csv
import logging

logger = logging.getLogger(__name__)


@login_required
def data_upload(request):
    """
    数据上传界面（任务书"公开数据集导入+本地数据录入"核心功能）
    支持Excel/CSV文件上传，自动清洗后入库
    """
    if request.method == 'POST':
        if 'data_file' not in request.FILES:
            messages.error(request, "请选择要上传的Excel/CSV文件")
            return redirect('data_process:data_upload')

        file = request.FILES['data_file']

        valid, message = data_service.validate_file(file)
        if not valid:
            messages.error(request, message)
            return redirect('data_process:data_upload')

        df, error = data_service.read_file(file)
        if error:
            messages.error(request, error)
            return redirect('data_process:data_upload')

        count, error = data_service.process_ride_data(df, request.user)
        if error:
            messages.error(request, f"处理骑行数据失败：{error}")
            return redirect('data_process:data_upload')

        # 记录数据处理日志
        DataProcessLog.objects.create(
            parking_spot_name=f"文件上传: {file.name}",
            actual_count=count,
            status='normal' if count > 0 else 'error',
            error_message=None if count > 0 else '无有效数据'
        )

        if count > 0:
            messages.success(request, f"成功导入{count}条清洗后的骑行数据")
            return redirect(f'/data/upload/?success=1&count={count}')
        else:
            messages.warning(request, "清洗后无有效数据，请检查文件内容")
            return redirect('data_process:data_upload')

    # 统计信息
    total_rides = BikeRideData.objects.count()
    user_rides = BikeRideData.objects.filter(upload_user=request.user).count()
    total_weather = WeatherData.objects.count()

    context = {
        'total_rides': total_rides,
        'user_rides': user_rides,
        'total_weather': total_weather,
    }
    return render(request, 'data_process/data_upload.html', context)


@login_required
def data_list(request):
    """
    数据仓库列表（支持筛选、分页查看）
    管理员可查看全部数据，其他用户仅查看自己上传的数据
    """
    if request.user.role == 'admin':
        queryset = BikeRideData.objects.all().order_by('-id')
    else:
        queryset = BikeRideData.objects.filter(upload_user=request.user).order_by('-id')

    # 筛选
    source_filter = request.GET.get('source', '')
    start_filter = request.GET.get('start_point', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if source_filter:
        queryset = queryset.filter(data_source__icontains=source_filter)
    if start_filter:
        queryset = queryset.filter(start_point__icontains=start_filter)
    if date_from:
        queryset = queryset.filter(ride_datetime__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(ride_datetime__date__lte=date_to)

    # 分页
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page', 1)
    data_page = paginator.get_page(page)

    context = {
        'data_list': data_page,
        'total_count': queryset.count(),
        'source_filter': source_filter,
        'start_filter': start_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'data_process/data_list.html', context)


@login_required
def weather_data_upload(request):
    """天气数据上传视图（毕设"数据上传模块"核心接口）"""
    if request.method == "POST":
        if 'weather_file' not in request.FILES:
            messages.error(request, "请选择要上传的Excel/CSV文件")
            return redirect("data_process:weather_upload")

        file = request.FILES['weather_file']

        valid, message = data_service.validate_file(file)
        if not valid:
            messages.error(request, message)
            return redirect("data_process:weather_upload")

        df, error = data_service.read_file(file)
        if error:
            messages.error(request, error)
            return redirect("data_process:weather_upload")

        count, error = data_service.process_weather_data(df)
        if error:
            messages.error(request, f"处理天气数据失败：{error}")
            return redirect("data_process:weather_upload")

        if count > 0:
            messages.success(request, f"成功导入{count}条天气数据！")
        else:
            messages.warning(request, "清洗后无有效数据，请检查文件内容")

        return redirect("data_process:weather_upload")
    else:
        form = WeatherDataUploadForm()

    weather_list = WeatherData.objects.all().order_by("-date")[:20]
    return render(
        request,
        "data_process/weather_upload.html",
        {"form": form, "weather_list": weather_list}
    )


@login_required
def data_manage_view(request):
    """
    数据管理页面视图（核心页面）
    包含数据导入、本地数据录入、天气数据、数据闭环日志、滚动窗口数据预览
    """
    # 处理文件上传（骑行数据）
    if request.method == 'POST' and 'data_file' in request.FILES:
        file = request.FILES['data_file']

        valid, message = data_service.validate_file(file)
        if not valid:
            messages.error(request, message)
            return redirect('data_process:data_manage')

        df, error = data_service.read_file(file)
        if error:
            messages.error(request, error)
            return redirect('data_process:data_manage')

        count, error = data_service.process_ride_data(df, request.user)
        if error:
            messages.error(request, f"处理骑行数据失败：{error}")
            return redirect('data_process:data_manage')

        DataProcessLog.objects.create(
            parking_spot_name=f"文件上传: {file.name}",
            actual_count=count,
            status='normal' if count > 0 else 'error',
            error_message=None if count > 0 else '无有效数据'
        )

        if count > 0:
            messages.success(request, f"成功导入{count}条清洗后的骑行数据")
        else:
            messages.warning(request, "清洗后无有效数据，请检查文件内容")

        return redirect('data_process:data_manage')

    # 处理天气数据文件上传
    if request.method == 'POST' and 'weather_file' in request.FILES:
        file = request.FILES['weather_file']

        valid, message = data_service.validate_file(file)
        if not valid:
            messages.error(request, message)
            return redirect('data_process:data_manage')

        df, error = data_service.read_file(file)
        if error:
            messages.error(request, error)
            return redirect('data_process:data_manage')

        count, error = data_service.process_weather_data(df)
        if error:
            messages.error(request, f"处理天气数据失败：{error}")
            return redirect('data_process:data_manage')

        if count > 0:
            messages.success(request, f"成功导入{count}条天气数据")
        else:
            messages.warning(request, "清洗后无有效天气数据")

        return redirect('data_process:data_manage')

    # 获取真实数据闭环日志
    logs = DataProcessLog.objects.all().order_by('-created_at')[:50]

    # 计算14天滚动窗口数据（真实数据库查询）
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=14)

    # 骑行数据统计
    total_count = BikeRideData.objects.filter(
        ride_datetime__date__gte=start_date,
        ride_datetime__date__lte=end_date
    ).count()

    # 停车点（起点）去重统计
    unique_parking_spots = BikeRideData.objects.filter(
        ride_datetime__date__gte=start_date,
        ride_datetime__date__lte=end_date
    ).values('start_point').distinct().count()

    # 准备小时骑行量数据（真实统计）
    hour_stats = BikeRideData.objects.filter(
        ride_datetime__date__gte=start_date,
        ride_datetime__date__lte=end_date
    ).extra(
        select={'hour': 'strftime("%%H", ride_datetime)'}
    ).values('hour').annotate(count=Count('id')).order_by('hour')

    hour_counts = [0] * 24
    for stat in hour_stats:
        try:
            h = int(stat['hour'])
            hour_counts[h] = stat['count']
        except (ValueError, TypeError):
            pass

    # 准备星期骑行量数据（真实统计）
    week_stats = BikeRideData.objects.filter(
        ride_datetime__date__gte=start_date,
        ride_datetime__date__lte=end_date
    ).extra(
        select={'weekday': 'strftime("%%w", ride_datetime)'}
    ).values('weekday').annotate(count=Count('id')).order_by('weekday')

    week_counts = [0] * 7
    for stat in week_stats:
        try:
            w = int(stat['weekday'])
            week_counts[w] = stat['count']
        except (ValueError, TypeError):
            pass

    # 天气数据列表
    weather_list = WeatherData.objects.all().order_by('-date')[:20]
    weather_count = WeatherData.objects.count()

    # 数据概览统计
    total_rides_all = BikeRideData.objects.count()

    # 本地数据录入表单
    ride_form = RideDataEntryForm()
    weather_form = WeatherDataEntryForm()

    context = {
        'page_title': '数据管理 - 共享单车需求预测系统',
        'logs': logs,
        'start_date': start_date,
        'end_date': end_date,
        'total_count': total_count,
        'unique_parking_spots': unique_parking_spots,
        'hour_counts': json.dumps(hour_counts),
        'week_counts': json.dumps(week_counts),
        'weather_list': weather_list,
        'weather_count': weather_count,
        'total_rides_all': total_rides_all,
        'ride_form': ride_form,
        'weather_form': weather_form,
    }
    return render(request, 'data_process/data_manage.html', context)


@login_required
def local_ride_entry(request):
    """本地骑行数据手动录入（任务书"本地数据录入"要求）"""
    if request.method == 'POST':
        form = RideDataEntryForm(request.POST)
        if form.is_valid():
            ride = form.save(commit=False)
            ride.upload_user = request.user
            ride.data_source = '本地手动录入'
            ride.status = 'cleaned'
            ride.save()

            DataProcessLog.objects.create(
                parking_spot_name=f"手动录入: {ride.start_point}->{ride.end_point}",
                actual_count=1,
                status='normal'
            )

            messages.success(request, "骑行数据录入成功！")
            return redirect('data_process:data_manage')
        else:
            messages.error(request, f"录入失败：{form.errors.as_text()}")
            return redirect('data_process:data_manage')
    return redirect('data_process:data_manage')


@login_required
def local_weather_entry(request):
    """本地天气数据手动录入"""
    if request.method == 'POST':
        form = WeatherDataEntryForm(request.POST)
        if form.is_valid():
            weather = form.save()

            DataProcessLog.objects.create(
                parking_spot_name=f"天气录入: {weather.area} {weather.date}",
                actual_count=1,
                status='normal'
            )

            messages.success(request, "天气数据录入成功！")
            return redirect('data_process:data_manage')
        else:
            messages.error(request, f"录入失败：{form.errors.as_text()}")
            return redirect('data_process:data_manage')
    return redirect('data_process:data_manage')


@login_required
def export_ride_data(request):
    """导出骑行数据为CSV（任务书"预测结果导出"要求）"""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="ride_data_export.csv"'
    response.write('\ufeff')  # BOM for Excel UTF-8

    writer = csv.writer(response)
    writer.writerow(['ID', '数据来源', '骑行起点', '骑行终点', '骑行时间',
                     '骑行时长(分钟)', '骑行距离(km)', '温度', '风速', '数据状态', '创建时间'])

    if request.user.role == 'admin':
        queryset = BikeRideData.objects.all().order_by('-ride_datetime')
    else:
        queryset = BikeRideData.objects.filter(upload_user=request.user).order_by('-ride_datetime')

    for ride in queryset[:5000]:  # 限制导出数量
        writer.writerow([
            ride.id, ride.data_source, ride.start_point, ride.end_point,
            ride.ride_datetime.strftime('%Y-%m-%d %H:%M') if ride.ride_datetime else '',
            round(ride.duration, 2), round(ride.distance, 2),
            ride.temperature, ride.wind_speed, ride.status,
            ride.create_time.strftime('%Y-%m-%d %H:%M') if ride.create_time else ''
        ])

    return response


@login_required
def export_weather_data(request):
    """导出天气数据为CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="weather_data_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['ID', '区域', '日期', '温度(℃)', '湿度(%)', '风速(m/s)', '降雨量(mm)', '天气类型'])

    for w in WeatherData.objects.all().order_by('-date')[:5000]:
        writer.writerow([
            w.id, w.area, w.date.strftime('%Y-%m-%d'),
            w.temperature, w.humidity, w.wind_speed, w.rainfall,
            w.get_weather_type_display()
        ])

    return response


@login_required
def data_stats_api(request):
    """数据统计API（用于AJAX刷新）"""
    total_rides = BikeRideData.objects.count()
    total_weather = WeatherData.objects.count()
    today_rides = BikeRideData.objects.filter(
        ride_datetime__date=timezone.now().date()
    ).count()

    # 最近7天趋势
    trend = []
    for i in range(7):
        day = timezone.now().date() - timedelta(days=i)
        count = BikeRideData.objects.filter(ride_datetime__date=day).count()
        trend.append({'date': day.strftime('%m-%d'), 'count': count})

    return JsonResponse({
        'total_rides': total_rides,
        'total_weather': total_weather,
        'today_rides': today_rides,
        'trend': list(reversed(trend)),
    })


def realtime_data_status_api(request):
    """Real-time data simulation status API (/api/real_time_data_status/)"""
    latest_log = DataProcessLog.objects.filter(
        parking_spot_name__startswith='实时模拟'
    ).order_by('-created_at').first()

    from operation_management.models import Vehicle
    return JsonResponse({
        'last_import_time': latest_log.created_at.strftime('%Y-%m-%d %H:%M:%S') if latest_log else None,
        'last_count': latest_log.actual_count if latest_log else 0,
        'total_rides': BikeRideData.objects.count(),
        'total_vehicles': Vehicle.objects.count(),
        'simulation_active': latest_log is not None,
    })