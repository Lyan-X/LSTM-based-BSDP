from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import pandas as pd
from .models import BikeRideData
from .utils import data_cleaning  # 自定义数据清洗工具（去重、缺失值填充）


@login_required
def data_upload(request):
    """数据上传界面（任务书"公开数据集导入+本地数据录入"核心功能）"""
    if request.method == 'POST':
        # 处理文件上传（Excel/CSV）
        if 'data_file' in request.FILES:
            file = request.FILES['data_file']
            if not file.name.endswith(('.xlsx', '.csv')):
                messages.error(request, "仅支持Excel（.xlsx）或CSV（.csv）格式")
                return redirect('data_process:data_upload')

            # 读取文件
            try:
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
            except Exception as e:
                messages.error(request, f"文件读取失败：{str(e)}")
                return redirect('data_process:data_upload')

            # 数据清洗（任务书"清洗、格式标准化"要求）
            cleaned_df = data_cleaning(df)

            # 批量写入数据仓库
            data_list = []
            for _, row in cleaned_df.iterrows():
                data_list.append(
                    BikeRideData(
                        data_source=request.POST.get('data_source'),
                        start_point=row.get('start_point', ''),
                        end_point=row.get('end_point', ''),
                        ride_datetime=row.get('ride_datetime'),
                        duration=row.get('duration', 0),
                        distance=row.get('distance', 0),
                        weather=row.get('weather', 'sunny'),
                        temperature=row.get('temperature', 25),
                        wind_speed=row.get('wind_speed', 0),
                        status='cleaned',
                        upload_user=request.user
                    )
                )
            BikeRideData.objects.bulk_create(data_list)
            messages.success(request, f"成功导入{len(data_list)}条清洗后的骑行数据")
            return redirect('data_process:data_list')

    return render(request, 'data_process/data_upload.html')


@login_required
def data_list(request):
    """数据仓库列表（支持筛选、查看）"""
    data = BikeRideData.objects.filter(upload_user=request.user)
    return render(request, 'data_process/data_list.html', {'data_list': data})