from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.utils import timezone
import logging

from data_process.models import ParkingSpotRealTime, ParkingSpot
import random
from datetime import datetime, time

logger = logging.getLogger(__name__)

# 创建调度器实例
scheduler = BackgroundScheduler()

def generate_real_time_data():
    """生成实时停车点数据"""
    try:
        current_time = timezone.now()
        parking_spots = ParkingSpot.objects.all()
        
        # 确定当前是否为高峰时段
        current_hour = current_time.hour
        current_minute = current_time.minute
        is_peak_hour = False
        
        # 高峰时段：7:00-9:00、11:30-13:00、17:00-19:00
        if (
            (7 <= current_hour < 9) or
            (current_hour == 11 and current_minute >= 30) or
            (current_hour == 12) or
            (current_hour == 13 and current_minute < 0) or
            (17 <= current_hour < 19)
        ):
            is_peak_hour = True
        
        # 批量创建实时数据
        real_time_data = []
        for spot in parking_spots:
            # 基础车辆数
            base_count = random.randint(10, 30)
            
            # 根据停车点类型和时段调整数据
            if is_peak_hour:
                if spot.spot_type == '教学楼' or spot.spot_type == '食堂':
                    # 高峰时段：需求量比停放数高 5-15
                    parked_count = base_count
                    demand_count = parked_count + random.randint(5, 15)
                else:
                    # 其他停车点：需求量与停放数基本持平
                    parked_count = base_count
                    demand_count = parked_count + random.randint(-2, 2)
            else:
                # 非高峰时段：需求量与停放数基本持平
                parked_count = base_count
                demand_count = parked_count + random.randint(-2, 2)
            
            # 骑行中车辆数：随机 5-15
            riding_count = random.randint(5, 15)
            
            # 故障车辆数：每个停车点随机 1-3 辆
            fault_count = random.randint(1, 3)
            
            # 创建实时数据对象
            real_time = ParkingSpotRealTime(
                parking_spot=spot,
                collect_time=current_time,
                parked_count=parked_count,
                riding_count=riding_count,
                fault_count=fault_count,
                demand_count=demand_count
            )
            real_time_data.append(real_time)
        
        # 批量保存数据
        ParkingSpotRealTime.objects.bulk_create(real_time_data)
        logger.info(f"生成了 {len(real_time_data)} 条实时停车点数据")
        
    except Exception as e:
        logger.error(f"生成实时停车点数据时出错: {str(e)}")

def start_scheduler():
    """启动调度器"""
    try:
        # 移除已存在的任务
        scheduler.remove_all_jobs()
        
        # 添加定时任务：每 1 分钟执行一次
        scheduler.add_job(
            generate_real_time_data,
            trigger=IntervalTrigger(minutes=1),
            id='generate_real_time_data',
            name='生成实时停车点数据',
            replace_existing=True
        )
        
        # 启动调度器
        if not scheduler.running:
            scheduler.start()
            logger.info("调度器已启动")
    except Exception as e:
        logger.error(f"启动调度器时出错: {str(e)}")

def stop_scheduler():
    """停止调度器"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("调度器已停止")
    except Exception as e:
        logger.error(f"停止调度器时出错: {str(e)}")
