import random
import time
from datetime import datetime, timedelta
from django.db.models import Q
from operation_management.models import Vehicle, ScheduleTask
from demand_prediction.models import PredictionResult
from data_process.models import BikeRideData
import logging

logger = logging.getLogger(__name__)

class DataSyncService:
    """数据同步服务"""
    
    @staticmethod
    def sync_vehicle_data():
        """同步车辆数据，模拟动态变化"""
        logger.info('开始同步车辆数据...')
        
        try:
            # 获取所有车辆
            vehicles = Vehicle.objects.all()
            
            for vehicle in vehicles:
                # 模拟车辆位置漂移（小范围随机移动）
                if random.random() < 0.3:  # 30%的概率发生位置变化
                    lat_offset = random.uniform(-0.0001, 0.0001)
                    lon_offset = random.uniform(-0.0001, 0.0001)
                    vehicle.latitude += lat_offset
                    vehicle.longitude += lon_offset
                    
                    # 确保车辆在燕大边界内
                    yanshan_bounds = {
                        'north': 39.9550,
                        'south': 39.9450,
                        'east': 119.5400,
                        'west': 119.5250
                    }
                    vehicle.latitude = max(yanshan_bounds['south'], min(yanshan_bounds['north'], vehicle.latitude))
                    vehicle.longitude = max(yanshan_bounds['west'], min(yanshan_bounds['east'], vehicle.longitude))
                
                # 模拟车辆状态切换
                if random.random() < 0.1:  # 10%的概率发生状态变化
                    status_options = ['available', 'ridden', 'faulty', 'locked']
                    current_status = vehicle.status
                    new_status = random.choice([s for s in status_options if s != current_status])
                    vehicle.status = new_status
                
                # 更新时间戳
                vehicle.update_time = datetime.now()
                vehicle.save()
            
            logger.info(f'成功同步了 {len(vehicles)} 辆车辆数据')
            return True
        except Exception as e:
            logger.error(f'同步车辆数据失败: {str(e)}')
            return False
    
    @staticmethod
    def sync_prediction_data():
        """同步预测数据，模拟供需值波动"""
        logger.info('开始同步预测数据...')
        
        try:
            # 获取当前时间
            current_time = datetime.now()
            
            # 更新未来24小时的预测数据
            for hour in range(24):
                predict_time = current_time + timedelta(hours=hour)
                
                # 获取该小时的预测数据
                predictions = PredictionResult.objects.filter(
                    predict_date=predict_time.date(),
                    predict_hour=predict_time.hour
                )
                
                for prediction in predictions:
                    # 模拟供需值波动
                    if random.random() < 0.5:  # 50%的概率发生波动
                        # 需求波动（±2）
                        demand_fluctuation = random.randint(-2, 2)
                        prediction.demand = max(0, prediction.demand + demand_fluctuation)
                        
                        # 供给波动（±2）
                        supply_fluctuation = random.randint(-2, 2)
                        prediction.supply = max(0, prediction.supply + supply_fluctuation)
                        
                        prediction.save()
            
            logger.info('成功同步预测数据')
            return True
        except Exception as e:
            logger.error(f'同步预测数据失败: {str(e)}')
            return False
    
    @staticmethod
    def generate_schedule_tasks():
        """根据供需差自动生成调度任务"""
        logger.info('开始生成调度任务...')
        
        try:
            # 获取当前时间
            current_time = datetime.now()
            
            # 获取未来1小时的预测数据
            next_hour = current_time + timedelta(hours=1)
            predictions = PredictionResult.objects.filter(
                predict_date=next_hour.date(),
                predict_hour=next_hour.hour
            )
            
            # 分离过剩和不足的停车点
            surplus_spots = []  # 供给过剩
            deficit_spots = []   # 供给不足
            
            for prediction in predictions:
                difference = prediction.supply_count - prediction.demand_count
                
                # 使用默认值作为停车点信息
                if difference > 5:  # 供给过剩超过5辆
                    surplus_spots.append({
                        'spot_id': 'P00101',
                        'spot_name': '燕山大学南门停车点1',
                        'difference': difference,
                        'latitude': 39.9450,
                        'longitude': 119.5300
                    })
                elif difference < -5:  # 供给不足超过5辆
                    deficit_spots.append({
                        'spot_id': 'P00101',
                        'spot_name': '燕山大学南门停车点1',
                        'difference': abs(difference),
                        'latitude': 39.9450,
                        'longitude': 119.5300
                    })
            
            # 匹配过剩和不足的停车点，生成调度任务
            tasks_created = 0
            
            for surplus in surplus_spots:
                if not deficit_spots:
                    break
                
                # 找到最近的需求缺口停车点
                nearest_deficit = None
                min_distance = float('inf')
                
                for deficit in deficit_spots:
                    distance = DataSyncService.calculate_distance(
                        surplus['latitude'], surplus['longitude'],
                        deficit['latitude'], deficit['longitude']
                    )
                    if distance < min_distance:
                        min_distance = distance
                        nearest_deficit = deficit
                
                if nearest_deficit:
                    # 计算调度数量
                    dispatch_count = min(surplus['difference'], nearest_deficit['difference'])
                    
                    # 创建调度任务
                    task = ScheduleTask(
                        task_type='vehicle_dispatch',
                        status='pending',
                        start_location=surplus['spot_name'],
                        end_location=nearest_deficit['spot_name'],
                        dispatch_count=dispatch_count,
                        priority='high' if dispatch_count > 10 else 'medium',
                        predicted_time=next_hour
                    )
                    task.save()
                    
                    tasks_created += 1
                    
                    # 更新过剩和不足的数量
                    surplus['difference'] -= dispatch_count
                    nearest_deficit['difference'] -= dispatch_count
                    
                    # 如果缺口已填满，从列表中移除
                    if nearest_deficit['difference'] <= 0:
                        deficit_spots.remove(nearest_deficit)
                    
                    # 如果过剩已处理完，退出循环
                    if surplus['difference'] <= 0:
                        break
            
            logger.info(f'成功生成了 {tasks_created} 个调度任务')
            return tasks_created
        except Exception as e:
            logger.error(f'生成调度任务失败: {str(e)}')
            return 0
    
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """计算两点之间的距离（Haversine公式）"""
        import math
        
        # 地球半径（米）
        R = 6371000
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # 差值
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Haversine公式
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # 距离
        distance = R * c
        
        return distance
    
    @staticmethod
    def run_sync_cycle():
        """运行一次完整的数据同步周期"""
        logger.info('开始数据同步周期...')
        
        # 同步车辆数据
        vehicle_sync_success = DataSyncService.sync_vehicle_data()
        
        # 同步预测数据
        prediction_sync_success = DataSyncService.sync_prediction_data()
        
        # 生成调度任务
        tasks_created = DataSyncService.generate_schedule_tasks()
        
        logger.info(f'数据同步周期完成: 车辆同步={vehicle_sync_success}, 预测同步={prediction_sync_success}, 生成任务={tasks_created}')
        
        return {
            'vehicle_sync': vehicle_sync_success,
            'prediction_sync': prediction_sync_success,
            'tasks_created': tasks_created
        }