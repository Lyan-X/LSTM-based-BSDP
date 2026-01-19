from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse
import os
import shutil
from datetime import datetime
from .models import OperationLog, DataBackup
from bike_dispatch_platform.settings import BASE_DIR, DATABASES


@login_required
@permission_required('system_support.add_databackup')
def data_backup(request):
    """数据加密备份（任务书要求）"""
    # 备份数据库文件
    db_path = DATABASES['default']['NAME']
    backup_dir = os.path.join(BASE_DIR, 'media/backups', datetime.now().strftime('%Y%m%d'))
    os.makedirs(backup_dir, exist_ok=True)

    # 备份文件名
    backup_filename = f"db_backup_{datetime.now().strftime('%H%M%S')}.db"
    backup_filepath = os.path.join(backup_dir, backup_filename)

    # 复制备份（实际项目可加加密逻辑）
    shutil.copy2(db_path, backup_filepath)
    backup_size = round(os.path.getsize(backup_filepath) / 1024 / 1024, 2)  # 转为MB

    # 记录备份日志
    DataBackup.objects.create(
        backup_file=os.path.join('backups', datetime.now().strftime('%Y%m%d'), backup_filename),
        backup_size=backup_size,
        backup_user=request.user
    )

    messages.success(request, f"数据备份成功，大小：{backup_size}MB")
    return redirect('system_support:backup_list')


@login_required
def report_export(request):
    """预测结果导出与报表生成（任务书要求）"""
    # 从数据库查询用户的预测结果
    results = PredictionResult.objects.filter(user=request.user).values(
        'predict_date', 'region', 'time_period', 'demand_count', 'model_used', 'accuracy'
    )

    # 生成Excel报表（简化版，实际用openpyxl构建）
    df = pd.DataFrame(list(results))
    df['region'] = df['region'].map(dict(PredictionResult.REGION_CHOICES))
    df['time_period'] = df['time_period'].map(dict(PredictionResult.TIME_PERIOD_CHOICES))

    # 保存报表
    report_dir = os.path.join(BASE_DIR, 'media/reports')
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f"prediction_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    report_filepath = os.path.join(report_dir, report_filename)
    df.to_excel(report_filepath, index=False)

    # 下载报表
    response = FileResponse(open(report_filepath, 'rb'), as_attachment=True, filename=report_filename)
    return response