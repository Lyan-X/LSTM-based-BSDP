from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import pandas as pd
import numpy as np
from .models import BikeRideData
from .utils import data_cleaning  # 自定义数据清洗工具（去重、缺失值填充）


@login_required
def data_upload(request):
    """
    数据上传界面（任务书"公开数据集导入+本地数据录入"核心功能）
    支持Excel/CSV文件上传，自动清洗后入库
    """
    # 处理POST请求（文件上传）
    if request.method == 'POST':
        # 1. 检查是否有文件上传
        if 'data_file' not in request.FILES:
            messages.error(request, "请选择要上传的Excel/CSV文件")
            return redirect('data_process:data_upload')
        
        file = request.FILES['data_file']
        
        # 2. 检查文件是否为空
        if file.size == 0:
            messages.error(request, "上传的文件为空，请选择有效文件")
            return redirect('data_process:data_upload')
        
        # 3. 检查文件格式
        allowed_formats = ('.xlsx', '.csv')
        if not file.name.lower().endswith(allowed_formats):
            messages.error(request, "仅支持Excel（.xlsx）或CSV（.csv）格式")
            return redirect('data_process:data_upload')

        # 4. 读取文件（增加异常捕获）
        try:
            if file.name.lower().endswith('.csv'):
                df = pd.read_csv(file, encoding='utf-8')  # 指定编码避免中文乱码
            else:
                df = pd.read_excel(file)
        except UnicodeDecodeError:
            # 兼容GBK编码的CSV文件
            try:
                df = pd.read_csv(file, encoding='gbk')
            except Exception as e:
                messages.error(request, f"文件编码错误，无法读取：{str(e)}")
                return redirect('data_process:data_upload')
        except Exception as e:
            messages.error(request, f"文件读取失败：{str(e)}")
            return redirect('data_process:data_upload')

        # 5. 数据清洗（任务书"清洗、格式标准化"要求）
        try:
            cleaned_df = data_cleaning(df)
        except Exception as e:
            messages.error(request, f"数据清洗失败：{str(e)}")
            return redirect('data_process:data_upload')

        # 6. 批量写入数据库（增加字段容错和类型转换）
        data_list = []
        # 定义必填字段和默认值，避免KeyError
        default_values = {
            'start_point': '',
            'end_point': '',
            'ride_datetime': None,
            'duration': 0.0,
            'distance': 0.0,
            'weather': 'sunny',
            'temperature': 25.0,
            'wind_speed': 0.0
        }
        
        for _, row in cleaned_df.iterrows():
            # 逐个字段取值，确保类型正确
            data_item = BikeRideData(
                # 数据来源：优先取POST参数，无则设默认值
                data_source=request.POST.get('data_source', 'upload'),
                # 骑行起点：转字符串，空值设默认
                start_point=str(row.get('start_point', default_values['start_point'])).strip(),
                # 骑行终点：转字符串，空值设默认
                end_point=str(row.get('end_point', default_values['end_point'])).strip(),
                # 骑行时间：确保是datetime类型
                ride_datetime=pd.to_datetime(row.get('ride_datetime'), errors='coerce') 
                             or default_values['ride_datetime'],
                # 骑行时长：转数值型，失败设默认
                duration=float(row.get('duration', default_values['duration'])) 
                         if pd.notna(row.get('duration')) else default_values['duration'],
                # 骑行距离：转数值型，失败设默认
                distance=float(row.get('distance', default_values['distance'])) 
                         if pd.notna(row.get('distance')) else default_values['distance'],
                # 天气：转字符串，空值设默认
                weather=str(row.get('weather', default_values['weather'])).strip(),
                # 温度：转数值型，失败设默认
                temperature=float(row.get('temperature', default_values['temperature'])) 
                             if pd.notna(row.get('temperature')) else default_values['temperature'],
                # 风速：转数值型，失败设默认
                wind_speed=float(row.get('wind_speed', default_values['wind_speed'])) 
                           if pd.notna(row.get('wind_speed')) else default_values['wind_speed'],
                # 数据状态：固定为清洗后
                status='cleaned',
                # 上传用户：关联当前登录用户
                upload_user=request.user
            )
            # 过滤掉骑行时间为空的数据（必选字段）
            if data_item.ride_datetime is not None:
                data_list.append(data_item)

        # 批量入库（避免单条插入效率低）
        if data_list:
            BikeRideData.objects.bulk_create(data_list)
            messages.success(request, f"成功导入{len(data_list)}条清洗后的骑行数据")
        else:
            messages.warning(request, "清洗后无有效数据，请检查文件内容")
        
        return redirect('data_process:data_list')

    # GET请求：返回上传页面
    return render(request, 'data_process/data_upload.html')


@login_required
def data_list(request):
    """
    数据仓库列表（支持筛选、查看）
    仅显示当前登录用户上传的数据
    """
    # 查询当前用户的骑行数据，按上传时间倒序排列
    data_list = BikeRideData.objects.filter(upload_user=request.user).order_by('-id')
    # 传递数据到模板
    context = {
        'data_list': data_list,
        'total_count': data_list.count()  # 数据总数，便于页面展示
    }
    return render(request, 'data_process/data_list.html', context)