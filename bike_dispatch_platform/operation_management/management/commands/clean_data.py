from django.core.management.base import BaseCommand
from operation_management.models import Vehicle, ScheduleTask
from demand_prediction.models import PredictionResult
from data_process.models import BikeRideData, WeatherData
from django.db.models import Q
import os
import shutil
from django.conf import settings
from django.utils import timezone

class Command(BaseCommand):
    help = '清理无效数据，删除历史测试数据和无用的旧数据文件'

    def handle(self, *args, **options):
        self.stdout.write('开始清理无效数据...')
        
        # 1. 清理数据库中的历史测试数据
        self.stdout.write('清理数据库中的历史测试数据...')
        
        # 清理超校园范围的车辆坐标
        yanshan_bounds = {
            'north': 39.9550,
            'south': 39.9450,
            'east': 119.5400,
            'west': 119.5250
        }
        out_of_bounds_count = Vehicle.objects.filter(
            Q(latitude__gt=yanshan_bounds['north']) |
            Q(latitude__lt=yanshan_bounds['south']) |
            Q(longitude__gt=yanshan_bounds['east']) |
            Q(longitude__lt=yanshan_bounds['west'])
        ).delete()[0]
        self.stdout.write(f'清理了 {out_of_bounds_count} 条超出燕大边界的车辆数据')
        
        # 清理没有坐标的车辆数据
        no_coords_count = Vehicle.objects.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True)).delete()[0]
        self.stdout.write(f'清理了 {no_coords_count} 条无坐标车辆数据')
        
        # 清理孤立数据集
        isolated_count = BikeRideData.objects.filter(data_source='test').delete()[0]
        self.stdout.write(f'清理了 {isolated_count} 条孤立测试数据')
        
        # 清理状态为invalid的数据
        invalid_count = BikeRideData.objects.filter(status='invalid').delete()[0]
        self.stdout.write(f'清理了 {invalid_count} 条无效数据')
        
        # 清理废弃的调度任务
        old_tasks_count = ScheduleTask.objects.filter(
            create_time__lt=timezone.now() - timezone.timedelta(days=30)
        ).delete()[0]
        self.stdout.write(f'清理了 {old_tasks_count} 条废弃调度任务')
        
        # 2. 删除项目中无用的旧数据文件、测试脚本
        self.stdout.write('删除项目中无用的旧数据文件、测试脚本...')
        
        # 定义要清理的目录和文件
        clean_dirs = [
            os.path.join(settings.BASE_DIR, '..', 'test_data'),
            os.path.join(settings.BASE_DIR, '..', 'old_data'),
            os.path.join(settings.BASE_DIR, '..', 'temp_data')
        ]
        
        for dir_path in clean_dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                self.stdout.write(f'删除了目录: {dir_path}')
        
        # 清理旧的测试脚本
        clean_files = [
            os.path.join(settings.BASE_DIR, '..', 'test_script.py'),
            os.path.join(settings.BASE_DIR, '..', 'old_test_data.csv'),
            os.path.join(settings.BASE_DIR, '..', 'test_data.json')
        ]
        
        for file_path in clean_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.stdout.write(f'删除了文件: {file_path}')
        
        self.stdout.write('数据清理完成！')
        self.stdout.write(f'总计清理了 {out_of_bounds_count + no_coords_count + isolated_count + invalid_count + old_tasks_count} 条无效数据')