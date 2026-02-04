import os
import sys
import django

# 获取项目根目录的绝对路径
project_root = os.path.abspath(os.path.dirname(__file__))

# 添加项目根目录到Python路径
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.bike_dispatch_platform.settings')
django.setup()

from data_process.models import BikeRideData
from operation_management.models import Vehicle, ScheduleTask, ParkingSpot
from demand_prediction.models import PredictionResult

def clear_database():
    print("===== 开始清空数据库表 =====")
    
    # 清空骑行数据表
    try:
        count = BikeRideData.objects.count()
        BikeRideData.objects.all().delete()
        print(f"清空BikeRideData表，删除 {count} 条记录")
    except Exception as e:
        print(f"清空BikeRideData表失败: {e}")
    
    # 清空车辆表
    try:
        count = Vehicle.objects.count()
        Vehicle.objects.all().delete()
        print(f"清空Vehicle表，删除 {count} 条记录")
    except Exception as e:
        print(f"清空Vehicle表失败: {e}")
    
    # 清空调度任务表
    try:
        count = ScheduleTask.objects.count()
        ScheduleTask.objects.all().delete()
        print(f"清空ScheduleTask表，删除 {count} 条记录")
    except Exception as e:
        print(f"清空ScheduleTask表失败: {e}")
    
    # 清空停车点表
    try:
        count = ParkingSpot.objects.count()
        ParkingSpot.objects.all().delete()
        print(f"清空ParkingSpot表，删除 {count} 条记录")
    except Exception as e:
        print(f"清空ParkingSpot表失败: {e}")
    
    # 清空预测结果表
    try:
        count = PredictionResult.objects.count()
        PredictionResult.objects.all().delete()
        print(f"清空PredictionResult表，删除 {count} 条记录")
    except Exception as e:
        print(f"清空PredictionResult表失败: {e}")
    
    print("===== 数据库表清空完成 =====")

if __name__ == "__main__":
    clear_database()